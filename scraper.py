"""
Deutsche Baseball Liga – EasyScore Stats Scraper
De API geeft een directe array terug van spelersrijen (geen wrapper).
Veldnamen: Player, PlayerID, Teamname, Team (ID), BA, OBP, SLG, OPS etc.
Stats komen al als strings met correcte baseball-notatie (.370, .921).
"""

import json
import os
import time
from datetime import datetime, timezone

import requests

# ── Configuratie ──────────────────────────────────────────────────────────────

API_BASE  = "https://api.easyscore.com/v2/stats"
YEAR      = 2026
LEAGUE_ID = 10147
DATA_DIR  = "data"

REQUEST_HEADERS = {
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

# ── Kolomdefinities per categorie ─────────────────────────────────────────────
# Gebaseerd op de werkelijke veldnamen uit de API response.
# format=False omdat EasyScore stats al als correcte strings levert (.370 etc.)

BATTING_HEADERS = [
    {"column": "Player",    "label": "Player",  "tooltip": "",                                              "format": False},
    {"column": "Teamname",  "label": "Team",    "tooltip": "",                                              "format": False},
    {"column": "G",         "label": "G",       "tooltip": "Games played",                                  "format": False},
    {"column": "PA",        "label": "PA",      "tooltip": "Plate Appearances",                             "format": False},
    {"column": "AB",        "label": "AB",      "tooltip": "At Bats",                                       "format": False},
    {"column": "R",         "label": "R",       "tooltip": "Runs scored",                                   "format": False},
    {"column": "H",         "label": "H",       "tooltip": "Hits",                                          "format": False},
    {"column": "2B",        "label": "2B",      "tooltip": "Doubles",                                       "format": False},
    {"column": "3B",        "label": "3B",      "tooltip": "Triples",                                       "format": False},
    {"column": "HR",        "label": "HR",      "tooltip": "Home Runs",                                     "format": False},
    {"column": "RBI",       "label": "RBI",     "tooltip": "Runs Batted In",                                "format": False},
    {"column": "SB",        "label": "SB",      "tooltip": "Stolen Bases",                                  "format": False},
    {"column": "CS",        "label": "CS",      "tooltip": "Caught Stealing",                               "format": False},
    {"column": "BB",        "label": "BB",      "tooltip": "Base on Balls (walks)",                         "format": False},
    {"column": "SO",        "label": "SO",      "tooltip": "Strikeouts",                                    "format": False},
    {"column": "HBP",       "label": "HBP",     "tooltip": "Hit by Pitch",                                  "format": False},
    {"column": "SF",        "label": "SF",      "tooltip": "Sacrifice Flies",                               "format": False},
    {"column": "BA",        "label": "AVG",     "tooltip": "Batting Average",                               "format": False},
    {"column": "OBP",       "label": "OBP",     "tooltip": "On Base Percentage",                            "format": False},
    {"column": "SLG",       "label": "SLG",     "tooltip": "Slugging Percentage",                           "format": False},
    {"column": "OPS",       "label": "OPS",     "tooltip": "On Base Plus Slugging",                         "format": False},
    {"column": "ISO",       "label": "ISO",     "tooltip": "Isolated Power (SLG - AVG)",                    "format": False},
    {"column": "BABIP",     "label": "BABIP",   "tooltip": "Batting Average on Balls in Play",              "format": False},
    {"column": "wOBA",      "label": "wOBA",    "tooltip": "Weighted On Base Average",                      "format": False},
    {"column": "TB",        "label": "TB",      "tooltip": "Total Bases",                                   "format": False},
    {"column": "XBH",       "label": "XBH",     "tooltip": "Extra Base Hits",                               "format": False},
]

PITCHING_HEADERS = [
    {"column": "Player",    "label": "Player",  "tooltip": "",                                              "format": False},
    {"column": "Teamname",  "label": "Team",    "tooltip": "",                                              "format": False},
    {"column": "G",         "label": "G",       "tooltip": "Games pitched",                                 "format": False},
    {"column": "GS",        "label": "GS",      "tooltip": "Games Started",                                 "format": False},
    {"column": "W",         "label": "W",       "tooltip": "Wins",                                          "format": False},
    {"column": "L",         "label": "L",       "tooltip": "Losses",                                        "format": False},
    {"column": "SV",        "label": "SV",      "tooltip": "Saves",                                         "format": False},
    {"column": "IP",        "label": "IP",      "tooltip": "Innings Pitched",                               "format": False},
    {"column": "H",         "label": "H",       "tooltip": "Hits allowed",                                  "format": False},
    {"column": "R",         "label": "R",       "tooltip": "Runs allowed",                                  "format": False},
    {"column": "ER",        "label": "ER",      "tooltip": "Earned Runs",                                   "format": False},
    {"column": "BB",        "label": "BB",      "tooltip": "Walks allowed",                                 "format": False},
    {"column": "SO",        "label": "SO",      "tooltip": "Strikeouts",                                    "format": False},
    {"column": "HR",        "label": "HR",      "tooltip": "Home Runs allowed",                             "format": False},
    {"column": "HBP",       "label": "HBP",     "tooltip": "Hit Batters",                                   "format": False},
    {"column": "ERA",       "label": "ERA",     "tooltip": "Earned Run Average",                            "format": False},
    {"column": "WHIP",      "label": "WHIP",    "tooltip": "Walks + Hits per Inning Pitched",               "format": False},
    {"column": "BAA",       "label": "BAA",     "tooltip": "Batting Average Against",                       "format": False},
    {"column": "SO9",       "label": "K/9",     "tooltip": "Strikeouts per 9 innings",                      "format": False},
    {"column": "BB9",       "label": "BB/9",    "tooltip": "Walks per 9 innings",                           "format": False},
    {"column": "HR9",       "label": "HR/9",    "tooltip": "Home Runs per 9 innings",                       "format": False},
    {"column": "KOBB",      "label": "K/BB",    "tooltip": "Strikeout to Walk ratio",                       "format": False},
]

FIELDING_HEADERS = [
    {"column": "Player",    "label": "Player",  "tooltip": "",                                              "format": False},
    {"column": "Teamname",  "label": "Team",    "tooltip": "",                                              "format": False},
    {"column": "Pos",       "label": "Pos",     "tooltip": "Position",                                      "format": False},
    {"column": "G",         "label": "G",       "tooltip": "Games played",                                  "format": False},
    {"column": "TC",        "label": "TC",      "tooltip": "Total Chances",                                  "format": False},
    {"column": "PO",        "label": "PO",      "tooltip": "Putouts",                                       "format": False},
    {"column": "A",         "label": "A",       "tooltip": "Assists",                                       "format": False},
    {"column": "E",         "label": "E",       "tooltip": "Errors",                                        "format": False},
    {"column": "DP",        "label": "DP",      "tooltip": "Double Plays",                                  "format": False},
    {"column": "FPCT",      "label": "FPCT",    "tooltip": "Fielding Percentage",                           "format": False},
]

HEADERS_MAP = {
    "batting":  BATTING_HEADERS,
    "pitching": PITCHING_HEADERS,
    "fielding": FIELDING_HEADERS,
}

os.makedirs(DATA_DIR, exist_ok=True)


# ── Hulpfuncties ──────────────────────────────────────────────────────────────

def fetch(params: dict) -> list | None:
    """Doe een GET-verzoek met retry. Geeft directe array terug."""
    for attempt in range(3):
        try:
            r = requests.get(API_BASE, params=params, headers=REQUEST_HEADERS, timeout=20)
            if r.status_code == 200:
                data = r.json()
                # API geeft directe array terug
                if isinstance(data, list):
                    return data
                # Of soms toch gewrapped
                if isinstance(data, dict):
                    return data.get("data") or data.get("players") or data.get("rows") or []
            print(f"  ⚠ HTTP {r.status_code}: {r.text[:200]}")
        except Exception as e:
            print(f"  ⚠ Poging {attempt + 1} mislukt: {e}")
        time.sleep(2 ** attempt)
    return None


def base_params(cat: str, round_: int = 0) -> dict:
    return {
        "yr":                YEAR,
        "leagueID":          LEAGUE_ID,
        "round":             round_,
        "cat":               cat,
        "split":             "",
        "nameDisplay":       0,
        "subCategory":       "",
        "playerID":          0,
        "gameID":            0,
        "byID":              0,
        "limit":             0,
        "affectedTable":     "",
        "numOfLeaders":      0,
        "selectedGameStats": 0,
        "hitChart":          0,
        "gameLeaders":       0,
        "parkFactors":       0,
    }


def normalise(rows: list, cat_key: str) -> dict:
    """
    Verwerk de ruwe API-array naar ons standaardformaat.

    Wat we weten uit de API:
    - Directe array van dicts
    - Naam: Player (bijv. "Goebel, Ch. COC")
    - Team: Teamname (bijv. "Cologne Cardinals"), Team = team ID (integer)
    - PlayerID: integer
    - Stats: al als strings met correcte baseball-notatie (".370", ".921")
      → GEEN /1000 nodig, format=False voor alle kolommen
    - Spelerlink: https://www.easyscore.com/players/{PlayerID}
    """
    if not rows:
        return {"headers": HEADERS_MAP[cat_key], "data": []}

    data = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        r = dict(row)

        # Spelerlink
        pid = r.get("PlayerID") or r.get("playerID")
        r["link"] = f"https://www.easyscore.com/players/{pid}" if pid else ""

        # Zorg dat Player en Teamname altijd aanwezig zijn
        r.setdefault("Player",   "")
        r.setdefault("Teamname", "")

        data.append(r)

    print(f"     → {len(data)} spelers verwerkt")
    return {"headers": HEADERS_MAP[cat_key], "data": data}


# ── Scrape functies ───────────────────────────────────────────────────────────

def scrape_section(cat_key: str, round_: int = 0) -> dict:
    cat_val = CATEGORIES[cat_key]
    print(f"  ↳ {cat_key} (cat={cat_val}, round={round_})…")
    rows = fetch(base_params(cat_val, round_))
    if rows is None:
        print(f"  ⚠ Geen data ontvangen voor {cat_key}")
        return {"headers": HEADERS_MAP[cat_key], "data": []}
    return normalise(rows, cat_key)


def scrape_rounds() -> list:
    """Haal beschikbare rondes op."""
    try:
        r = requests.get(
            "https://api.easyscore.com/v2/rounds",
            params={
                "uid": "", "isAdmin": 0, "hasAccessToLeagues": "",
                "id": 0, "lg": LEAGUE_ID, "yr": YEAR, "byLeague": 1,
            },
            headers=REQUEST_HEADERS,
            timeout=15,
        )
        if r.status_code == 200:
            data = r.json()
            rounds = data if isinstance(data, list) else data.get("rounds", [])
            print(f"  ✅ {len(rounds)} rondes gevonden")
            return rounds
        print(f"  ⚠ Rondes HTTP {r.status_code}")
    except Exception as e:
        print(f"  ⚠ Rondes ophalen mislukt: {e}")
    return []


def main():
    print(f"\nDBL EasyScore Scraper — {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}\n")

    # ── Alle stats (gehele seizoen, round=0) ──────────────────────────────────
    print("Scraping stats (alle rondes)…")
    all_stats = {}
    for cat_key in CATEGORIES:
        all_stats[cat_key] = scrape_section(cat_key, round_=0)
        time.sleep(0.5)

    with open(f"{DATA_DIR}/stats.json", "w", encoding="utf-8") as f:
        json.dump(all_stats, f, ensure_ascii=False, indent=2)
    print(f"  ✅ stats.json ({sum(len(v['data']) for v in all_stats.values())} rijen totaal)")

    # ── Rondes ophalen ────────────────────────────────────────────────────────
    print("\nRondes ophalen…")
    rounds = scrape_rounds()
    with open(f"{DATA_DIR}/rounds.json", "w", encoding="utf-8") as f:
        json.dump(rounds, f, ensure_ascii=False, indent=2)

    # ── Meta ──────────────────────────────────────────────────────────────────
    meta = {
        "last_updated":  datetime.now(timezone.utc).isoformat(),
        "source":        "https://api.easyscore.com/v2/stats",
        "league":        "Deutsche Baseball Liga",
        "league_id":     LEAGUE_ID,
        "year":          YEAR,
        "player_counts": {s: len(v["data"]) for s, v in all_stats.items()},
    }
    with open(f"{DATA_DIR}/meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"\nKlaar! Data opgeslagen in /{DATA_DIR}/\n")


if __name__ == "__main__":
    main()
