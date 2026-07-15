import os
from dotenv import load_dotenv
from groq import Groq

# Load the API key from .env
load_dotenv()

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

response = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[
        {"role": "user", "content": "Say hello and confirm you're working, in one sentence."}
    ]
)

print(response.choices[0].message.content)