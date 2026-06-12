import httpx, json, sys

r = httpx.post('http://127.0.0.1:8080/api/auth/login',
    json={"username": "admin", "email": "admin@test.com", "password": "admin123"}, timeout=10)
if r.status_code != 200:
    print(f"Login failed: {r.status_code}")
    sys.exit(1)
tok = r.json()["access_token"]

r2 = httpx.get('http://127.0.0.1:8080/api/articles',
    headers={"Authorization": f"Bearer {tok}"}, timeout=10)
data = r2.json()

articles = data.get('articles', [])
print(f"Total: {data.get('total', len(articles))}")
for a in articles:
    c = a.get('content', '') or ''
    print(f"  {a.get('id','')[:30]:30s} | {len(c):>5} chars | {a.get('title','')[:40]:40s} | {a.get('source','')[:20]}")
