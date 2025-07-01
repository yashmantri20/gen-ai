
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from dotenv import load_dotenv
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from qdrant_client.http.exceptions import UnexpectedResponse
from langgraph.graph.message import add_messages
from typing import Annotated
from typing import Annotated
from langgraph.graph.message import add_messages
from langchain.chat_models import init_chat_model
from persona import HITESH_REWRITER_SYSTEM_PROMPT
import os

# nodes
# state, graph, invoke and compile
# 1. query enhancer
# 2. Answer generation
# 3. LLM as a judge -> output 

load_dotenv()

class State(TypedDict):
    collection_name: str
    user_query: str
    sub_queries: list
    result: str
    temp_result: list
    messages: Annotated[list, add_messages]

embeddings = OpenAIEmbeddings(
    model="text-embedding-3-large"
)
llm = init_chat_model(model_provider="openai", model="gpt-4.1-nano")

def generate_sub_queries(state: State):
    """
    Generate 3 sub-queries from the original query using few-shot prompting.
    """
    SYSTEM_PROMPT = """
You are a helpful AI assistant specialized in rephrasing and expanding user queries into multiple focused search queries.
Your goal is to generate 3 diverse sub-queries that cover different angles of the original question to help retrieve the most relevant information from a document store.

**Important Instructions:**
- Always generate exactly 3 sub-queries.
- Sub-queries should be clear, concise, and different ways of asking the question.
- If the original query is ambiguous, include clarifying sub-queries.
- Only return the sub-queries as a numbered list. No explanations, no extra text.

**Examples:**

User Query:
"What is the impact of remote work on employee productivity?"

Sub-Queries:
1. How does working remotely affect employee productivity?
2. What studies measure productivity changes due to remote work?
3. Benefits and drawbacks of remote work on work performance.

---

User Query:
"Explain Kubernetes architecture"

Sub-Queries:
1. What are the main components of Kubernetes architecture?
2. How does Kubernetes manage containers and clusters?
3. Overview of Kubernetes control plane and nodes.

"""

    query = state['user_query']

    response = llm.invoke([
        *state["messages"][-10:],
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": query}
    ])

    content = response.content.strip()

    # Parse into list
    state['sub_queries'] = [query]
    for line in content.split("\n"):
        if line.strip():
            parts = line.strip().split(".", 1)
            if len(parts) == 2:
                state['sub_queries'].append(parts[1].strip())
    print(state['sub_queries'])
    return state

def generate_answers(state: State):
    state['temp_result'] = []
    enhanced_queries = state['sub_queries']
    # Initialize the vector DB only when needed
    try:
        vector_db = QdrantVectorStore.from_existing_collection(
            url=os.getenv("QDRANT_URL"),
            api_key=os.getenv("QDRANT_API_KEY"),
            collection_name=state['collection_name'],
            embedding=embeddings
        )
    except UnexpectedResponse:
        state["result"] = "Index not found. Please run the indexing step before asking questions."
        return state
    for enhanced_query in enhanced_queries:
        search_results = vector_db.similarity_search(
            query=enhanced_query
        )

        context = "\n\n\n".join([
        f"Page Content: {result.page_content}\n\nPage Description: {result.metadata['description']}\n\nUrl: {result.metadata['source']}"
        for result in search_results
        ])

        SYSTEM_PROMPT = f"""
        You are a helpful AI assistant designed to answer user questions **strictly based on the context provided below**, which has been retrieved from webpages using recursive web loading.

        **Important Rules:**
        - You must not use any outside knowledge beyond what is included in the context.
        - If the answer is present in the context, answer clearly, citing the relevant *Url*.
        - If the answer is **not** available in the context, simply respond with:

            **"I'm sorry, there is no information available in the provided context to answer that question."**

        - Do **not** suggest referring to external sources, or websites unless the context explicitly mentions them.
        - Do **not** fabricate urls, page titles, or suggest next steps.
        - Do **not** ask follow-up questions or clarify anything.
        - Stick exactly to what's in the context.

        **Formatting Instructions (for web display):**
        - Use Markdown formatting:
            - **Bold** for headings and important statements.
            - *Italics* for emphasis.
            - Bullet points or numbered lists for clarity.
            - Code blocks for commands or examples.

        **Example Style Guide:**
        - **Headings:** Bold
        - *Keywords or important terms:* Italic
        - Code snippets: Code blocks (```)

        **Context for Answering the User’s Query:**

        {context}
        """

        response = llm.invoke([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": enhanced_query}
        ])

        content = response.content.strip()

        state['temp_result'].append(content)
    return state

def select_best_answer(state: State):
    """
    Given a user query and a list of top retrieved answers,
    use the LLM to select the best answer as the answer.

    Returns a formatted string with the selected answer or a fallback message.
    """
    BEST_RESULT_SYSTEM_PROMPT = """
        You are an expert AI assistant tasked with selecting the best information answer to answer the user's query.

        **Your task:**
        - Carefully read the user query and each retrieved answer.
        - Select the answer that most directly, completely, and accurately answers the query.
        - The best answer should be the one that is most specific and comprehensive.
        - If none of the answers sufficiently address the question, respond:
        **"I'm sorry, none of the provided answers contain information to answer this query."**

        **Rules:**
        - Do NOT use any outside knowledge.
        - Select based strictly on the provided answers.
        - **ONLY return the text of the best answer exactly as it is given**.
        - Do NOT add, remove explanation or formatting 
        - Just remove the Ans n. text and give everything as it is.
        - Include source link everytime
    """

    temp_result = ''
    for i, text in enumerate(state['temp_result'], 1):
        temp_result += f"\n\nAns {i}. {text}"
    print(temp_result)
    user_query = state['user_query']
    
    messages = [
        {"role": "system", "content": BEST_RESULT_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"User Query:\n{user_query}\n\nRetrieved answers:\n\n{temp_result}",
        },
    ]

    response = llm.invoke(messages)

    content = response.content.strip()

    return {"messages": [response], "result": content}

def answer_like_hitesh_sir(state: State):
    SYSTEM_PROMPT = HITESH_REWRITER_SYSTEM_PROMPT

    factual_answer = state["result"]

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Factual Answer:\n{factual_answer}"},
    ]

    response = llm.invoke(messages)
    state["result"] = response.content.strip()

    return state

graph_builder = StateGraph(State)

graph_builder.add_node("generate_sub_queries", generate_sub_queries)
graph_builder.add_node("generate_answers", generate_answers)
graph_builder.add_node("select_best_answer", select_best_answer)
graph_builder.add_node("answer_like_hitesh_sir", answer_like_hitesh_sir)

graph_builder.add_edge(START, "generate_sub_queries")
graph_builder.add_edge("generate_sub_queries", "generate_answers")
graph_builder.add_edge("generate_answers", "select_best_answer")
graph_builder.add_edge("select_best_answer", "answer_like_hitesh_sir")
graph_builder.add_edge("answer_like_hitesh_sir", END)

def compile_graph_with_checkpointer(checkpointer):
    graph_with_checkpointer = graph_builder.compile(checkpointer=checkpointer)
    return graph_with_checkpointer
