from typing_extensions import TypedDict
from typing import Annotated
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, START, END
from langchain.chat_models import init_chat_model
from dotenv import load_dotenv
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode, tools_condition
import requests

load_dotenv()

class State(TypedDict):
    messages: Annotated[list, add_messages]

@tool()
def get_weather(city: str):
    """Takes a city name as input and returns the current weather for that city."""
    url = f"https://wttr.in/{city}?format=%C+%t"
    response = requests.get(url)

    if response.status_code == 200:
        return f"The weather in {city} is {response.text}."
    
    return "Something went wrong"

# Tool creation
tools = [get_weather]

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

graph = graph_builder.compile()

def main():
    user_query = input("> ")

    _state = {"messages": [{"role": "user", "content": user_query}]}

    result = graph.invoke(_state)
    for event in graph.stream(_state, stream_mode = "values"):
        if "messages" in event:
            event['messages'][-1].pretty_print()

main()