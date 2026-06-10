import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

# 1. login
username = os.getenv("TEST_USERNAME", "admin@example.com")
password = os.getenv("TEST_PASSWORD", "password123")

login_res = requests.post(
    'http://127.0.0.1:8000/api/auth/login',
    data={'username': username, 'password': password}
)
token = login_res.json().get('access_token')

if not token:
    print("❌ Failed to get access token. Invalid credentials or server is down.")
    sys.exit(1)

print("Token length:", len(token))

# 2. auto-fill enrich
res = requests.post(
    'http://127.0.0.1:8000/api/enrich/',
    json={'url': 'https://example.com'},
    headers={'Authorization': f'Bearer {token}'}
)
print('Status:', res.status_code)
print('Output:', res.text)
