# indexing

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.document_loaders import WebBaseLoader
from dotenv import load_dotenv
from langchain_qdrant import QdrantVectorStore
from langchain_community.document_loaders import RecursiveUrlLoader
from collections import defaultdict
import re

load_dotenv()

#Read all the topics
base = "https://docs.chaicode.com"

sections = defaultdict(list)
pattern = re.compile(r"/youtube/([^/]+)/")

loader = RecursiveUrlLoader(base, max_depth=4)
docs = loader.load()

print(len(docs))
for doc in docs:
    url = doc.metadata.get("source", "")
    match = pattern.search(url)
    if match:
        section = match.group(1)
        sections[section].append(url)

# Print grouped results\
for section, urls in sections.items():
    print(f"\nSection: {section} ({len(urls)} URLs)")
    for url in urls:
        print("  ", url)


# Text splitting
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=400
)
texts_split = text_splitter.split_documents(documents=docs)

# print(texts_split)

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