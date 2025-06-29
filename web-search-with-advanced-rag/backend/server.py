# api_server.py

from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.responses import JSONResponse
from langgraph_pipeline import graph
from sse_starlette.sse import EventSourceResponse
import json
from fastapi.middleware.cors import CORSMiddleware
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from langchain_community.document_loaders import RecursiveUrlLoader
from collections import defaultdict
import re

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

@app.post("/index")
async def index_website(request: IndexRequest):
    try:
         # Load docs
        loader = RecursiveUrlLoader(request.base_url, max_depth=request.depth)
        docs = loader.load()

        # Optional: group by section
        sections = []
        for doc in docs:
            title = doc.metadata.get("title", "")
            sections.append(title)

        # Split
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=400
        )
        texts_split = text_splitter.split_documents(documents=docs)

        # Embed and index
        embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
        vector_store = QdrantVectorStore.from_documents(
            documents=texts_split,
            url="http://vector-db:6333",
            collection_name="web_vector",
            embedding=embeddings
        )

        return JSONResponse(content={"message": "Indexing complete", "details": {
            "total_documents": len(docs),
            "sections_indexed": sections
        }})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/ask")
async def ask_question(request: QueryRequest):
    user_query = request.query

    # Initial state
    _state = {
        "user_query": user_query,
        "result": None,
        "sub_queries": [],
        "temp_result": []
    }

    # Run the graph
    graph_result = graph.invoke(_state)

    return JSONResponse(content={
        "query": user_query,
        "answer": graph_result["result"],
        "sub_queries": graph_result["sub_queries"],
    })

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
            payload = {
                "step": step_name
            }
            yield f"event: step\ndata: {json.dumps(payload)}\n\n"

        # Signal done
        yield f"event: done\ndata: {json.dumps(_state)}\n\n"

    return EventSourceResponse(event_generator())