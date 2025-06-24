# indexing

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.document_loaders import WebBaseLoader
from dotenv import load_dotenv
from langchain_qdrant import QdrantVectorStore
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

load_dotenv()

#Read all the topics
index_url = "https://docs.chaicode.com/youtube/getting-started/"
base = "https://docs.chaicode.com"

res = requests.get(index_url)
res.raise_for_status()
soup = BeautifulSoup(res.text, "html.parser")

links = set()
for a in soup.find_all('a', href=True):
    href = a["href"]
    full = urljoin(base, href)
    if full.startswith(base + "/youtube/chai-aur"):
        links.add(full)

print(f"Found {len(links)} pages")

# Reading website
loader = WebBaseLoader(list(links))
docs = loader.load()

# Text splitting
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=400
)
texts_split = text_splitter.split_documents(documents=docs)

print(texts_split)

# Vector embeddings
embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
print("embeddings")

# Using [embeddings] create embeddings of [texts_split] and store in DB
vector_store = QdrantVectorStore.from_documents(
    documents=texts_split,
    url="http://vector-db:6333",
    collection_name="web_vector",
    embedding=embeddings
)

print("Indexing of Documents Done...")