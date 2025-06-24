import streamlit as st
from dotenv import load_dotenv
from langchain_community.document_loaders import WebBaseLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from openai import OpenAI
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# Load env variables
load_dotenv()

client = OpenAI()
embeddings = OpenAIEmbeddings(model="text-embedding-3-large")

st.set_page_config(page_title="Chaidocs Q&A", layout="centered")
st.title("📄 RAG based Chatbot - Chat with chaidocs documents")

# Session state for vector store
if "vector_store" not in st.session_state:
    st.session_state.vector_store = None

if "messages" not in st.session_state:
    st.session_state.messages = []

if "web_indexed" not in st.session_state:
    st.session_state.web_indexed = False


index_url = "https://docs.chaicode.com/youtube/getting-started/"
base = "https://docs.chaicode.com"

indexing_status = st.empty()

res = requests.get(index_url)
res.raise_for_status()
soup = BeautifulSoup(res.text, "html.parser")

if not st.session_state.web_indexed:
    indexing_status.info("📥 Parsing the webpage")

links = set()
for a in soup.find_all('a', href=True):
    href = a["href"]
    full = urljoin(base, href)
    if full.startswith(base + "/youtube/chai-aur"):
        links.add(full)

if not st.session_state.web_indexed:
    indexing_status.info("📥 Loading the webpages")
    try:
        indexing_status.info("📥 Checking if indexing exists...")
        vector_db = QdrantVectorStore.from_existing_collection(
            url="http://vector-db:6333",
            collection_name="web_vector",
            embedding=embeddings
        )
        indexing_status.success("✅ Indexing found.")
    except Exception as e:
        loader = WebBaseLoader(list(links))
        docs = loader.load()

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=400
        )
        texts_split = text_splitter.split_documents(documents=docs)

        indexing_status.info("📥 Indexing PDF into vector database...")

        vector_db = QdrantVectorStore.from_documents(
            documents=texts_split,
            url="http://vector-db:6333",
            collection_name="web_vector",
            embedding=embeddings
        )
        indexing_status.success("✅ Indexing complete.")
    st.session_state.vector_store = vector_db
    st.session_state.web_indexed = True

# Chat section
if st.session_state.vector_store:
    user_query = st.chat_input("Ask something about the document...")

    for msg in st.session_state.messages:
        st.chat_message(msg["role"]).write(msg["content"])

    if user_query:
        st.session_state.messages.append({"role": "user", "content": user_query})
        st.chat_message("user").write(user_query)

        with st.spinner("Thinking..."):
            search_results = st.session_state.vector_store.similarity_search(query=user_query)

            context = "\n\n\n".join([f"Page Content: {result.page_content}\nPage description: {result.metadata['description']}\nFile Location: {result.metadata['source']}" for result in search_results])

            SYSTEM_PROMPT = f"""
                You are a helpfull AI Assistant who answers user query accurately based on the available context
                retrieved from the webpage along with page_contents and page source.

                Do not use any outside knowledge beyond what is given in the context

                You should only ans the user based on the following context and navigate the user
                to open the right page source to know more.

                Just give the information that is asked for don't ask questions like would you like guidance installing configuring Nginx on your VPS?, etc.....
                
                Guidelines:
                - Format your answer for terminal display using ANSI escape codes:
                    - Use bright colors to highlight keywords and examples.
                    - Use bold or underline for headings.
                    - Use proper indentation and spacing for readability.
                    
                Context:
                {context}
            """

            # Limit message history to avoid token overflow (last 6 exchanges max)
            history_limit = 12  # 6 pairs (user + assistant)
            trimmed_history = st.session_state.messages[-history_limit:]

            chat_messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                *trimmed_history,
                {"role": "user", "content": user_query}
            ]

            chat_completion = client.chat.completions.create(
                model="gpt-4.1-nano",  # Ensure this is a valid model you have access to
                messages=chat_messages
            )

            answer = chat_completion.choices[0].message.content
            st.session_state.messages.append({"role": "assistant", "content": answer})
            st.chat_message("assistant").write(answer)
