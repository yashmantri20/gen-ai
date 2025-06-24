# indexing 

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pathlib import Path
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv
from langchain_qdrant import QdrantVectorStore

load_dotenv()

pdf_path = Path(__file__).parent / "nodejs.pdf"

# Reading Docs
loader = PyPDFLoader(file_path = pdf_path)
docs = loader.load()

print(docs[0])
# Text splitting
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=400
)
# print(text_splitter)
texts_split = text_splitter.split_documents(documents=docs)

# # Vector embeddings
embeddings = OpenAIEmbeddings(model="text-embedding-3-large")

# # Using [embeddings] create embeddings of [texts_split] and store in DB
vector_store = QdrantVectorStore.from_documents(
    documents=texts_split,
    url="http://vector-db:6333",
    collection_name="nodejs_vector",
    embedding=embeddings
)

print("Indexing of Documents Done...")
