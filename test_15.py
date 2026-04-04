from google import genai
import os
from dotenv import load_dotenv

load_dotenv()
try:
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    response = client.models.generate_content(
        model='gemini-1.5-flash',
        contents='hello',
    )
    print("SUCCESS:", response.text)
except Exception as e:
    print("FAILED:", str(e))
