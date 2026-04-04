from curl_cffi import requests
session = requests.Session(impersonate="chrome110")
response = session.get("https://chat.openai.com/")
print("Status:", response.status_code)
print("Content length:", len(response.text))
