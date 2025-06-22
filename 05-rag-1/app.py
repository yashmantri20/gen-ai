import streamlit as st
from pathlib import Path
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from openai import OpenAI
import tempfile

# Load env variables
load_dotenv()

# OpenAI Client
client = OpenAI()
embeddings = OpenAIEmbeddings(model="text-embedding-3-large")

st.set_page_config(page_title="PDF Q&A with Qdrant", layout="centered")
st.title("📄 RAG based Chatbot - Chat with your PDF")

# Session state for vector store
if "vector_store" not in st.session_state:
    st.session_state.vector_store = None

if "messages" not in st.session_state:
    st.session_state.messages = []

if "pdf_indexed" not in st.session_state:
    st.session_state.pdf_indexed = False

# File upload
uploaded_file = st.file_uploader("Upload a PDF file", type=["pdf"])

# Reset state if file is removed
if uploaded_file is None and st.session_state.get("current_file"):
    st.session_state.update({
        "vector_store": None,
        "messages": [],
        "pdf_indexed": False,
        "current_file": None,
    })

# Detect a new file and reset index flag
if uploaded_file and st.session_state.get("current_file") != uploaded_file.name:
        st.session_state.update({
        "vector_store": None,
        "messages": [],
        "pdf_indexed": False,
        "current_file": uploaded_file.name,
    })

indexing_status = st.empty()

if uploaded_file and not st.session_state.pdf_indexed:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name

    indexing_status.success("✅ PDF uploaded successfully!")

    # Load and split PDF
    loader = PyPDFLoader(tmp_path)
    docs = loader.load()
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=400)
    texts_split = text_splitter.split_documents(docs)

    # Index into Qdrant
    indexing_status.info("📥 Indexing PDF into vector database...")
    vector_store = QdrantVectorStore.from_documents(
        documents=texts_split,
        url=st.secrets["QDRANT_URL"],
        api_key=st.secrets["QDRANT_API_KEY"],
        collection_name="uploaded_pdf_vector",
        embedding=embeddings
    )
    indexing_status.success("✅ Indexing complete.")
    st.session_state.vector_store = vector_store
    st.session_state.pdf_indexed = True

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

            context = "\n\n\n".join([
                f"Page Content: {r.page_content}\nPage Number: {r.metadata.get('page_label', 'N/A')}\nFile: {r.metadata.get('source', 'N/A')}"
                for r in search_results
            ])

            SYSTEM_PROMPT = f"""
                You are a helpfull AI Assistant who answers user query based on the available context
                retrieved from a PDF file along with page_contents and page number.

                You should only ans the user based on the following context and navigate the user
                to open the right page number to know more.

                Context:
                {context}
            """

            chat_completion = client.chat.completions.create(
                model="gpt-4.1-nano",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_query}
                ]
            )

            answer = chat_completion.choices[0].message.content
            st.session_state.messages.append({"role": "assistant", "content": answer})
            st.chat_message("assistant").write(answer)
