
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from openai import OpenAI
from dotenv import load_dotenv

from langchain.chat_models import init_chat_model
from typing_extensions import TypedDict
from typing import Annotated
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, START, END
import re

# nodes
# state, graph, invoke and compile
# 1. query enhancer
# 2. Answer generation
# 3. LLM as a judge -> output 

load_dotenv()

model = 'gpt-4.1-nano'

class State(TypedDict):
    user_query: str
    sub_queries: list
    result: str
    temp_result: list

client = OpenAI()

embeddings = OpenAIEmbeddings(
    model="text-embedding-3-large"
)

vector_db = QdrantVectorStore.from_existing_collection(
    url="http://vector-db:6333",
    collection_name="web_vector",
    embedding=embeddings
)

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

    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ],
        temperature=0.2,
    )

    content = completion.choices[0].message.content.strip()

    # Parse into list
    state['sub_queries'] = [query]
    for line in content.split("\n"):
        if line.strip():
            parts = line.strip().split(".", 1)
            if len(parts) == 2:
                state['sub_queries'].append(parts[1].strip())
    return state


def generate_answers(state: State):
    state['temp_result'] = []
    enhanced_queries = state['sub_queries']
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

        chat_completion = client.chat.completions.create(
            model=model,
            messages=[
                { "role": "system", "content": SYSTEM_PROMPT },
                { "role": "user", "content": enhanced_query },
            ]
        )

        state['temp_result'].append(chat_completion.choices[0].message.content)
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
        - **ONLY** return the number of the best answer
    """

    temp_result = ''
    for i, text in enumerate(state['temp_result'], 1):
        temp_result += f"\n\n{i}. {text}"

    user_query = state['user_query']
    
    messages = [
        {"role": "system", "content": BEST_RESULT_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"User Query:\n{user_query}\n\nRetrieved answers:\n\n{temp_result}",
        },
    ]

    completion = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.0
    )

    response_text = completion.choices[0].message.content.strip()
    match = re.search(r"\b(\d+)\b", response_text)
    if match:
        selected_idx = int(match.group(1))
        state["result"] = state["temp_result"][selected_idx - 1]
    else:
        state["result"] = "I'm sorry, I could not interpret the selection."
    return state

graph_builder = StateGraph(State)

graph_builder.add_node("generate_sub_queries", generate_sub_queries)
graph_builder.add_node("generate_answers", generate_answers)
graph_builder.add_node("select_best_answer", select_best_answer)

graph_builder.add_edge(START, "generate_sub_queries")
graph_builder.add_edge("generate_sub_queries", "generate_answers")
graph_builder.add_edge("generate_answers", "select_best_answer")
graph_builder.add_edge("select_best_answer", END)

graph = graph_builder.compile()

def main():
    user = input("> ")

    _state = {
        "user_query": user,
        "result": None,
        "sub_queries": [],
        "temp_result": []
    }

    graph_result = graph.invoke(_state)
    for step in graph.stream(_state):
        keys = list(step.keys())
        step_name = keys[0]

        print(f"\n🟢 Step: {step_name}")

    print("graph_result", graph_result['result'])

main()