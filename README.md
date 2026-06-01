# DBL 2026 Baseball Statistics Scraper

Scrapes all player statistics (batting, pitching, fielding) from the
Deutsche Baseball Liga stats page at [baseball.de](https://www.baseball.de/saison/statistiken/2026),
which sources data from [easyscore.com](https://www.easyscore.com).

## Why previous scrapers failed

The stats page embeds an `<iframe>` pointing to EasyScore, which is a
**Next.js single-page application** — the page HTML is just a shell with
`"loading..."` text. All actual data is fetched **client-side via JavaScript
after the page loads**, so any scraper that only fetches raw HTML or
immediately parses the response will get empty results.

This scraper uses **Playwright** (a headless browser) to:
1. Render the page fully, executing all JavaScript
2. **Intercept XHR/fetch network requests** to capture the raw JSON payloads
   that EasyScore's frontend receives from its API
3. Fall back to DOM table parsing if JSON interception doesn't capture data

## Requirements

```bash
pip install playwright pandas
playwright install chromium
```

## Usage

```bash
# Scrape 2026 season (default)
python scraper.py

# Scrape a specific year
python scraper.py --year 2025

# Custom output path
python scraper.py --output data/stats_2026.json
```

## Output

A JSON file `dbl_stats.json` with this structure:

```json
{
  "meta": {
    "source": "https://www.baseball.de/saison/statistiken/2026",
    "data_provider": "https://www.easyscore.com",
    "league_id": 10147,
    "year": 2026,
    "scraped_at": "2026-06-01T..."
  },
  "stats": {
    "batting":  [ { "Player": "...", "G": "12", "AVG": ".312", ... } ],
    "pitching": [ { "Player": "...", "ERA": "2.40", "IP": "45.0", ... } ],
    "fielding": [ { "Player": "...", "FLD%": ".987", ... } ]
  }
}
```

## Notes

- The scraper waits for `networkidle` + an additional 4 seconds to ensure
  all lazy-loaded data has been fetched before extraction.
- Headless Chrome is launched with a realistic `User-Agent` to avoid
  bot-detection blocks.
- If EasyScore changes its internal API paths, the DOM fallback parser
  will still extract data from rendered HTML tables.

## GitHub usage

Push this file to any GitHub repository and run it in CI or locally.
No API keys required — it scrapes the public stats page directly.
