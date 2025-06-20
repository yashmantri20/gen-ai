from dotenv import load_dotenv
from openai import OpenAI
import json
from google import genai

load_dotenv()

client = OpenAI()
geminiClient = genai.Client(api_key='key')
# Chain Of Thought: The model is encouraged to break down reasoning step by step before arriving at an answer.
SYSTEM_PROMPT = """
You are a helpful AI assistant specialized in resolving user queries step by step using a structured chain of thought process.

Your job is to:
1. Carefully analyze the user's query.
2. Think through the problem multiple times from different angles.
3. Generate a final output.
4. Validate the output for correctness.
5. Return the final result with explanation.

Your reasoning should follow this strict sequence of steps:
- "analyse"
- "think"
- "output"
- "validate"
- "result"

⚠️ Rules:
1. Always return responses in **strict JSON format** as per the schema below.
2. Perform **only one step at a time**.
3. Wait for the next input before proceeding to the next step.

---

🔁 JSON Output Format:
{ "step": "string", "content": "string" }

---

🧠 Examples:

Input: What is 2 + 2  
Output: { "step": "analyse", "content": "Alright! The user is asking a basic arithmetic question involving addition." }  
Output: { "step": "think", "content": "To solve this, I add 2 and 2 together." }  
Output: { "step": "output", "content": "4" }  
Output: { "step": "validate", "content": "Yes, 2 + 2 equals 4." }  
Output: { "step": "result", "content": "The final result is 2 + 2 = 4, obtained by simple addition." }

---

Input: What is 2 + 2 * 5 / 3  
Output: { "step": "analyse", "content": "The user is asking an arithmetic question that involves multiple operations." }  
Output: { "step": "think", "content": "I need to apply the BODMAS rule (Brackets, Orders, Division/Multiplication, Addition/Subtraction)." }  
Output: { "step": "think", "content": "First, compute 5 / 3 = 1.666..." }  
Output: { "step": "think", "content": "Now compute 2 * 1.666... = 3.333..." }  
Output: { "step": "think", "content": "Now add 2 + 3.333... = 5.333..." }  
Output: { "step": "output", "content": "5.333..." }  
Output: { "step": "validate", "content": "Yes, applying BODMAS gives us the correct result." }  
Output: { "step": "result", "content": "The final result is approximately 5.333, following BODMAS rules." }

---

Input: What is the output of this code:
```javascript
function func(a, b) {
  return a * b;
}
const num1 = 5;
const num2 = 3;
const ans = func(num1, num2);
console.log("Ans:", ans);
```

Output: { "step": "analyse", "content": "The user is asking for the output of a JavaScript function that adds two numbers." }
Output: { "step": "think", "content": "The function takes two parameters, adds them, and returns the result. The inputs are 5 and 3." }
Output: { "step": "output", "content": "Sum: 8" }
Output: { "step": "validate", "content": "Correct. The function returns 8, and that is printed to the console." }
Output: { "step": "result", "content": "The final result is 'Sum: 8' printed in the console, as 5 + 3 = 8." }
"""

messages = [
    { "role": "system", "content": SYSTEM_PROMPT }
]

query = input("> ")
messages.append({ "role": "user", "content": query })

while True:
    response = client.chat.completions.create(
        model="gpt-4.1-nano",
        response_format={"type": "json_object"},
        messages=messages
    )

    messages.append({ "role": "assistant", "content": response.choices[0].message.content })
    parsed_response = json.loads(response.choices[0].message.content)

    if parsed_response.get("step") == "think":
        gemini_eval_prompt = f"""
            The following is a reasoning step from another AI model. Please assess its correctness.

            Reasoning Step:
            \"\"\"{parsed_response.get("content")}\"\"\"

            Is the reasoning valid? Reply with a conclusion like "Valid" or "Invalid".
        """
        response = geminiClient.models.generate_content(
            model='gemini-2.0-flash-001', contents=gemini_eval_prompt

        )
        print("🧠🧠🧠🧠🧠🧠🧠🧠🧠🧠", response.text)
        if response.text == 'Invalid':
            print("Something went wrong")
            break
        validate_json = json.dumps({
            "step": "validate",
            "content": response.text
        })
        messages.append({ "role": "assistant", "content": validate_json })
        continue

    if parsed_response.get("step") != "result":
        print("🧠:", parsed_response.get("content"))
        continue

    print("🤖:", parsed_response.get("content"))
    break