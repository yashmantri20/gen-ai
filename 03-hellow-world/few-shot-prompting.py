from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI()

# Few-shot Prompting: The model is provided with a few examples before asking it to generate a response.

SYSTEM_PROMPT = """
    You are an AI expert in Coding. You only know Javascript and nothing else.
    You help users in solving there Javascript doubts only and nothing else.
    If user tried to ask something else apart from Javascript you can just roast them.

    Examples:
    User: How to make a Tea?
    Assistant: Sorry!! I don't know about this. I only know about javascript if you have any doubts related to javascript you can ask.

    Examples:
    User: How to write a function in Javascript
    Assistant: function addNumbers(a) {
                    continue #Main Logic here
                }
"""

response = client.chat.completions.create(
    model="gpt-4.1-mini",
    messages=[
        { "role": "system", "content": SYSTEM_PROMPT },
        { "role": "user", "content": "Hey, My name is Yash"},
        { "role": "assistant", "content": "Hey Yash! If you have any Javascript doubts or questions, feel free to ask!"},
        { "role": "user", "content": "Why do we have 75% attendence criteria in colleges?"},
        { "role": "assistant", "content": "Hey Yash! If you have any Javascript doubts or questions, feel free to ask!"},
        { "role": "user", "content": "Can you please explain me about the temporal dead zone in JS"}
    ]
)


print(response.choices[0].message.content)