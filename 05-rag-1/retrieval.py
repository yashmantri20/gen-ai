# Retrieval 

from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI()

# Vector embeddings
embeddings = OpenAIEmbeddings(
    model="text-embedding-3-large"
)

vector_db = QdrantVectorStore.from_existing_collection(
    url="http://localhost:6333",
    collection_name="nodejs_vector",
    embedding=embeddings
)

# input
while True:
    query = input(">")

    if query == 'exit':
        print("Closing the chat")
        break

    search_results = vector_db.similarity_search(
        query=query
    )

    context = "\n\n\n".join([f"Page Content: {result.page_content}\nPage Number: {result.metadata['page_label']}\nFile Location: {result.metadata['source']}" for result in search_results])

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
            { "role": "system", "content": SYSTEM_PROMPT },
            { "role": "user", "content": query },
        ]
    )


    print(f"🤖: {chat_completion.choices[0].message.content}")