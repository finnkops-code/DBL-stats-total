"""
DBL 2026 Baseball Statistics Scraper
======================================
Scrapes player statistics from baseball.de / easyscore.com using Playwright.
The stats page is a Next.js SPA that loads data dynamically — this scraper
intercepts the actual API calls made by EasyScore's frontend.

Install requirements:
    pip install playwright pandas
    playwright install chromium

Run:
    python scraper.py
    python scraper.py --year 2025   # previous season
    python scraper.py --output stats.json
"""

import asyncio
import json
import argparse
import sys
from pathlib import Path
from datetime import datetime

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("❌  playwright not installed. Run: pip install playwright && playwright install chromium")
    sys.exit(1)


# ── Config ────────────────────────────────────────────────────────────────────

STATS_URL = "https://www.easyscore.com/stats/?y={year}&l=10147&r=0&cat=off"
CATEGORIES = ["off", "pit", "fld"]   # offense / pitching / fielding
CATEGORY_NAMES = {"off": "batting", "pit": "pitching", "fld": "fielding"}

# ── Helpers ───────────────────────────────────────────────────────────────────

def log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


async def scrape_category(page, year: int, cat: str) -> list[dict]:
    """
    Navigate to EasyScore stats for one category.
    Intercepts XHR/fetch requests to capture the raw JSON payload,
    then also falls back to DOM extraction if no JSON is captured.
    """
    url = f"https://www.easyscore.com/stats/?y={year}&l=10147&r=0&cat={cat}"
    captured = []

    # ── Intercept all API responses ──────────────────────────────────────────
    async def handle_response(response):
        rurl = response.url
        # EasyScore fetches stats via their own API – catch anything JSON-shaped
        if (
            "easyscore.com" in rurl
            and response.status == 200
            and "json" in (response.headers.get("content-type", ""))
        ):
            try:
                data = await response.json()
                if isinstance(data, (list, dict)):
                    captured.append({"url": rurl, "data": data})
                    log(f"  📡 Captured JSON from: {rurl}")
            except Exception:
                pass

    page.on("response", handle_response)

    log(f"  🌐 Loading {url}")
    await page.goto(url, wait_until="networkidle", timeout=60_000)

    # Wait extra for lazy-loaded data
    await page.wait_for_timeout(4_000)

    # ── Try to trigger different sub-tabs if present ─────────────────────────
    try:
        # Some versions of the page have tab buttons; click each to load all data
        buttons = await page.query_selector_all("button[data-cat], [role='tab'], .stats-tab")
        if buttons:
            for btn in buttons:
                try:
                    await btn.click()
                    await page.wait_for_timeout(1_500)
                except Exception:
                    pass
    except Exception:
        pass

    page.remove_listener("response", handle_response)

    # ── If JSON was intercepted, return it ────────────────────────────────────
    if captured:
        # Merge all captured payloads
        all_rows = []
        for item in captured:
            d = item["data"]
            if isinstance(d, list):
                all_rows.extend(d)
            elif isinstance(d, dict):
                # Unwrap common wrappers: {players: [...]} {data: [...]} {stats: [...]}
                for key in ("players", "data", "stats", "rows", "results", "items"):
                    if key in d and isinstance(d[key], list):
                        all_rows.extend(d[key])
                        break
                else:
                    all_rows.append(d)
        return all_rows

    # ── Fallback: parse HTML table ────────────────────────────────────────────
    log(f"  ⚠️  No JSON captured for '{cat}', falling back to HTML table parsing")
    return await extract_from_dom(page, cat)


async def extract_from_dom(page, cat: str) -> list[dict]:
    """Extract stats rows directly from the rendered HTML table."""
    try:
        # Wait for a table or stats container
        await page.wait_for_selector(
            "table, .stats-table, [class*='stat'], [class*='player']",
            timeout=10_000,
        )
    except Exception:
        log("  ❌  No stats table found in DOM")
        return []

    rows = await page.evaluate("""
        () => {
            const results = [];

            // ── Try <table> first ─────────────────────────────────────────
            const tables = document.querySelectorAll('table');
            if (tables.length > 0) {
                for (const table of tables) {
                    const headers = [...table.querySelectorAll('thead th, thead td')]
                        .map(th => th.innerText.trim());
                    if (headers.length === 0) continue;

                    for (const row of table.querySelectorAll('tbody tr')) {
                        const cells = [...row.querySelectorAll('td')]
                            .map(td => td.innerText.trim());
                        if (cells.length === 0) continue;
                        const obj = {};
                        headers.forEach((h, i) => { obj[h || `col${i}`] = cells[i] ?? ''; });
                        results.push(obj);
                    }
                }
                if (results.length > 0) return results;
            }

            // ── Generic fallback: rows with multiple children ─────────────
            const candidates = document.querySelectorAll(
                '[class*="row"], [class*="player"], [class*="stat-row"]'
            );
            for (const el of candidates) {
                const spans = [...el.querySelectorAll('span, td, div')]
                    .map(s => s.innerText.trim())
                    .filter(Boolean);
                if (spans.length >= 3) results.push({ raw: spans.join(' | ') });
            }
            return results;
        }
    """)

    log(f"  📋 Extracted {len(rows)} rows from DOM for '{cat}'")
    return rows


# ── Main ──────────────────────────────────────────────────────────────────────

async def run(year: int, output_path: str):
    log(f"🚀 Starting DBL {year} stats scraper")

    all_stats = {}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
            locale="de-DE",
        )

        page = await context.new_page()

        for cat in CATEGORIES:
            cat_name = CATEGORY_NAMES[cat]
            log(f"\n📊 Scraping {cat_name} stats (cat={cat})")
            try:
                rows = await scrape_category(page, year, cat)
                all_stats[cat_name] = rows
                log(f"  ✅ {len(rows)} {cat_name} records collected")
            except Exception as e:
                log(f"  ❌ Error scraping {cat_name}: {e}")
                all_stats[cat_name] = []

        await browser.close()

    # ── Write output ──────────────────────────────────────────────────────────
    out = {
        "meta": {
            "source": f"https://www.baseball.de/saison/statistiken/{year}",
            "data_provider": "https://www.easyscore.com",
            "league_id": 10147,
            "year": year,
            "scraped_at": datetime.utcnow().isoformat() + "Z",
        },
        "stats": all_stats,
    }

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(json.dumps(out, indent=2, ensure_ascii=False))
    log(f"\n✅ Done! Output saved to: {output_path}")

    # Summary
    total = sum(len(v) for v in all_stats.values())
    log(f"📈 Total records: {total}")
    for k, v in all_stats.items():
        log(f"   {k}: {len(v)}")

    return out


def main():
    parser = argparse.ArgumentParser(description="Scrape DBL baseball statistics")
    parser.add_argument("--year", type=int, default=2026, help="Season year (default: 2026)")
    parser.add_argument("--output", default="dbl_stats.json", help="Output JSON file path")
    args = parser.parse_args()

    asyncio.run(run(args.year, args.output))


if __name__ == "__main__":
    main()
