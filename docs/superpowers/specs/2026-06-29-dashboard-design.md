# Dashboard Design Spec
**Date:** 2026-06-29
**Feature:** One-page HTML dashboard for review mining pipeline results
**Deployment target:** Vercel (static)

---

## Goal

Generate a self-contained `public/index.html` as part of each pipeline run. The file is committed to the repo and Vercel auto-deploys it. No backend, no API, no extra dependencies.

---

## Architecture

### New file: `output/html_generator.py`

A single Python module with one public function:

```python
def write_dashboard(week_id: str, analysis: str, stats: dict) -> str
```

It:
1. Reads all weekly review counts from SQLite (for the bar chart)
2. Combines the current week's stats + analysis + historical data
3. Renders a self-contained HTML string
4. Writes it to `public/index.html`
5. Returns the output path

### Changes to `main.py`

Add one call after `write_digest`:
```python
from output.html_generator import write_dashboard
dashboard_path = write_dashboard(week_id, analysis, stats)
logger.info("Dashboard written: %s", dashboard_path)
```

### New file: `vercel.json`

```json
{
  "outputDirectory": "public"
}
```

Tells Vercel to serve the `public/` directory as the static root.

### New directory: `public/`

Contains only `index.html`. Added to `.gitignore` exclusions so it IS committed (unlike `digests/` and `data/`).

---

## Page Layout

Single scrolling page, modern light dashboard style (subtle colors, card shadows).

### Header
- Title: "Review Mining Dashboard"
- Subtitle: current week ID + date
- Pill badges for each active source (Reddit, Trustpilot)

### Stats Row (3 cards)
- **Total Reviews** — integer count for the current week
- **By Source** — small horizontal bar showing Reddit vs Trustpilot split
- **Sentiment** — text badge (Positive / Mixed / Negative) parsed from the digest

### Weekly Volume Chart
- Bar chart using Chart.js (CDN, no install)
- X-axis: last 8 week IDs
- Y-axis: review count
- Data sourced from SQLite query: `SELECT week_id, COUNT(*) FROM reviews GROUP BY week_id ORDER BY week_id DESC LIMIT 8`

### Analysis Section
- Full Claude digest rendered as HTML
- Markdown converted client-side using marked.js (CDN)
- Digest text embedded as a JS string in the HTML

### Footer
- "Generated on {datetime}" + "by Review Mining Pipeline"

---

## Data Flow

```
SQLite (reviews.db)
    └── weekly counts query → bar chart data

digests/YYYY-WNN.md (or analysis string passed directly)
    └── embedded as escaped JS string → marked.js renders it

stats dict (from run_scrapers)
    └── total + per-source counts → stat cards
```

All data is baked into the HTML at generation time. No runtime data fetching.

---

## External Dependencies (CDN only, no pip installs)

| Library | Purpose |
|---|---|
| Chart.js 4.x | Weekly volume bar chart |
| marked.js 9.x | Render digest markdown to HTML |

Both loaded via `<script>` tags from cdnjs. Page degrades gracefully if CDN is unavailable (stats cards still show, chart area shows a message).

---

## Sentiment Parsing

Parse sentiment from the analysis string with a simple regex before embedding:
- Search for "positive", "negative", "mixed" in the `## Overall Sentiment` section
- Default to "Mixed" if not found
- Used to set the badge color: green / red / amber

---

## Files Changed

| File | Change |
|---|---|
| `output/html_generator.py` | New — generates `public/index.html` |
| `main.py` | Add `write_dashboard()` call after `write_digest()` |
| `vercel.json` | New — tells Vercel to serve `public/` |
| `public/index.html` | Generated output (committed to repo) |
| `.gitignore` | Ensure `public/` is NOT ignored |

---

## Out of Scope

- Multi-page navigation
- Search or filtering of raw reviews
- Live data refresh
- Authentication
- G2 scraper (V2 item)
