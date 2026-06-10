import os
from google import genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.environ.get("GEMINI_API_KEY")

try:
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model='gemini-1.5-flash',
        contents='test',
    )
    print("SUCCESS WITH 1.5-FLASH:", response.text)
except Exception as e:
    print("ERROR WITH 1.5:", str(e))
