"""
DBL Statistics Scraper
========================
Scrapes player statistics from baseball.de / easyscore.com using Playwright
and writes the output files expected by the WordPress shortcode:

    data/stats.json   — batting, pitching, fielding data + headers
    data/splits.json  — splits per team (currently empty, reserved)
    data/meta.json    — last_updated timestamp + source info

Install:
    pip install playwright
    playwright install chromium

Run:
    python scraper.py
    python scraper.py --year 2025
"""

import asyncio
import json
import argparse
import sys
import re
from pathlib import Path
from datetime import datetime, timezone

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("❌  playwright not installed. Run: pip install playwright && playwright install chromium")
    sys.exit(1)


# ── League config ─────────────────────────────────────────────────────────────

LEAGUE_ID  = 10147   # Deutsche Baseball Liga on EasyScore
CATEGORIES = [
    ("off", "batting"),
    ("pit", "pitching"),
    ("fld", "fielding"),
]

# ── Column definitions ────────────────────────────────────────────────────────
# Maps EasyScore column keys → label + optional tooltip + format flag
# format=True means the value is stored as integer * 1000 (e.g. AVG 312 = .312)

BATTING_HEADERS = [
    {"column": "Player",   "label": "Speler",  "tooltip": "Spelernaam"},
    {"column": "Teamname", "label": "Team",    "tooltip": "Teamnaam"},
    {"column": "G",        "label": "G",       "tooltip": "Gespeelde wedstrijden"},
    {"column": "PA",       "label": "PA",      "tooltip": "Plate appearances"},
    {"column": "AB",       "label": "AB",      "tooltip": "At bats"},
    {"column": "R",        "label": "R",       "tooltip": "Runs"},
    {"column": "H",        "label": "H",       "tooltip": "Hits"},
    {"column": "2B",       "label": "2B",      "tooltip": "Doubles"},
    {"column": "3B",       "label": "3B",      "tooltip": "Triples"},
    {"column": "HR",       "label": "HR",      "tooltip": "Home runs"},
    {"column": "RBI",      "label": "RBI",     "tooltip": "Runs batted in"},
    {"column": "BB",       "label": "BB",      "tooltip": "Walks"},
    {"column": "SO",       "label": "SO",      "tooltip": "Strikeouts"},
    {"column": "SB",       "label": "SB",      "tooltip": "Stolen bases"},
    {"column": "AVG",      "label": "AVG",     "tooltip": "Batting average", "format": True},
    {"column": "OBP",      "label": "OBP",     "tooltip": "On-base percentage", "format": True},
    {"column": "SLG",      "label": "SLG",     "tooltip": "Slugging percentage", "format": True},
    {"column": "OPS",      "label": "OPS",     "tooltip": "On-base + slugging", "format": True},
]

PITCHING_HEADERS = [
    {"column": "Player",   "label": "Speler",  "tooltip": "Spelernaam"},
    {"column": "Teamname", "label": "Team",    "tooltip": "Teamnaam"},
    {"column": "G",        "label": "G",       "tooltip": "Wedstrijden"},
    {"column": "GS",       "label": "GS",      "tooltip": "Starts"},
    {"column": "W",        "label": "W",       "tooltip": "Wins"},
    {"column": "L",        "label": "L",       "tooltip": "Losses"},
    {"column": "SV",       "label": "SV",      "tooltip": "Saves"},
    {"column": "IP",       "label": "IP",      "tooltip": "Innings pitched"},
    {"column": "H",        "label": "H",       "tooltip": "Hits toegestaan"},
    {"column": "R",        "label": "R",       "tooltip": "Runs toegestaan"},
    {"column": "ER",       "label": "ER",      "tooltip": "Earned runs"},
    {"column": "BB",       "label": "BB",      "tooltip": "Walks"},
    {"column": "SO",       "label": "SO",      "tooltip": "Strikeouts"},
    {"column": "ERA",      "label": "ERA",     "tooltip": "Earned run average", "format": True},
    {"column": "WHIP",     "label": "WHIP",    "tooltip": "Walks + hits per inning", "format": True},
]

FIELDING_HEADERS = [
    {"column": "Player",   "label": "Speler",  "tooltip": "Spelernaam"},
    {"column": "Teamname", "label": "Team",    "tooltip": "Teamnaam"},
    {"column": "POS",      "label": "Pos",     "tooltip": "Positie"},
    {"column": "G",        "label": "G",       "tooltip": "Wedstrijden"},
    {"column": "INN",      "label": "INN",     "tooltip": "Innings gespeeld"},
    {"column": "PO",       "label": "PO",      "tooltip": "Putouts"},
    {"column": "A",        "label": "A",       "tooltip": "Assists"},
    {"column": "E",        "label": "E",       "tooltip": "Errors"},
    {"column": "DP",       "label": "DP",      "tooltip": "Double plays"},
    {"column": "FPCT",     "label": "FLD%",    "tooltip": "Fielding percentage", "format": True},
]

HEADERS_MAP = {
    "batting":  BATTING_HEADERS,
    "pitching": PITCHING_HEADERS,
    "fielding": FIELDING_HEADERS,
}


# ── Scraping ──────────────────────────────────────────────────────────────────

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def is_stats_row(row: dict) -> bool:
    """Geeft True als dit een echte spelerrij is (geen landen/lookup data)."""
    # Landentabel heeft 'Country' en 'Code' sleutels
    if "Country" in row or "Code" in row:
        return False
    # Echte stats rijen hebben baseball-gerelateerde velden
    baseball_fields = {"G", "AB", "PA", "H", "R", "HR", "RBI", "BB", "SO",
                       "ERA", "IP", "W", "L", "SV", "PO", "A", "E",
                       "Player", "Teamname", "name", "teamcode"}
    return bool(baseball_fields & set(row.keys()))


async def scrape_category(page, year: int, cat_code: str, cat_name: str) -> list:
    url = f"https://www.easyscore.com/stats/?y={year}&l={LEAGUE_ID}&r=0&cat={cat_code}"
    captured = []

    async def on_response(response):
        rurl = response.url
        # Sla lookup/config endpoints over
        skip_patterns = ["countries", "country", "lookup", "config", "i18n", "locale"]
        if any(p in rurl.lower() for p in skip_patterns):
            return
        if (
            "easyscore.com" in rurl
            and response.status == 200
            and "json" in response.headers.get("content-type", "")
        ):
            try:
                data = await response.json()
                if isinstance(data, (list, dict)):
                    captured.append({"url": rurl, "data": data})
                    log(f"    📡 JSON gevangen: {rurl}")
            except Exception:
                pass

    page.on("response", on_response)
    log(f"  🌐 Laden: {url}")
    await page.goto(url, wait_until="networkidle", timeout=60_000)
    await page.wait_for_timeout(5_000)

    # Klik eventuele sub-tabs aan
    try:
        for btn in await page.query_selector_all("button[data-cat], [role='tab'], .stats-tab"):
            try:
                await btn.click()
                await page.wait_for_timeout(1_200)
            except Exception:
                pass
    except Exception:
        pass

    page.remove_listener("response", on_response)

    if captured:
        rows = []
        for item in captured:
            d = item["data"]
            candidates = []
            if isinstance(d, list):
                candidates = d
            elif isinstance(d, dict):
                for key in ("players", "data", "stats", "rows", "results", "items"):
                    if key in d and isinstance(d[key], list):
                        candidates = d[key]
                        break
                else:
                    candidates = [d]
            # Filter: alleen echte stats rijen
            valid = [r for r in candidates if isinstance(r, dict) and is_stats_row(r)]
            if valid:
                log(f"    ✅ {len(valid)} stats-rijen gevonden in {item['url']}")
                rows.extend(valid)
            elif candidates:
                log(f"    ⏭️  {len(candidates)} rijen geskipped (geen baseball data) in {item['url']}")
        if rows:
            return rows

    # Fallback: HTML tabel
    log(f"  ⚠️  Geen JSON stats — HTML tabel proberen")
    return await extract_from_table(page)


async def extract_from_table(page) -> list:
    try:
        await page.wait_for_selector("table", timeout=10_000)
    except Exception:
        return []

    return await page.evaluate("""
        () => {
            const results = [];
            for (const table of document.querySelectorAll('table')) {
                const headers = [...table.querySelectorAll('thead th, thead td')]
                    .map(th => th.innerText.trim());
                if (!headers.length) continue;
                for (const row of table.querySelectorAll('tbody tr')) {
                    const cells = [...row.querySelectorAll('td')].map(td => td.innerText.trim());
                    if (!cells.length) continue;
                    const obj = {};
                    headers.forEach((h, i) => { obj[h || 'col' + i] = cells[i] ?? ''; });
                    results.push(obj);
                }
            }
            return results;
        }
    """)


def normalize_rows(raw_rows: list, cat_name: str) -> list:
    """
    Pass rows through as-is — the EasyScore API already provides
    Player, Teamname and all stat columns in the correct format.
    Only filter out non-player rows and strip internal fields.
    """
    normalized = []
    # Fields we don't need in the output
    strip_keys = {"name", "IO", "dtCreated", "Lic", "TopOrBot",
                  "LeagueID", "League", "SubCategory", "Round", "RoundName",
                  "Year", "TeamsGames", "MinPA", "MinIP", "MinINN"}

    for r in raw_rows:
        if not isinstance(r, dict):
            continue
        # Must have a player name
        if not r.get("Player"):
            continue
        row = {k: v for k, v in r.items() if k not in strip_keys}
        normalized.append(row)

    return normalized


# ── Main ──────────────────────────────────────────────────────────────────────

async def run(year: int, out_dir: str):
    log(f"🚀 DBL {year} scraper gestart")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    stats_result = {}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage",
                  "--disable-blink-features=AutomationControlled"],
        )
        ctx = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
            locale="de-DE",
        )
        page = await ctx.new_page()

        for cat_code, cat_name in CATEGORIES:
            log(f"\n📊 {cat_name.capitalize()} (cat={cat_code})")
            try:
                raw   = await scrape_category(page, year, cat_code, cat_name)
                rows  = normalize_rows(raw, cat_name)
                hdrs  = HEADERS_MAP[cat_name]
                stats_result[cat_name] = {"headers": hdrs, "data": rows}
                log(f"  ✅ {len(rows)} rijen")
            except Exception as e:
                log(f"  ❌ Fout: {e}")
                stats_result[cat_name] = {"headers": HEADERS_MAP[cat_name], "data": []}

        await browser.close()

    now = datetime.now(timezone.utc).isoformat()

    # ── stats.json ────────────────────────────────────────────────────────────
    (out / "stats.json").write_text(
        json.dumps(stats_result, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # ── splits.json ───────────────────────────────────────────────────────────
    (out / "splits.json").write_text(
        json.dumps({}, indent=2), encoding="utf-8"
    )

    # ── meta.json ─────────────────────────────────────────────────────────────
    meta = {
        "last_updated": now,
        "year": year,
        "league_id": LEAGUE_ID,
        "source": f"https://www.baseball.de/saison/statistiken/{year}",
        "data_provider": "https://www.easyscore.com",
    }
    (out / "meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    total = sum(len(v["data"]) for v in stats_result.values())
    log(f"\n✅ Klaar! Bestanden opgeslagen in: {out_dir}")
    log(f"   stats.json · splits.json · meta.json")
    log(f"   Totaal: {total} records")
    for k, v in stats_result.items():
        log(f"   {k}: {len(v['data'])}")


def main():
    parser = argparse.ArgumentParser(description="DBL stats scraper")
    parser.add_argument("--year",   type=int, default=2026,  help="Seizoensjaar")
    parser.add_argument("--outdir", default="data",          help="Output map (default: data/)")
    args = parser.parse_args()
    asyncio.run(run(args.year, args.outdir))


if __name__ == "__main__":
    main()
