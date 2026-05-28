"""
DBL EasyScore Scraper — lokaal draaien
=======================================
Vereisten:
    pip install requests

Gebruik:
    python dbl-scraper-lokaal.py

Het script haalt batting/pitching/fielding op en pusht JSON naar GitHub.
Stel eenmalig GITHUB_TOKEN en GITHUB_REPO in (zie CONFIG hieronder).

Automatisch draaien (Mac/Linux):
    Voeg toe aan crontab:  0 7,13,19 * * * cd /pad/naar/script && python dbl-scraper-lokaal.py

Automatisch draaien (Windows):
    Task Scheduler → dagelijks python dbl-scraper-lokaal.py uitvoeren
"""

import json
import base64
import os
import time
from datetime import datetime, timezone

import requests

# ── CONFIG — pas dit aan ──────────────────────────────────────────────────────

GITHUB_TOKEN = "ghp_JOUW_TOKEN_HIER"   # GitHub → Settings → Developer Settings → Personal access tokens
GITHUB_REPO  = "finnkops-code/DBL-resultaten"  # gebruikersnaam/reponaam
GITHUB_BRANCH = "main"

# ── EasyScore API ─────────────────────────────────────────────────────────────

API_BASE  = "https://api.easyscore.com/v2/stats"
YEAR      = 2026
LEAGUE_ID = 10147

API_HEADERS = {
    "Accept":          "*/*",
    "Content-Type":    "application/json",
    "Origin":          "https://www.easyscore.com",
    "Referer":         "https://www.easyscore.com/",
    "X-Api-Key":       "urxiKaOhuH6keoQBwC74a2mi0nsgcAkJ1VBlkIK6",
    "User-Agent":      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
    "Accept-Language": "nl-NL,nl;q=0.9,en-US;q=0.8,en;q=0.7",
}

CATEGORIES = {
    "batting":  "off",
    "pitching": "pit",
    "fielding": "fld",
}

BATTING_HEADERS = [
    {"column":"Player","label":"Player","tooltip":"","format":False},
    {"column":"Teamname","label":"Team","tooltip":"","format":False},
    {"column":"G","label":"G","tooltip":"Games played","format":False},
    {"column":"PA","label":"PA","tooltip":"Plate Appearances","format":False},
    {"column":"AB","label":"AB","tooltip":"At Bats","format":False},
    {"column":"R","label":"R","tooltip":"Runs","format":False},
    {"column":"H","label":"H","tooltip":"Hits","format":False},
    {"column":"2B","label":"2B","tooltip":"Doubles","format":False},
    {"column":"3B","label":"3B","tooltip":"Triples","format":False},
    {"column":"HR","label":"HR","tooltip":"Home Runs","format":False},
    {"column":"RBI","label":"RBI","tooltip":"Runs Batted In","format":False},
    {"column":"SB","label":"SB","tooltip":"Stolen Bases","format":False},
    {"column":"BB","label":"BB","tooltip":"Walks","format":False},
    {"column":"SO","label":"SO","tooltip":"Strikeouts","format":False},
    {"column":"HBP","label":"HBP","tooltip":"Hit by Pitch","format":False},
    {"column":"BA","label":"AVG","tooltip":"Batting Average","format":False},
    {"column":"OBP","label":"OBP","tooltip":"On Base Percentage","format":False},
    {"column":"SLG","label":"SLG","tooltip":"Slugging Percentage","format":False},
    {"column":"OPS","label":"OPS","tooltip":"On Base Plus Slugging","format":False},
    {"column":"ISO","label":"ISO","tooltip":"Isolated Power","format":False},
    {"column":"BABIP","label":"BABIP","tooltip":"Batting Avg on Balls in Play","format":False},
    {"column":"wOBA","label":"wOBA","tooltip":"Weighted On Base Average","format":False},
    {"column":"TB","label":"TB","tooltip":"Total Bases","format":False},
]

PITCHING_HEADERS = [
    {"column":"Player","label":"Player","tooltip":"","format":False},
    {"column":"Teamname","label":"Team","tooltip":"","format":False},
    {"column":"G","label":"G","tooltip":"Games","format":False},
    {"column":"GS","label":"GS","tooltip":"Games Started","format":False},
    {"column":"W","label":"W","tooltip":"Wins","format":False},
    {"column":"L","label":"L","tooltip":"Losses","format":False},
    {"column":"SV","label":"SV","tooltip":"Saves","format":False},
    {"column":"IP","label":"IP","tooltip":"Innings Pitched","format":False},
    {"column":"H","label":"H","tooltip":"Hits allowed","format":False},
    {"column":"R","label":"R","tooltip":"Runs allowed","format":False},
    {"column":"ER","label":"ER","tooltip":"Earned Runs","format":False},
    {"column":"BB","label":"BB","tooltip":"Walks","format":False},
    {"column":"SO","label":"SO","tooltip":"Strikeouts","format":False},
    {"column":"HR","label":"HR","tooltip":"HR allowed","format":False},
    {"column":"ERA","label":"ERA","tooltip":"Earned Run Average","format":False},
    {"column":"WHIP","label":"WHIP","tooltip":"Walks + Hits per IP","format":False},
    {"column":"BAA","label":"BAA","tooltip":"Batting Average Against","format":False},
    {"column":"SO9","label":"K/9","tooltip":"Strikeouts per 9 innings","format":False},
    {"column":"BB9","label":"BB/9","tooltip":"Walks per 9 innings","format":False},
    {"column":"KOBB","label":"K/BB","tooltip":"K/BB ratio","format":False},
]

FIELDING_HEADERS = [
    {"column":"Player","label":"Player","tooltip":"","format":False},
    {"column":"Teamname","label":"Team","tooltip":"","format":False},
    {"column":"Pos","label":"Pos","tooltip":"Position","format":False},
    {"column":"G","label":"G","tooltip":"Games","format":False},
    {"column":"TC","label":"TC","tooltip":"Total Chances","format":False},
    {"column":"PO","label":"PO","tooltip":"Putouts","format":False},
    {"column":"A","label":"A","tooltip":"Assists","format":False},
    {"column":"E","label":"E","tooltip":"Errors","format":False},
    {"column":"DP","label":"DP","tooltip":"Double Plays","format":False},
    {"column":"FPCT","label":"FPCT","tooltip":"Fielding Percentage","format":False},
]

HEADERS_MAP = {
    "batting":  BATTING_HEADERS,
    "pitching": PITCHING_HEADERS,
    "fielding": FIELDING_HEADERS,
}


# ── EasyScore ophalen ─────────────────────────────────────────────────────────

def fetch_stats(cat_val: str) -> list:
    params = {
        "yr": YEAR, "leagueID": LEAGUE_ID, "round": 0,
        "cat": cat_val, "split": "", "nameDisplay": 0,
        "subCategory": "", "playerID": 0, "gameID": 0,
        "byID": 0, "limit": 0, "affectedTable": "",
        "numOfLeaders": 0, "selectedGameStats": 0,
        "hitChart": 0, "gameLeaders": 0, "parkFactors": 0,
    }
    for attempt in range(3):
        try:
            r = requests.get(API_BASE, params=params, headers=API_HEADERS, timeout=20)
            print(f"    HTTP {r.status_code} | {len(r.content)} bytes")
            if r.status_code == 200:
                data = r.json()
                rows = data if isinstance(data, list) else (data.get("data") or data.get("players") or [])
                # Spelerlink toevoegen
                for row in rows:
                    pid = row.get("PlayerID") or row.get("playerID")
                    row["link"] = f"https://www.easyscore.com/players/{pid}" if pid else ""
                return rows
            print(f"    Fout: {r.text[:200]}")
        except Exception as e:
            print(f"    Poging {attempt+1} mislukt: {e}")
        time.sleep(2 ** attempt)
    return []


# ── GitHub upload ─────────────────────────────────────────────────────────────

def github_upload(path: str, content: str, message: str):
    """Maak of update een bestand in GitHub via de API."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }

    # Huidige SHA ophalen (nodig voor update)
    sha = None
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        sha = r.json().get("sha")

    payload = {
        "message": message,
        "content": base64.b64encode(content.encode()).decode(),
        "branch":  GITHUB_BRANCH,
    }
    if sha:
        payload["sha"] = sha

    r = requests.put(url, headers=headers, json=payload)
    if r.status_code in (200, 201):
        print(f"    ✅ GitHub: {path}")
    else:
        print(f"    ⚠ GitHub fout {r.status_code}: {r.text[:200]}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"\nDBL Scraper — {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}\n")

    all_stats = {}
    for cat_key, cat_val in CATEGORIES.items():
        print(f"  {cat_key} ({cat_val})…")
        rows = fetch_stats(cat_val)
        all_stats[cat_key] = {
            "headers": HEADERS_MAP[cat_key],
            "data":    rows,
        }
        print(f"    {len(rows)} spelers")
        time.sleep(0.5)

    meta = {
        "last_updated":  datetime.now(timezone.utc).isoformat(),
        "source":        "https://api.easyscore.com/v2/stats",
        "league":        "Deutsche Baseball Liga",
        "league_id":     LEAGUE_ID,
        "year":          YEAR,
        "player_counts": {s: len(v["data"]) for s, v in all_stats.items()},
    }

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    print("\nUploaden naar GitHub…")
    github_upload(
        "data/stats.json",
        json.dumps(all_stats, ensure_ascii=False, indent=2),
        f"📊 DBL stats update {ts}",
    )
    github_upload(
        "data/meta.json",
        json.dumps(meta, ensure_ascii=False, indent=2),
        f"📊 DBL meta update {ts}",
    )

    print(f"\nKlaar! {sum(len(v['data']) for v in all_stats.values())} spelers opgeslagen.\n")


if __name__ == "__main__":
    main()
