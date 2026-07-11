# Pulse Check

An automated weekly intelligence pipeline that scrapes reviews and discussions from Reddit, Capterra, and Hacker News, runs them through Gemini AI, and generates a structured digest and interactive HTML dashboard — all without manual intervention.

## What It Does

Each run:
1. Scrapes posts from Reddit subreddits, Capterra product reviews, and Hacker News discussions
2. Cleans and deduplicates the data, stores it in SQLite
3. Sends the reviews to Gemini AI for analysis
4. Outputs a Markdown digest and an HTML dashboard with charts and insights

## Output

**Markdown digest** saved to `digests/YYYY-WNN.md`:
- Top 5 recurring themes (positive and negative)
- Overall sentiment with rationale
- Emerging or unusual signals
- Repeated pain points, features, and competitor mentions

**HTML dashboard** at `public/index.html`:
- Weekly review volume bar chart
- Source distribution doughnut chart
- Top themes horizontal bar chart
- Tabbed intelligence report with Key Insights summary
- Mobile-responsive, dark-themed UI

To view the dashboard locally:
```bash
python -m http.server 8080 --directory public
```
Then open **http://localhost:8080**.

## Setup

**1. Install dependencies**
```bash
pip install -r requirements.txt
```

**2. Configure environment**
```bash
cp .env.example .env
```
Fill in `.env` with your Gemini API key:
```
GEMINI_API_KEY=your_key_here
```

**3. Adjust targets in `config.py`**
```python
ANALYSIS_TOPIC = "productivity and collaboration software tools"

SEARCH_QUERIES = {
    "reddit":     ["r/projectmanagement", "r/Airtable", "r/nocode", "r/SaaS"],
    "capterra":   ["project management", "collaboration software"],
    "hackernews": ["productivity tools", "collaboration software"],
}
```

**4. Run**
```bash
python main.py
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `MAX_REVIEWS_PER_SOURCE` | 50 | Posts to collect per query per source |
| `MAX_REVIEWS_FOR_ANALYSIS` | 150 | Hard cap on reviews sent to Gemini per run |
| `MAX_TOKEN_BUDGET` | 100,000 | Token limit per run before stopping early |
| `BATCH_SIZE` | 30 | Reviews per Gemini API call |
| `INTER_BATCH_DELAY` | 2s | Delay between API calls |

## Project Structure

```
review-scraper/
├── main.py               # Entry point — runs the full pipeline
├── config.py             # Search targets and settings
├── scrapers/
│   ├── base.py           # Retry logic, shared session
│   ├── reddit.py         # Reddit RSS scraper
│   ├── capterra.py       # Capterra review scraper
│   └── hackernews.py     # Hacker News scraper
├── processing/
│   ├── cleaner.py        # Deduplication, normalisation, filtering
│   └── storage.py        # SQLite read/write helpers
├── ai/
│   └── analyser.py       # Gemini API calls, batching, token tracking
├── output/
│   ├── formatter.py      # Markdown digest generator
│   └── html_generator.py # HTML dashboard generator
├── public/
│   ├── index.html        # Generated dashboard
│   └── js/               # Bundled Chart.js (no CDN dependency)
└── digests/              # Weekly digest output files
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | Yes | Google Gemini API key |

## Automation

A GitHub Actions workflow runs the pipeline every **Monday at 9am UTC** and commits the updated digest and dashboard back to the repo automatically.

To enable it, add your API key under **Settings → Secrets and variables → Actions** in your GitHub repo:

| Secret | Value |
|---|---|
| `GEMINI_API_KEY` | Your Google Gemini API key |

You can also trigger a run manually from the **Actions** tab → **Weekly Pulse Check** → **Run workflow**.

The SQLite database is cached between runs (up to 10 GB per repo) so scraped data accumulates across executions.
