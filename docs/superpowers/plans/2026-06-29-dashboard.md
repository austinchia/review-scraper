# Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate a self-contained `public/index.html` dashboard during each pipeline run, commit it to the repo, and serve it on Vercel as a static site.

**Architecture:** A new `output/html_generator.py` module reads weekly counts from SQLite and the current analysis string, then writes a single HTML file with Chart.js and marked.js loaded from CDN. `main.py` calls it after `write_digest()`. Vercel is configured to serve the `public/` directory.

**Tech Stack:** Python 3.11+, SQLite (stdlib), Chart.js 4.4.1 (CDN), marked.js 9.1.6 (CDN), Python `string.Template`

## Global Constraints

- No new pip dependencies — use stdlib only
- All external JS loaded from cdnjs CDN via `<script>` tags
- `public/index.html` must be a single self-contained file (no separate CSS or JS files)
- Follow existing patterns: module-level logger, `os.path.join(os.path.dirname(__file__), ...)` for paths
- Python 3.11+

---

### Task 1: Add `fetch_weekly_counts()` to storage.py

**Files:**
- Modify: `processing/storage.py`
- Create: `tests/test_storage.py`

**Interfaces:**
- Produces: `fetch_weekly_counts() -> list[dict]` where each dict has keys `"week_id": str` and `"count": int`, ordered oldest to newest

- [ ] **Step 1: Create the test file**

```python
# tests/test_storage.py
import os
import sqlite3
import pytest
from unittest.mock import patch

# Point at a temp DB so tests don't touch the real one
TEST_DB = ":memory:"


def _seed_db(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT, query TEXT, title TEXT, text TEXT NOT NULL,
            text_hash TEXT UNIQUE NOT NULL, rating INTEGER, date TEXT,
            url TEXT, scraped_at TEXT, week_id TEXT, processed INTEGER DEFAULT 0
        )
    """)
    conn.executemany(
        "INSERT INTO reviews (source, text, text_hash, week_id) VALUES (?, ?, ?, ?)",
        [
            ("reddit", "text1", "h1", "2026-W25"),
            ("reddit", "text2", "h2", "2026-W25"),
            ("trustpilot", "text3", "h3", "2026-W26"),
        ]
    )
    conn.commit()


def test_fetch_weekly_counts_returns_sorted_weeks(tmp_path):
    db_path = str(tmp_path / "reviews.db")
    conn = sqlite3.connect(db_path)
    _seed_db(conn)
    conn.close()

    with patch("processing.storage.DB_PATH", db_path):
        from processing.storage import fetch_weekly_counts
        result = fetch_weekly_counts()

    assert len(result) == 2
    assert result[0] == {"week_id": "2026-W25", "count": 2}
    assert result[1] == {"week_id": "2026-W26", "count": 1}


def test_fetch_weekly_counts_empty_db(tmp_path):
    db_path = str(tmp_path / "reviews.db")
    conn = sqlite3.connect(db_path)
    _seed_db(conn)
    conn.execute("DELETE FROM reviews")
    conn.commit()
    conn.close()

    with patch("processing.storage.DB_PATH", db_path):
        from processing.storage import fetch_weekly_counts
        result = fetch_weekly_counts()

    assert result == []
```

- [ ] **Step 2: Run the test to confirm it fails**

```
pytest tests/test_storage.py -v
```

Expected: `ImportError` or `AttributeError: module has no attribute 'fetch_weekly_counts'`

- [ ] **Step 3: Add `fetch_weekly_counts()` to `processing/storage.py`**

Add this function at the bottom of `processing/storage.py`:

```python
def fetch_weekly_counts() -> list[dict]:
    conn = _connect()
    rows = conn.execute(
        "SELECT week_id, COUNT(*) as count FROM reviews GROUP BY week_id ORDER BY week_id ASC"
    ).fetchall()
    conn.close()
    return [{"week_id": r[0], "count": r[1]} for r in rows]
```

- [ ] **Step 4: Run tests to confirm they pass**

```
pytest tests/test_storage.py -v
```

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add processing/storage.py tests/test_storage.py
git commit -m "feat: add fetch_weekly_counts to storage"
```

---

### Task 2: Create `output/html_generator.py`

**Files:**
- Create: `output/html_generator.py`
- Create: `tests/test_html_generator.py`

**Interfaces:**
- Consumes: `fetch_weekly_counts() -> list[dict]` from `processing.storage` (Task 1)
- Produces: `write_dashboard(week_id: str, analysis: str, stats: dict) -> str` — writes `public/index.html`, returns the path

- [ ] **Step 1: Write the tests**

```python
# tests/test_html_generator.py
import os
import pytest
from unittest.mock import patch


SAMPLE_ANALYSIS = """## Top Themes
- Theme one
- Theme two

## Overall Sentiment
The overall sentiment is **positive** with strong satisfaction signals.

## Emerging Signals
- Signal one

## Notable Pain Points & Features
- Pain point one
"""

SAMPLE_STATS = {
    "sources": {"reddit": 30, "trustpilot": 20},
    "total": 50,
}

WEEKLY_COUNTS = [
    {"week_id": "2026-W24", "count": 40},
    {"week_id": "2026-W25", "count": 35},
    {"week_id": "2026-W26", "count": 50},
]


def test_write_dashboard_creates_file(tmp_path):
    public_dir = tmp_path / "public"
    with patch("output.html_generator.PUBLIC_DIR", str(public_dir)):
        with patch("output.html_generator.fetch_weekly_counts", return_value=WEEKLY_COUNTS):
            from output.html_generator import write_dashboard
            path = write_dashboard("2026-W26", SAMPLE_ANALYSIS, SAMPLE_STATS)

    assert os.path.exists(path)
    assert path.endswith("index.html")


def test_write_dashboard_html_contains_week_id(tmp_path):
    public_dir = tmp_path / "public"
    with patch("output.html_generator.PUBLIC_DIR", str(public_dir)):
        with patch("output.html_generator.fetch_weekly_counts", return_value=WEEKLY_COUNTS):
            from output.html_generator import write_dashboard
            path = write_dashboard("2026-W26", SAMPLE_ANALYSIS, SAMPLE_STATS)

    html = open(path, encoding="utf-8").read()
    assert "2026-W26" in html


def test_write_dashboard_html_contains_sources(tmp_path):
    public_dir = tmp_path / "public"
    with patch("output.html_generator.PUBLIC_DIR", str(public_dir)):
        with patch("output.html_generator.fetch_weekly_counts", return_value=WEEKLY_COUNTS):
            from output.html_generator import write_dashboard
            path = write_dashboard("2026-W26", SAMPLE_ANALYSIS, SAMPLE_STATS)

    html = open(path, encoding="utf-8").read()
    assert "Reddit" in html
    assert "Trustpilot" in html
    assert "50" in html


def test_parse_sentiment_positive():
    from output.html_generator import _parse_sentiment
    assert _parse_sentiment(SAMPLE_ANALYSIS) == "Positive"


def test_parse_sentiment_negative():
    from output.html_generator import _parse_sentiment
    analysis = "## Overall Sentiment\nThe sentiment is negative overall.\n"
    assert _parse_sentiment(analysis) == "Negative"


def test_parse_sentiment_defaults_to_mixed():
    from output.html_generator import _parse_sentiment
    assert _parse_sentiment("No sentiment section here.") == "Mixed"
```

- [ ] **Step 2: Run tests to confirm they fail**

```
pytest tests/test_html_generator.py -v
```

Expected: `ImportError: No module named 'output.html_generator'`

- [ ] **Step 3: Create `output/html_generator.py`**

```python
import os
import json
import logging
import re
from string import Template
from datetime import datetime

from processing.storage import fetch_weekly_counts

logger = logging.getLogger(__name__)

PUBLIC_DIR = os.path.join(os.path.dirname(__file__), "..", "public")

_SENTIMENT_COLORS = {
    "Positive": "#16a34a",
    "Negative": "#dc2626",
    "Mixed":    "#d97706",
}

_HTML = Template("""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Review Mining Dashboard</title>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/marked/9.1.6/marked.min.js"></script>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
           background: #f8fafc; color: #1e293b; min-height: 100vh; }
    header { background: #fff; border-bottom: 1px solid #e2e8f0;
             padding: 1.25rem 2rem; display: flex; align-items: center;
             justify-content: space-between; }
    header h1 { font-size: 1.25rem; font-weight: 700; color: #0f172a; }
    header p  { font-size: 0.875rem; color: #64748b; margin-top: 0.2rem; }
    .badges { display: flex; gap: 0.5rem; flex-wrap: wrap; }
    .badge { background: #e0f2fe; color: #0369a1; font-size: 0.75rem;
             font-weight: 600; padding: 0.25rem 0.625rem; border-radius: 9999px; }
    main { max-width: 1100px; margin: 2rem auto; padding: 0 1.5rem; }
    .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
             gap: 1rem; margin-bottom: 1.5rem; }
    .card { background: #fff; border: 1px solid #e2e8f0; border-radius: 0.75rem;
            padding: 1.25rem 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,.06); }
    .card-label { font-size: 0.75rem; font-weight: 600; color: #64748b;
                  text-transform: uppercase; letter-spacing: .05em; margin-bottom: 0.5rem; }
    .card-value { font-size: 2rem; font-weight: 700; color: #0f172a; line-height: 1; }
    .card-sub   { font-size: 0.8rem; color: #64748b; margin-top: 0.5rem; }
    .source-bar { margin-top: 0.75rem; }
    .source-row { display: flex; align-items: center; gap: 0.5rem;
                  font-size: 0.8rem; margin-bottom: 0.4rem; }
    .source-row span:first-child { width: 80px; color: #475569; }
    .bar-track { flex: 1; background: #f1f5f9; border-radius: 9999px; height: 8px; }
    .bar-fill  { height: 8px; border-radius: 9999px; background: #3b82f6; }
    .sentiment-badge { display: inline-block; margin-top: 0.75rem; padding: 0.35rem 0.75rem;
                       border-radius: 9999px; font-size: 0.85rem; font-weight: 600; color: #fff; }
    .chart-card { background: #fff; border: 1px solid #e2e8f0; border-radius: 0.75rem;
                  padding: 1.25rem 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,.06);
                  margin-bottom: 1.5rem; }
    .chart-card h2 { font-size: 0.875rem; font-weight: 600; color: #64748b;
                     text-transform: uppercase; letter-spacing: .05em; margin-bottom: 1rem; }
    .analysis-card { background: #fff; border: 1px solid #e2e8f0; border-radius: 0.75rem;
                     padding: 1.5rem 2rem; box-shadow: 0 1px 3px rgba(0,0,0,.06);
                     margin-bottom: 1.5rem; }
    .analysis-card h2 { font-size: 0.875rem; font-weight: 600; color: #64748b;
                        text-transform: uppercase; letter-spacing: .05em; margin-bottom: 1.25rem; }
    #digest h2 { font-size: 1.1rem; font-weight: 700; color: #0f172a;
                 margin: 1.25rem 0 0.5rem; border-bottom: 1px solid #f1f5f9; padding-bottom: 0.4rem; }
    #digest h3 { font-size: 0.95rem; font-weight: 600; color: #334155; margin: 1rem 0 0.4rem; }
    #digest p  { font-size: 0.9rem; color: #475569; line-height: 1.7; margin-bottom: 0.75rem; }
    #digest ul { padding-left: 1.25rem; margin-bottom: 0.75rem; }
    #digest li { font-size: 0.9rem; color: #475569; line-height: 1.7; }
    #digest strong { color: #0f172a; }
    footer { text-align: center; font-size: 0.75rem; color: #94a3b8;
             padding: 2rem; border-top: 1px solid #e2e8f0; margin-top: 1rem; }
    @media (max-width: 600px) {
      header { flex-direction: column; align-items: flex-start; gap: 0.75rem; }
      .card-value { font-size: 1.5rem; }
    }
  </style>
</head>
<body>
<header>
  <div>
    <h1>Review Mining Dashboard</h1>
    <p>$week_id &nbsp;·&nbsp; Generated $generated_at</p>
  </div>
  <div class="badges">$source_badges</div>
</header>

<main>
  <div class="cards">
    <div class="card">
      <div class="card-label">Total Reviews</div>
      <div class="card-value">$total</div>
      <div class="card-sub">this week across all sources</div>
    </div>
    <div class="card">
      <div class="card-label">By Source</div>
      <div class="source-bar">$source_bars</div>
    </div>
    <div class="card">
      <div class="card-label">Overall Sentiment</div>
      <div class="sentiment-badge" style="background:$sentiment_color">$sentiment</div>
      <div class="card-sub">based on Claude analysis</div>
    </div>
  </div>

  <div class="chart-card">
    <h2>Weekly Review Volume</h2>
    <canvas id="volumeChart" height="80"></canvas>
    <p id="chart-fallback" style="display:none;color:#94a3b8;font-size:0.85rem">
      Chart unavailable (Chart.js failed to load)
    </p>
  </div>

  <div class="analysis-card">
    <h2>This Week's Analysis</h2>
    <div id="digest"></div>
  </div>
</main>

<footer>Generated by Review Mining Pipeline &nbsp;·&nbsp; $generated_at</footer>

<script>
  const weeklyLabels = $weekly_labels;
  const weeklyCounts = $weekly_counts;
  const digestMarkdown = $digest_json;

  // Render markdown
  if (typeof marked !== 'undefined') {
    document.getElementById('digest').innerHTML = marked.parse(digestMarkdown);
  } else {
    document.getElementById('digest').innerText = digestMarkdown;
  }

  // Render chart
  const canvas = document.getElementById('volumeChart');
  if (typeof Chart !== 'undefined') {
    new Chart(canvas, {
      type: 'bar',
      data: {
        labels: weeklyLabels,
        datasets: [{
          label: 'Reviews',
          data: weeklyCounts,
          backgroundColor: '#3b82f6',
          borderRadius: 4,
          borderSkipped: false,
        }]
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
          y: { beginAtZero: true, ticks: { precision: 0 },
               grid: { color: '#f1f5f9' } },
          x: { grid: { display: false } }
        }
      }
    });
  } else {
    canvas.style.display = 'none';
    document.getElementById('chart-fallback').style.display = 'block';
  }
</script>
</body>
</html>
""")


def _parse_sentiment(analysis: str) -> str:
    match = re.search(
        r"## Overall Sentiment\s*(.*?)(?=\n##|\Z)", analysis, re.DOTALL | re.IGNORECASE
    )
    if match:
        section = match.group(1).lower()
        if "positive" in section:
            return "Positive"
        if "negative" in section:
            return "Negative"
    return "Mixed"


def _source_badges(sources: dict) -> str:
    return "".join(
        f'<span class="badge">{name.capitalize()}</span>'
        for name in sorted(sources)
    )


def _source_bars(sources: dict, total: int) -> str:
    if total == 0:
        return ""
    lines = []
    for name, count in sorted(sources.items()):
        pct = round(count / total * 100)
        lines.append(
            f'<div class="source-row">'
            f'<span>{name.capitalize()}</span>'
            f'<div class="bar-track"><div class="bar-fill" style="width:{pct}%"></div></div>'
            f'<span>{count}</span></div>'
        )
    return "".join(lines)


def write_dashboard(week_id: str, analysis: str, stats: dict) -> str:
    os.makedirs(PUBLIC_DIR, exist_ok=True)
    output_path = os.path.join(PUBLIC_DIR, "index.html")

    weekly = fetch_weekly_counts()
    labels = [w["week_id"] for w in weekly[-8:]]
    counts = [w["count"]   for w in weekly[-8:]]

    sentiment = _parse_sentiment(analysis)
    total     = stats.get("total", 0)
    sources   = stats.get("sources", {})

    html = _HTML.substitute(
        week_id=week_id,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        source_badges=_source_badges(sources),
        total=total,
        source_bars=_source_bars(sources, total),
        sentiment=sentiment,
        sentiment_color=_SENTIMENT_COLORS.get(sentiment, "#d97706"),
        weekly_labels=json.dumps(labels),
        weekly_counts=json.dumps(counts),
        digest_json=json.dumps(analysis),
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    logger.info("Dashboard written to %s", output_path)
    return output_path
```

- [ ] **Step 4: Run tests to confirm they pass**

```
pytest tests/test_html_generator.py -v
```

Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add output/html_generator.py tests/test_html_generator.py
git commit -m "feat: add html_generator for static dashboard"
```

---

### Task 3: Wire into `main.py`, add `vercel.json`, update `.gitignore`, deploy

**Files:**
- Modify: `main.py`
- Modify: `.gitignore`
- Create: `vercel.json`
- Create: `public/index.html` (generated by running the pipeline or a test run)

**Interfaces:**
- Consumes: `write_dashboard(week_id: str, analysis: str, stats: dict) -> str` from `output.html_generator` (Task 2)

- [ ] **Step 1: Add `write_dashboard` call to `main.py`**

Add the import at the top of `main.py` alongside the other output imports:

```python
from output.html_generator import write_dashboard
```

Add this block in `main()` immediately after the `write_digest` call (line 68):

```python
    dashboard_path = write_dashboard(week_id, analysis, stats)
    logger.info("Dashboard written: %s", dashboard_path)
```

And add it to the final print block:

```python
    print(f"Dashboard:  {dashboard_path}")
```

- [ ] **Step 2: Ensure `public/` is committed (not gitignored)**

Check `.gitignore` — `public/` must NOT appear in it. Open `.gitignore` and confirm it only contains:

```
.env
data/reviews.db
digests/
__pycache__/
*.pyc
.venv/
venv/
```

If `public/` or `public/**` appears, remove it.

- [ ] **Step 3: Create `vercel.json`**

Create `vercel.json` in the project root:

```json
{
  "outputDirectory": "public"
}
```

- [ ] **Step 4: Generate the initial `public/index.html`**

Since the pipeline needs real data to run, generate a placeholder dashboard with stub data so `public/index.html` exists before the first real pipeline run:

```bash
python -c "
from output.html_generator import write_dashboard
path = write_dashboard(
    '2026-W00',
    '## Top Themes\n- Awaiting first pipeline run\n\n## Overall Sentiment\nMixed — no data yet.\n\n## Emerging Signals\n- Run the pipeline to populate this dashboard.\n\n## Notable Pain Points & Features\n- N/A',
    {'sources': {}, 'total': 0}
)
print('Written to:', path)
"
```

- [ ] **Step 5: Commit everything**

```bash
git add main.py vercel.json public/index.html
git commit -m "feat: wire dashboard into pipeline and add Vercel config"
```

- [ ] **Step 6: Push to GitHub**

```bash
git push
```

- [ ] **Step 7: Deploy to Vercel**

1. Go to vercel.com → "Add New Project"
2. Import your `review-scraper` GitHub repo
3. Vercel will detect `vercel.json` and serve `public/` automatically
4. Click Deploy — the dashboard will be live at your Vercel URL

To verify: open the Vercel URL and confirm the page loads with the stub content. After the next `python main.py` run, commit the regenerated `public/index.html` and Vercel will auto-redeploy.

---

## Self-Review

| Spec requirement | Task |
|---|---|
| Self-contained `public/index.html` | Task 2 (`html_generator.py`) |
| Chart.js for weekly volume bar chart | Task 2 (CDN script tag + JS) |
| marked.js for markdown digest | Task 2 (CDN script tag + JS) |
| Stats cards (total, by source, sentiment) | Task 2 (`_source_bars`, `_parse_sentiment`) |
| Pipeline calls generator after each run | Task 3 (`main.py`) |
| `vercel.json` serving `public/` | Task 3 |
| `public/` committed to repo | Task 3 |
| No new pip dependencies | All tasks — stdlib + CDN only |
