"""
DBL EasyScore Stats Scraper
Draait via GitHub Actions, slaat resultaten op in data/stats.json
"""

import json
import os
import time
from datetime import datetime, timezone

import requests

API_BASE  = "https://api.easyscore.com/v2/stats"
YEAR      = 2026
LEAGUE_ID = 10147
DATA      = "data"
os.makedirs(DATA, exist_ok=True)

API_HEADERS = {
    "Accept":          "*/*",
    "Content-Type":    "application/json",
    "Origin":          "https://www.easyscore.com",
    "Referer":         "https://www.easyscore.com/",
    "X-Api-Key":       os.environ.get("EASYSCORE_API_KEY", "urxiKaOhuH6keoQBwC74a2mi0nsgcAkJ1VBlkIK6"),
    "User-Agent":      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "nl-NL,nl;q=0.9,en-US;q=0.8,en;q=0.7",
}

CATEGORIES = {
    "batting":  "off",
    "pitching": "pit",
    "fielding": "fld",
}

BATTING_HEADERS = [
    {"column":"Player",  "label":"Player",  "tooltip":"",                             "format":False},
    {"column":"Teamname","label":"Team",    "tooltip":"",                             "format":False},
    {"column":"G",       "label":"G",       "tooltip":"Games played",                 "format":False},
    {"column":"PA",      "label":"PA",      "tooltip":"Plate Appearances",            "format":False},
    {"column":"AB",      "label":"AB",      "tooltip":"At Bats",                      "format":False},
    {"column":"R",       "label":"R",       "tooltip":"Runs scored",                  "format":False},
    {"column":"H",       "label":"H",       "tooltip":"Hits",                         "format":False},
    {"column":"RBI",     "label":"RBI",     "tooltip":"Runs Batted In",               "format":False},
    {"column":"HR",      "label":"HR",      "tooltip":"Home Runs",                    "format":False},
    {"column":"2B",      "label":"2B",      "tooltip":"Doubles",                      "format":False},
    {"column":"3B",      "label":"3B",      "tooltip":"Triples",                      "format":False},
    {"column":"TB",      "label":"TB",      "tooltip":"Total Bases",                  "format":False},
    {"column":"SB",      "label":"SB",      "tooltip":"Stolen Bases",                 "format":False},
    {"column":"BB",      "label":"BB",      "tooltip":"Walks",                        "format":False},
    {"column":"SO",      "label":"SO",      "tooltip":"Strikeouts",                   "format":False},
    {"column":"HBP",     "label":"HBP",     "tooltip":"Hit by Pitch",                 "format":False},
    {"column":"BA",      "label":"BA",      "tooltip":"Batting Average",              "format":False},
    {"column":"OBP",     "label":"OBP",     "tooltip":"On Base Percentage",           "format":False},
    {"column":"SLG",     "label":"SLG",     "tooltip":"Slugging Percentage",          "format":False},
    {"column":"OPS",     "label":"OPS",     "tooltip":"On Base + Slugging",           "format":False},
    {"column":"wOBA",    "label":"wOBA",    "tooltip":"Weighted On Base Average",     "format":False},
    {"column":"BABIP",   "label":"BABIP",   "tooltip":"Batting Avg on Balls in Play", "format":False},
    {"column":"ISO",     "label":"ISO",     "tooltip":"Isolated Power",               "format":False},
    {"column":"BBPct",   "label":"BB%",     "tooltip":"Walk Percentage",              "format":False},
    {"column":"SOPct",   "label":"SO%",     "tooltip":"Strikeout Percentage",         "format":False},
    {"column":"RC",      "label":"RC",      "tooltip":"Runs Created",                 "format":False},
    {"column":"RISP",    "label":"RISP",    "tooltip":"Runners in Scoring Position",  "format":False},
    {"column":"SBPct",   "label":"SB%",     "tooltip":"Stolen Base Percentage",       "format":False},
]

PITCHING_HEADERS = [
    {"column":"Player",   "label":"Player",  "tooltip":"",                              "format":False},
    {"column":"Teamname", "label":"Team",    "tooltip":"",                              "format":False},
    {"column":"G",        "label":"G",       "tooltip":"Games pitched",                 "format":False},
    {"column":"GS",       "label":"GS",      "tooltip":"Games started",                 "format":False},
    {"column":"W",        "label":"W",       "tooltip":"Wins",                          "format":False},
    {"column":"L",        "label":"L",       "tooltip":"Losses",                        "format":False},
    {"column":"SV",       "label":"SV",      "tooltip":"Saves",                         "format":False},
    {"column":"IP",       "label":"IP",      "tooltip":"Innings Pitched",               "format":False},
    {"column":"BF",       "label":"BF",      "tooltip":"Batters Faced",                 "format":False},
    {"column":"HA",       "label":"H",       "tooltip":"Hits Allowed",                  "format":False},
    {"column":"ER",       "label":"ER",      "tooltip":"Earned Runs",                   "format":False},
    {"column":"BBA",      "label":"BB",      "tooltip":"Walks Allowed",                 "format":False},
    {"column":"K",        "label":"K",       "tooltip":"Strikeouts",                    "format":False},
    {"column":"HRA",      "label":"HR",      "tooltip":"Home Runs Allowed",             "format":False},
    {"column":"HBPA",     "label":"HBP",     "tooltip":"Hit Batters",                   "format":False},
    {"column":"ERA",      "label":"ERA",     "tooltip":"Earned Run Average",            "format":False},
    {"column":"WHIP",     "label":"WHIP",    "tooltip":"Walks + Hits per Inning",       "format":False},
    {"column":"FIP",      "label":"FIP",     "tooltip":"Fielding Independent Pitching", "format":False},
    {"column":"K9",       "label":"K/9",     "tooltip":"Strikeouts per 9 innings",      "format":False},
    {"column":"BBA9",     "label":"BB/9",    "tooltip":"Walks per 9 innings",           "format":False},
    {"column":"HA9",      "label":"H/9",     "tooltip":"Hits per 9 innings",            "format":False},
    {"column":"KPct",     "label":"K%",      "tooltip":"Strikeout Percentage",          "format":False},
    {"column":"BBAPct",   "label":"BB%",     "tooltip":"Walk Percentage",               "format":False},
    {"column":"KBB",      "label":"K/BB",    "tooltip":"Strikeout to Walk Ratio",       "format":False},
    {"column":"OppAVG",   "label":"OppAVG",  "tooltip":"Opponent Batting Average",      "format":False},
    {"column":"OppOPS",   "label":"OppOPS",  "tooltip":"Opponent OPS",                  "format":False},
    {"column":"OppBABIP", "label":"OppBABIP","tooltip":"Opponent BABIP",                "format":False},
    {"column":"QS",       "label":"QS",      "tooltip":"Quality Starts",                "format":False},
    {"column":"WPct",     "label":"W%",      "tooltip":"Win Percentage",                "format":False},
]

FIELDING_HEADERS = [
    {"column":"Player",        "label":"Player","tooltip":"",                              "format":False},
    {"column":"Teamname",      "label":"Team",  "tooltip":"",                              "format":False},
    {"column":"G",             "label":"G",     "tooltip":"Games played",                  "format":False},
    {"column":"Chances",       "label":"TC",    "tooltip":"Total Chances",                 "format":False},
    {"column":"Putout",        "label":"PO",    "tooltip":"Putouts",                       "format":False},
    {"column":"Assist",        "label":"A",     "tooltip":"Assists",                       "format":False},
    {"column":"Error",         "label":"E",     "tooltip":"Errors",                        "format":False},
    {"column":"DP",            "label":"DP",    "tooltip":"Double Plays",                  "format":False},
    {"column":"FPct",          "label":"FPCT",  "tooltip":"Fielding Percentage",           "format":False},
    {"column":"RangeFactor",   "label":"RF",    "tooltip":"Range Factor",                  "format":False},
    {"column":"InningsPlayed", "label":"IP",    "tooltip":"Innings Played in Field",       "format":False},
    {"column":"GamesatC",      "label":"C",     "tooltip":"Games at Catcher",              "format":False},
    {"column":"Gamesat1B",     "label":"1B",    "tooltip":"Games at First Base",           "format":False},
    {"column":"Gamesat2B",     "label":"2B",    "tooltip":"Games at Second Base",          "format":False},
    {"column":"Gamesat3B",     "label":"3B",    "tooltip":"Games at Third Base",           "format":False},
    {"column":"GamesatSS",     "label":"SS",    "tooltip":"Games at Shortstop",            "format":False},
    {"column":"GamesatOF",     "label":"OF",    "tooltip":"Games in Outfield",             "format":False},
    {"column":"GamesatP",      "label":"P",     "tooltip":"Games at Pitcher",              "format":False},
    {"column":"PB",            "label":"PB",    "tooltip":"Passed Balls",                  "format":False},
    {"column":"SBAtt",         "label":"SBA",   "tooltip":"Stolen Base Attempts against",  "format":False},
    {"column":"CSMade",        "label":"CS",    "tooltip":"Caught Stealing",               "format":False},
    {"column":"CSPct",         "label":"CS%",   "tooltip":"Caught Stealing Percentage",    "format":False},
]

HEADERS_MAP = {
    "batting":  BATTING_HEADERS,
    "pitching": PITCHING_HEADERS,
    "fielding": FIELDING_HEADERS,
}


def fetch_stats(cat_val):
    url = (
        f"{API_BASE}?yr={YEAR}&leagueID={LEAGUE_ID}"
        f"&round=0&cat={cat_val}&subcat=ind&sortdir=desc&sortcol=&filter=all&_=1"
    )
    for attempt in range(3):
        try:
            r = requests.get(url, headers=API_HEADERS, timeout=30)
            if r.status_code == 200:
                data = r.json()
                rows = data if isinstance(data, list) else (data.get("data") or data.get("players") or [])
                for row in rows:
                    pid = row.get("PlayerID") or row.get("playerID")
                    row["link"] = f"https://www.easyscore.com/players/{pid}" if pid else ""
                return rows
            print(f"    Fout: HTTP {r.status_code} — {r.text[:200]}")
        except Exception as e:
            print(f"    Poging {attempt + 1} mislukt: {e}")
        time.sleep(2 ** attempt)
    return []


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
        print(f"    {len(rows)} rijen")
        time.sleep(0.5)

    with open(f"{DATA}/stats.json", "w", encoding="utf-8") as f:
        json.dump(all_stats, f, ensure_ascii=False, indent=2)

    total = sum(len(v["data"]) for v in all_stats.values())
    print(f"\n✅ stats.json geschreven ({total} totaal rijen)\n")


if __name__ == "__main__":
    main()
