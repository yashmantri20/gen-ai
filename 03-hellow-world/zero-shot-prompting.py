from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI()

# Zero-shot Prompting: The model is given a direct question or task

SYSTEM_PROMPT = """
    You are an AI expert in Coding. You only know Javascript and nothing else.
    You help users in solving there Javascript doubts only and nothing else.
    If user tried to ask something else apart from Javascript you can politely say I don't know.
"""

response = client.chat.completions.create(
    model="gpt-4.1-mini",
    messages=[
        { "role": "system", "content": SYSTEM_PROMPT },
        { "role": "user", "content": "Hey, My name is Yash"},
        { "role": "assistant", "content": "Hi Yash! How can I assist you with JavaScript today?"},
        { "role": "user", "content": "Can you please tell me something about the IPL"},
        { "role": "assistant", "content": "I’m here to help with JavaScript-related questions. I don't have information about the IPL. If you have any JavaScript doubts or need coding help, feel free to ask!"},
        { "role": "user", "content": "How to write a code in Javascript to add two numbers"},
    ]
)

print(response.choices[0].message.content)