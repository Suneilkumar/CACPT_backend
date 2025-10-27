import requests, json, sys

with open("questions.json", "r", encoding="utf-8") as f:
    data = json.load(f)

url = "http://127.0.0.1:8000/api/questions/bulk"   # make sure this matches your running server
try:
    resp = requests.post(url, json=data, timeout=60)
except requests.RequestException as e:
    print("Request failed:", e)
    sys.exit(1)

print("STATUS:", resp.status_code)
print("HEADERS:", resp.headers)
print("TEXT (first 1000 chars):\n", resp.text[:1000])
# try to print JSON nicely if present
try:
    print("JSON:", resp.json())
except Exception as e:
    print("Failed to decode JSON response:", e)
