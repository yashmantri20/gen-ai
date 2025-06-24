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
    url="http://vector-db:6333",
    collection_name="web_vector",
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

    chat_completion = client.chat.completions.create(
        model="gpt-4.1-nano",
        messages=[
            { "role": "system", "content": SYSTEM_PROMPT },
            { "role": "user", "content": query },
        ]
    )


    print(f"🤖: {chat_completion.choices[0].message.content}")