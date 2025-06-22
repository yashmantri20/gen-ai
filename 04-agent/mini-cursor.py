from dotenv import load_dotenv
from openai import OpenAI
import json
import os
import webbrowser
import subprocess
import re

load_dotenv()

client = OpenAI()

# ----------------------- TOOL DEFINITIONS --------------------------

PROJECT_CONTEXT_FILE = "project_context.json"

# Load existing context from file if exists
if os.path.exists(PROJECT_CONTEXT_FILE):
    with open(PROJECT_CONTEXT_FILE, 'r') as f:
        project_context = json.load(f)
else:
    project_context = {
        "name": None,
        "typescript": False,
        "package_manager": "npm",
        "root_directory": None
    }

def save_context():
    with open(PROJECT_CONTEXT_FILE, 'w') as f:
        json.dump(project_context, f, indent=2)

def create_directory(name: str):
    try:
        os.makedirs(name, exist_ok=True)
        return f"Directory '{name}' created or already exists."
    except Exception as e:
        return str(e)

def create_a_file(name: str):
    try:
        with open(name, 'w') as f:
            f.write("")
        return f"File '{name}' created."
    except Exception as e:
        return str(e)

def update_file(params: str):
    try:
        data = json.loads(params)
        path = data.get("path")
        content = data.get("content")
        with open(path, 'w') as f:
            f.write(content)
        return f"File '{path}' updated."
    except Exception as e:
        return str(e)

def delete_file(path: str):
    try:
        os.remove(path)
        return f"File '{path}' deleted."
    except Exception as e:
        return str(e)

def read_file(path: str):
    try:
        if os.path.isfile(path):
            with open(path, 'r') as f:
                return f.read()
        else:
            return f"File '{path}' does not exist."
    except Exception as e:
        return str(e)

def find_file_in_directory(directory: str, filename: str):
    for root, dirs, files in os.walk(directory):
        for file in files:
            if filename == file:
                return os.path.join(root, file)
    return None

def locate_file(params: str):
    try:
        data = json.loads(params)
        directory = data.get("directory", ".")
        filename = data.get("filename")
        result = find_file_in_directory(directory, filename)
        return result if result else f"No exact match for '{filename}' found."
    except Exception as e:
        return str(e)

def install_package(params: str):
    try:
        data = json.loads(params)
        directory = data.get("directory", ".")
        package = data.get("package")
        return os.system(f"cd {directory} && npm install {package}")
    except Exception as e:
        return str(e)

def start_dev_server(directory: str):
    try:
        subprocess.Popen("npm start", cwd=directory, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"Development server started in background for '{directory}'"
    except Exception as e:
        return str(e)

def open_browser(url: str):
    try:
        webbrowser.open(url)
        return f"Browser opened at {url}"
    except Exception as e:
        return str(e)

def init_react_app(params: str):
    try:
        data = json.loads(params)
        name = data.get("name", "my-app")
        typescript = data.get("typescript", False)
        package_manager = data.get("package_manager", "npm")

        project_context["root_directory"] = name
        save_context()

        template = "--template typescript" if typescript else ""
        command = f"npx create-react-app {name} {template} --use-{package_manager}"
        return os.system(command)
    except Exception as e:
        return str(e)

def set_project_context(params: str):
    try:
        data = json.loads(params)
        project_context.update(data)
        save_context()
        return f"Project context updated: {project_context}"
    except Exception as e:
        return str(e)

def get_project_context(_: str):
    try:
        return json.dumps(project_context, indent=2)
    except Exception as e:
        return str(e)

def reset_project_context(_: str):
    global project_context
    project_context = {
        "name": None,
        "typescript": False,
        "package_manager": "npm",
        "root_directory": None
    }
    save_context()
    return "Project context has been reset."

def find_project_directory(project_name: str):
    try:
        normalized_target = re.sub(r"[^a-zA-Z0-9]", "", project_name.lower())
        for root, dirs, _ in os.walk("."):
            for d in dirs:
                norm_d = re.sub(r"[^a-zA-Z0-9]", "", d.lower())
                if norm_d == normalized_target:
                    abs_path = os.path.abspath(os.path.join(root, d))
                    project_context["root_directory"] = abs_path
                    save_context()
                    return f"Matched and set project directory: {abs_path}"
        return f"No matching folder found for project '{project_name}'"
    except Exception as e:
        return str(e)

# ------------------------ AVAILABLE TOOLS --------------------------

available_tools = {
    "create_directory": create_directory,
    "create_a_file": create_a_file,
    "init_react_app": init_react_app,
    "install_package": install_package,
    "start_dev_server": start_dev_server,
    "open_browser": open_browser,
    "update_file": update_file,
    "delete_file": delete_file,
    "read_file": read_file,
    "set_project_context": set_project_context,
    "get_project_context": get_project_context,
    "reset_project_context": reset_project_context,
    "locate_file": locate_file,
    "find_project_directory": find_project_directory
}

# ------------------------ SYSTEM PROMPT ----------------------------

SYSTEM_PROMPT = f"""
You are a helpful React AI Assistant specialized in creating React applications.
You operate in four stages: start, plan, action, and observe.

Always begin by asking about the project details (like name, typescript usage, and package manager).
Use the `set_project_context` function to store this, and `get_project_context` when you need to recall it.
To switch to a new project, first call `reset_project_context`, then use `set_project_context` again.

You can assume the current working directory of the project is `project_context['root_directory']` once set.

If a user mentions a project name in natural language (e.g., "todo-list project"), and no context is set, use `find_project_directory` to search and set it automatically by normalizing folder names.

If searching for a file, use `locate_file` instead of assuming extensions. Match full file names exactly.

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
- "create_directory": Takes the name of the project as input and creates the directory
- "create_a_file": Takes the name of the file as input and creates the file in the directory
- "init_react_app": Takes JSON string with name, typescript (bool), and package_manager (npm/yarn)
- "install_package": Takes JSON string with directory and package
- "start_dev_server": Takes project directory and runs `npm start`
- "open_browser": Takes a URL and opens it in browser
- "update_file": Takes JSON with `path` and `content`, and replaces the file content
- "delete_file": Takes a string path of the file to delete
- "read_file": Takes a string path and returns the content of the file
- "set_project_context": Takes JSON with "name", "typescript", and "package_manager"
- "get_project_context": Returns current project metadata
- "reset_project_context": Resets the project metadata
- "locate_file": Finds a file by name inside a directory
- "find_project_directory": Finds and sets root directory based on normalized project name
"""

# ----------------------------- MAIN LOOP ------------------------------

messages = [
  { "role": "system", "content": SYSTEM_PROMPT }
]

while True:
    query = input("\n👤 > ")
    messages.append({ "role": "user", "content": query })

    while True:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            response_format={"type": "json_object"},
            messages=messages
        )

        reply = response.choices[0].message.content
        messages.append({ "role": "assistant", "content": reply })

        parsed = json.loads(reply)
        step = parsed.get("step")

        if not step:
            print("⚠️  No step returned. Waiting for user input.")
            break

        if step == "plan":
            print(f"🧠 PLAN: {parsed['content']}")

        if step == "action":
            func = parsed.get("function")
            arg = parsed.get("input")

            print(f"🔧 ACTION: {func} → {arg}")
            if func in available_tools:
                result = available_tools[func](arg)
            else:
                result = f"Unknown tool: {func}"

            messages.append({
                "role": "user",
                "content": json.dumps({"step": "observe", "content": result})
            })
            continue

        if step == "observe":
            print(f"📥 OBSERVATION: {parsed['content']}")

        if step == "output":
            print(f"✅ OUTPUT: {parsed['content']}")
            break
