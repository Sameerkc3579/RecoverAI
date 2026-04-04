import urllib.request, json
try:
    req = urllib.request.Request('http://localhost:8000/api/generate-message', data=json.dumps({'prompt': 'test'}).encode(), headers={'Content-Type': 'application/json'}, method='POST')
    res = urllib.request.urlopen(req)
    print("STATUS", res.status)
    print(res.read().decode())
except urllib.error.HTTPError as e:
    print("HTTP ERROR", e.code)
    print(e.read().decode())
except Exception as e:
    print("ERROR", str(e))
