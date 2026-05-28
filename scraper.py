"""
Deutsche Baseball Liga – EasyScore Stats Scraper
Haalt batting, pitching en fielding stats op via de EasyScore API.
Slaat alles op als JSON in /data.
"""

import json
import os
import re
import time
from datetime import datetime, timezone

import requests

# ── Configuratie ──────────────────────────────────────────────────────────────

API_BASE  = "https://api.easyscore.com/v2/stats"
YEAR      = 2026
LEAGUE_ID = 10147
DATA_DIR  = "data"

HEADERS = {
    "Accept":          "*/*",
    "Content-Type":    "application/json",
    "Origin":          "https://www.easyscore.com",
    "Referer":         "https://www.easyscore.com/",
    "X-Api-Key":       "urxiKaOhuH6keoQBwC74a2mi0nsgcAkJ1VBlkIK6",
    "User-Agent":      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
    "Accept-Language": "nl-NL,nl;q=0.9,en-US;q=0.8,en;q=0.7",
}

# cat=off  → batting
# cat=pit  → pitching
# cat=fld  → fielding
CATEGORIES = {
    "batting":  "off",
    "pitching": "pit",
    "fielding": "fld",
}

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(f"{DATA_DIR}/teams", exist_ok=True)


# ── Hulpfuncties ──────────────────────────────────────────────────────────────

def fetch(params: dict) -> dict | None:
    """Doe een GET-verzoek met retry."""
    for attempt in range(3):
        try:
            r = requests.get(API_BASE, params=params, headers=HEADERS, timeout=20)
            if r.status_code == 200:
                return r.json()
            print(f"  ⚠ HTTP {r.status_code}: {r.text[:200]}")
        except Exception as e:
            print(f"  ⚠ Poging {attempt + 1} mislukt: {e}")
        time.sleep(2 ** attempt)
    return None


def base_params(cat: str, round_: int = 0) -> dict:
    return {
        "yr":                 YEAR,
        "leagueID":           LEAGUE_ID,
        "round":              round_,
        "cat":                cat,
        "split":              "",
        "nameDisplay":        0,
        "subCategory":        "",
        "playerID":           0,
        "gameID":             0,
        "byID":               0,
        "limit":              0,
        "affectedTable":      "",
        "numOfLeaders":       0,
        "selectedGameStats":  0,
        "hitChart":           0,
        "gameLeaders":        0,
        "parkFactors":        0,
    }


def normalise(raw: dict) -> dict:
    """
    EasyScore geeft een object terug met:
      - raw["headers"]  → lijst van kolomdefinities
      - raw["data"]     → lijst van spelersrijen

    We normaliseren dit naar hetzelfde formaat als de Hoofdklasse scraper:
      { "headers": [...], "data": [...] }

    Baseball-percentages (AVG, OBP, SLG, ERA, FLDP …) komen als float
    of als integer × 1000. We detecteren het type en bewaren de waarde
    ongewijzigd — de display-laag doet de formatting.
    """
    if not raw:
        return {"headers": [], "data": []}

    # EasyScore kan de data op twee manieren aanleveren
    headers_raw = raw.get("headers") or raw.get("columns") or []
    rows_raw    = raw.get("data")    or raw.get("rows")    or raw.get("players") or []

    # Headers normaliseren
    headers = []
    for h in headers_raw:
        if isinstance(h, dict):
            headers.append({
                "column":  h.get("key")     or h.get("id")    or h.get("field") or "",
                "label":   h.get("label")   or h.get("title") or h.get("name")  or "",
                "tooltip": h.get("tooltip") or h.get("description") or "",
                "format":  h.get("format")  or h.get("type") == "pct",
            })
        elif isinstance(h, str):
            headers.append({"column": h, "label": h, "tooltip": "", "format": False})

    # Rijen normaliseren — speler-link toevoegen
    data = []
    for row in rows_raw:
        if isinstance(row, dict):
            r = dict(row)
            # Spelerlink opbouwen
            pid = r.get("playerID") or r.get("player_id") or r.get("id")
            r["link"] = f"https://www.easyscore.com/players/{pid}" if pid else ""
            # teamcode afleiden uit teamnaam indien afwezig
            if not r.get("teamcode") and r.get("team"):
                r["teamcode"] = r["team"]
            data.append(r)

    return {"headers": headers, "data": data}


# ── Scrape functies ───────────────────────────────────────────────────────────

def scrape_section(cat_key: str, cat_val: str, round_: int = 0) -> dict:
    print(f"  ↳ {cat_key} (round={round_})…")
    params = base_params(cat_val, round_)
    raw    = fetch(params)
    result = normalise(raw)
    print(f"     {len(result['data'])} spelers, {len(result['headers'])} kolommen")
    return result


def scrape_rounds() -> list:
    """Haal beschikbare rondes op."""
    try:
        r = requests.get(
            "https://api.easyscore.com/v2/rounds",
            params={
                "uid": "", "isAdmin": 0, "hasAccessToLeagues": "",
                "id": 0, "lg": LEAGUE_ID, "yr": YEAR, "byLeague": 1,
            },
            headers=HEADERS,
            timeout=15,
        )
        if r.status_code == 200:
            data = r.json()
            rounds = data if isinstance(data, list) else data.get("rounds", [])
            print(f"  ✅ {len(rounds)} rondes gevonden")
            return rounds
    except Exception as e:
        print(f"  ⚠ Rondes ophalen mislukt: {e}")
    return []


def main():
    print(f"\n🚀 DBL EasyScore Scraper — {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}\n")

    # ── Alle stats (alle rondes samen) ────────────────────────────────────────
    print("📊 Scraping algemene stats (alle rondes)…")
    all_stats = {}
    for cat_key, cat_val in CATEGORIES.items():
        all_stats[cat_key] = scrape_section(cat_key, cat_val)
        time.sleep(0.5)

    with open(f"{DATA_DIR}/stats.json", "w", encoding="utf-8") as f:
        json.dump(all_stats, f, ensure_ascii=False, indent=2)
    print(f"  ✅ stats.json")

    # ── Rondes ophalen ────────────────────────────────────────────────────────
    print("\n📋 Rondes ophalen…")
    rounds = scrape_rounds()

    with open(f"{DATA_DIR}/rounds.json", "w", encoding="utf-8") as f:
        json.dump(rounds, f, ensure_ascii=False, indent=2)

    # ── Stats per ronde ───────────────────────────────────────────────────────
    if rounds:
        print("\n🔄 Scraping per ronde…")
        rounds_data = {}
        for ronde in rounds[:10]:  # max 10 rondes
            rid   = ronde.get("id") or ronde.get("roundID") or ronde.get("round")
            rnaam = ronde.get("name") or ronde.get("label") or str(rid)
            if not rid:
                continue
            print(f"  Ronde: {rnaam} (id={rid})")
            rounds_data[str(rid)] = {
                "label":    rnaam,
                "batting":  scrape_section("batting",  "off", rid),
                "pitching": scrape_section("pitching", "pit", rid),
                "fielding": scrape_section("fielding", "fld", rid),
            }
            time.sleep(0.8)

        with open(f"{DATA_DIR}/rounds_stats.json", "w", encoding="utf-8") as f:
            json.dump(rounds_data, f, ensure_ascii=False, indent=2)
        print(f"  ✅ rounds_stats.json")

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

    print(f"\n✅ Klaar! Data opgeslagen in /{DATA_DIR}/\n")


if __name__ == "__main__":
    main()
