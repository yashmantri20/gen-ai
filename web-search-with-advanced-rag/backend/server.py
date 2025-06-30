# api_server.py

from fastapi import FastAPI
from pydantic import BaseModel
from langgraph_pipeline import compile_graph_with_checkpointer
from fastapi.responses import StreamingResponse
import json
from fastapi.middleware.cors import CORSMiddleware
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from langchain_community.document_loaders import RecursiveUrlLoader
import asyncio
from qdrant_client import QdrantClient
import uuid
from contextlib import asynccontextmanager
from langgraph.checkpoint.mongodb import AsyncMongoDBSaver
from langchain_core.messages import messages_to_dict

# TODO:
# 1. Max depth

# FastAPI app
DB_URI = "mongodb://admin:admin@mongodb:27017"

@asynccontextmanager
async def lifespan(app: FastAPI):
    saver_cm = AsyncMongoDBSaver.from_conn_string(DB_URI)
    saver = await saver_cm.__aenter__()

    graph = compile_graph_with_checkpointer(checkpointer=saver)

    app.state.mongo_saver_cm = saver_cm
    app.state.mongo_saver = saver
    app.state.graph_with_mongo = graph

    print("✅ Lifespan startup completed")
    try:
        yield
    finally:
        await saver_cm.__aexit__(None, None, None)
        print("✅ MongoDB saver closed")

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or ["http://localhost:3000"] for security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    query: str

class IndexRequest(BaseModel):
    base_url: str
    depth: int = 2

@app.get("/index-stream")
async def index_stream(base_url: str, depth: int):
    async def event_generator():
        try:
            yield f"event: info\ndata: Starting indexing for {base_url}\n\n"

            # Step 1: Load documents
            loader = RecursiveUrlLoader(base_url, max_depth=1)
            docs = await asyncio.to_thread(loader.load)
            yield f"event: step\ndata: Loaded {len(docs)} documents\n\n"
            await asyncio.sleep(0.1)

            # Step 2: Extract section titles
            sections = [doc.metadata.get("title", "Untitled") for doc in docs]
            yield f"event: step\ndata: Extracted {len(sections)} section titles\n\n"
            await asyncio.sleep(0.1)

            # Step 3: Split documents
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=400
            )
            texts_split = text_splitter.split_documents(documents=docs)
            yield f"event: step\ndata: Split into {len(texts_split)} text chunks\n\n"
            await asyncio.sleep(0.1)

            # Step 4: Embed and store in vector DB
            collection_name = f"web_vector_{uuid.uuid4().hex}"
            embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
            await asyncio.to_thread(
                QdrantVectorStore.from_documents,
                documents=texts_split,
                url="http://vector-db:6333",
                collection_name=collection_name,
                embedding=embeddings
                )
            yield f"event: step\ndata: Documents embedded and stored in Qdrant\n\n"

            result = {
                "collection_name": collection_name,
                "total_documents": len(docs),
                "sections_indexed": sections
            }
            yield f"event: done\ndata: {json.dumps(result)}\n\n"

        except Exception as e:
            yield f"event: error\ndata: {str(e)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
    
@app.get("/ask-stream")
async def ask_question_stream(query: str, collection_name: str):
    _state = {
        "collection_name": collection_name,
        "user_query": query,
        "result": None,
        "sub_queries": [],
        "temp_result": [],
        "messages": [{"role":"user", "content": query}]
    }

    async def event_generator():
        config = {"configurable": {"thread_id": "47"}}
        async for step in app.state.graph_with_mongo.astream(_state, config):
            keys = list(step.keys())
            step_name = keys[0]
            step_data = step[step_name]

            serializable_state = {
                **step_data,
                "messages": messages_to_dict(step_data["messages"])
            }
            _state.update(serializable_state)

            payload = {
                "step": step_name
            }
            yield f"event: step\ndata: {json.dumps(payload)}\n\n"

        yield f"event: done\ndata: {json.dumps(_state)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.delete("/delete-collection")
async def delete_collection(name: str):
    client = QdrantClient(url="http://vector-db:6333")
    client.delete_collection(collection_name=name)
    return {"status": "deleted"}