"""
DBL API Test — draai dit lokaal en plak de output
Vereisten: pip install requests
"""

import json
import requests

API_BASE = "https://api.easyscore.com/v2/stats"

HEADERS = {
    "Accept":          "*/*",
    "Content-Type":    "application/json",
    "Origin":          "https://www.easyscore.com",
    "Referer":         "https://www.easyscore.com/",
    "X-Api-Key":       "urxiKaOhuH6keoQBwC74a2mi0nsgcAkJ1VBlkIK6",
    "User-Agent":      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
}

PARAMS = {
    "yr": 2026, "leagueID": 10147, "round": 0,
    "cat": "off", "split": "", "nameDisplay": 0,
    "subCategory": "", "playerID": 0, "gameID": 0,
    "byID": 0, "limit": 0, "affectedTable": "",
    "numOfLeaders": 0, "selectedGameStats": 0,
    "hitChart": 0, "gameLeaders": 0, "parkFactors": 0,
}

print("Verzoek versturen...")
r = requests.get(API_BASE, params=PARAMS, headers=HEADERS, timeout=20)

print(f"Status: {r.status_code}")
print(f"Bytes:  {len(r.content)}")
print(f"Content-Type: {r.headers.get('Content-Type')}")
print()

data = r.json()
print(f"Type response: {type(data).__name__}")

if isinstance(data, list):
    print(f"Aantal rijen: {len(data)}")
    if data:
        print(f"\nEerste rij (alle keys):")
        print(json.dumps(data[0], indent=2, ensure_ascii=False)[:2000])
elif isinstance(data, dict):
    print(f"Keys: {list(data.keys())}")
    for k, v in data.items():
        if isinstance(v, list):
            print(f"  {k}: {len(v)} items")
        else:
            print(f"  {k}: {v}")
