from dotenv import load_dotenv
from openai import OpenAI
from datetime import datetime
import json
import requests
import os

load_dotenv()

client = OpenAI()

def run_command(cmd: str):
    result = os.system(cmd)
    return result

def create_directory(name: str):
    return os.system(f"mkdir {name}")

def create_a_file(name: str):
    return os.system(f"touch {name}")

def get_weather(city: str):
    url = f"https://wttr.in/{city}?format=%C+%t"
    response = requests.get(url)

    if response.status_code == 200:
        return f"The weather in {city} is {response.text}."
    
    return "Something went wrong"


available_tools = {
    "get_weather": get_weather,
    "run_command": run_command,
    "create_directory": create_directory,
    "create_a_file": create_a_file
}

# directory create
# file create 
# init react project 
# update the file 
# delete the file 


SYSTEM_PROMPT = f"""
You are a helpful AI Assistant specialized in resolving user queries.
You operate in four stages: start, plan, action, and observe.

For each user query and based on the available tools, plan a step-by-step execution.
According to the plan, select the relevant tool from the list and perform an action to call the tool.

Wait for the observation (tool response), and based on the observation, resolve the user's query.

Rules:
- Follow the Output JSON Format strictly.
- Always perform one step at a time and wait for the next input.
- Carefully analyze the user query.

Output JSON Format:
{{
    "step": "string",                  # One of: plan, action, observe, output
    "content": "string",              # Description of the step (optional for action/observe)
    "function": "string",             # Name of the function (required for action step)
    "input": "string"                 # Input parameters for the function (required for action step)
}}

Available Tools:
- "get_weather": Takes a city name as input and returns the current weather for that city.
- "run_command": Takes a Linux command as a string, executes it, and returns the output.
- "create_directory": Takes the name of the project as input and creates the directory
- "create_a_file": Takes the name of the file as input and creates the file in the directory

Example:
User Query: What is the weather in New York?
Output: {{ "step": "plan", "content": "The user is interested in the weather data for New York." }}
Output: {{ "step": "plan", "content": "From the available tools, I should call get_weather." }}
Output: {{ "step": "action", "function": "get_weather", "input": "New York" }}
Output: {{ "step": "observe", "output": "12°C" }}
Output: {{ "step": "output", "content": "The weather in New York is currently 12°C." }}
"""


messages = [
  { "role": "system", "content": SYSTEM_PROMPT }
]

while True:
    query = input("> ")
    messages.append({ "role": "user", "content": query })

    while True:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            response_format={"type": "json_object"},
            messages=messages
        )

        messages.append({ "role": "assistant", "content": response.choices[0].message.content })
        parsed_response = json.loads(response.choices[0].message.content)

        if parsed_response.get("step") == "plan":
            print(f"🧠: {parsed_response.get("content")}")
            continue

        if parsed_response.get("step") == "action":
            tool_name = parsed_response.get("function")
            tool_input = parsed_response.get("input")

            print(f"🛠️: Calling Tool:{tool_name} with input {tool_input}")

            if available_tools.get(tool_name) != False:
                output = available_tools[tool_name](tool_input)
                messages.append({ "role": "user", "content": json.dumps({ "step": "observe", "output": output }) })
                continue
        
        if parsed_response.get("step") == "output":
            print(f"🤖: {parsed_response.get("content")}")
            break