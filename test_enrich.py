import requests

# 1. login
login_res = requests.post(
    'http://127.0.0.1:8000/api/auth/login',
    data={'username': 'demo@recoverai.com', 'password': 'demo123456'}
)
token = login_res.json().get('access_token')
print("Token length:", len(token) if token else "No token")

# 2. auto-fill enrich
res = requests.post(
    'http://127.0.0.1:8000/api/enrich/',
    json={'url': 'https://example.com'},
    headers={'Authorization': f'Bearer {token}'}
)
print('Status:', res.status_code)
print('Output:', res.text)
