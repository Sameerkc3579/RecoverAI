import urllib.request, json
req = urllib.request.Request('https://api.github.com/users/Sameerkc3579/repos?sort=updated', headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req) as response:
        repos = json.loads(response.read().decode())
        for r in repos:
            print(f"- {r['name']}: {r.get('description') or 'No description'}")
except Exception as e:
    print(e)
