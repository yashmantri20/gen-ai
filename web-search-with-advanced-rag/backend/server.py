# api_server.py

from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.responses import JSONResponse
from langgraph_pipeline import graph
from sse_starlette.sse import EventSourceResponse
from fastapi.responses import StreamingResponse
import json
from fastapi.middleware.cors import CORSMiddleware
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from langchain_community.document_loaders import RecursiveUrlLoader
import asyncio

# TODO:
# 1. Delete DB once done and on demand deletion
# 2. Max depth
# 3. unique DB thing

# FastAPI app
app = FastAPI()

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
            embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
            await asyncio.to_thread(
                QdrantVectorStore.from_documents,
                documents=texts_split,
                url="http://vector-db:6333",
                collection_name="web_vector1",
                embedding=embeddings
                )
            yield f"event: step\ndata: Documents embedded and stored in Qdrant\n\n"

            result = {
                "total_documents": len(docs),
                "sections_indexed": sections
            }
            yield f"event: done\ndata: {json.dumps(result)}\n\n"

        except Exception as e:
            yield f"event: error\ndata: {str(e)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
    
@app.get("/ask-stream")
async def ask_question_stream(query: str):
    _state = {
        "user_query": query,
        "result": None,
        "sub_queries": [],
        "temp_result": []
    }

    async def event_generator():
        async for step in graph.astream(_state):
            keys = list(step.keys())
            step_name = keys[0]
            step_data = step[step_name]

            _state.update(step_data)

            payload = {
                "step": step_name
            }
            yield f"event: step\ndata: {json.dumps(payload)}\n\n"

        yield f"event: done\ndata: {json.dumps(_state)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")