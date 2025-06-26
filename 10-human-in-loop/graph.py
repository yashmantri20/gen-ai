from typing_extensions import TypedDict
from typing import Annotated
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, START, END
from langchain.chat_models import init_chat_model
from dotenv import load_dotenv
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.mongodb import MongoDBSaver
from langgraph.types import interrupt, Command
import json

load_dotenv()

class State(TypedDict):
    messages: Annotated[list, add_messages]

@tool
def human_assistance(query: str) -> str:
    """Request assistance from a human."""
    human_response = interrupt(
        {"query": query})  # This saves the state in DB and kills the graph
    return human_response["data"]

# Tool creation
tools = [human_assistance]

# Tool binding
llm = init_chat_model(model_provider="openai", model="gpt-4.1-nano")
model_with_tools = llm.bind_tools(tools)

def chatbot(state: State):
    response = model_with_tools.invoke(state['messages'])
    return {"messages": [response]}

tool_node = ToolNode(tools)

graph_builder = StateGraph(State)

graph_builder.add_node("chatbot", chatbot)
graph_builder.add_node("tools", tool_node)

graph_builder.add_edge(START, "chatbot")
graph_builder.add_conditional_edges("chatbot", tools_condition)
graph_builder.add_edge("tools", "chatbot")
graph_builder.add_edge("chatbot", END)

graph = graph_builder.compile()

def compile_graph_with_checkpointer(checkpointer):
    graph_with_checkpointer = graph_builder.compile(checkpointer=checkpointer)
    return graph_with_checkpointer


def user_chat():
    #   mongodb://<username>:<pass>@<host>:<port>
    DB_URI = "mongodb://admin:admin@mongodb:27017"
    config = {"configurable": {"thread_id": "22"}}

    with MongoDBSaver.from_conn_string(DB_URI) as mongo_checkpointer:

        graph_with_mongo = compile_graph_with_checkpointer(mongo_checkpointer)

        query = input("> ")

        _state = State({"messages": [{"role": "user", "content": query}]})
        for event in graph_with_mongo.stream(_state, config, stream_mode = "values"):
            if "messages" in event:
                event['messages'][-1].pretty_print()

def admin_call():
    DB_URI = "mongodb://admin:admin@mongodb:27017"
    config = {"configurable": {"thread_id": "22"}}

    with MongoDBSaver.from_conn_string(DB_URI) as mongo_checkpointer:
        graph_with_mongo = compile_graph_with_checkpointer(mongo_checkpointer)

        state = graph_with_mongo.get_state(config=config)
        last_message = state.values['messages'][-1]

        tool_calls = last_message.additional_kwargs.get("tool_calls", [])

        user_query = None

        for call in tool_calls:
            if call.get("function", {}).get("name") == "human_assistance":
                args = call["function"].get("arguments", "{}")
                try:
                    args_dict = json.loads(args)
                    user_query = args_dict.get("query")
                except json.JSONDecodeError:
                    print("Failed to decode function arguments.")

        print("User Has a Query", user_query)
        solution = input("> ")

        resume_command = Command(resume={"data": solution})

        for event in graph_with_mongo.stream(resume_command, config, stream_mode="values"):
            if "messages" in event:
                event["messages"][-1].pretty_print()


user_chat()
# admin_call()
