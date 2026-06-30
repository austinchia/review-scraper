# Review Mining Pipeline

A personal automation tool that scrapes reviews and discussions from Trustpilot and Reddit, runs them through Claude (Anthropic), and generates a structured weekly digest — all without manual intervention.

## What It Does

Each run:
1. Scrapes reviews from Trustpilot and posts from Reddit subreddits
2. Cleans and deduplicates the data, stores it in SQLite
3. Sends the reviews to Claude for analysis
4. Outputs a Markdown digest with themes, sentiment, and signals

## Output

A Markdown file saved to `/digests/YYYY-WNN.md` containing:
- Top 5 recurring themes (positive and negative)
- Overall sentiment with rationale
- Emerging or unusual signals
- Repeated pain points, features, and competitor mentions

## Setup

**1. Install dependencies**
```bash
pip install -r requirements.txt
```

**2. Configure environment**
```bash
cp .env.example .env
```
Fill in `.env` with your Anthropic API key and DataImpulse proxy credentials.

**3. Adjust targets in `config.py`**
```python
SEARCH_QUERIES = {
    "trustpilot": ["data analytics course", "online data training"],
    "reddit": ["r/PowerBI", "r/dataengineering", "r/learnpython"],
}
```
Point these at whatever topics, tools, or competitors you want to monitor.

**4. Run**
```bash
python main.py
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `MAX_REVIEWS_PER_SOURCE` | 50 | Reviews to collect per query per source |
| `MAX_REVIEWS_FOR_ANALYSIS` | 150 | Hard cap on reviews sent to Claude per run |
| `MAX_TOKEN_BUDGET` | 100,000 | Token limit per run before stopping early |
| `BATCH_SIZE` | 30 | Reviews per Claude API call |
| `INTER_BATCH_DELAY` | 2s | Delay between API calls |

## Project Structure

```
review-scraper/
├── main.py               # Entry point — runs the full pipeline
├── config.py             # Search targets and settings
├── scrapers/
│   ├── base.py           # Proxy setup, retry logic, shared session
│   ├── trustpilot.py     # Trustpilot scraper
│   └── reddit.py         # Reddit RSS scraper
├── processing/
│   ├── cleaner.py        # Deduplication, normalisation, filtering
│   └── storage.py        # SQLite read/write helpers
├── ai/
│   └── analyser.py       # Claude API calls, batching, cost tracking
├── output/
│   └── formatter.py      # Markdown digest generator
└── digests/              # Weekly digest output files
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key |
| `PROXY_HOST` | No | DataImpulse proxy host |
| `PROXY_PORT` | No | DataImpulse proxy port |
| `PROXY_USER` | No | Proxy username |
| `PROXY_PASS` | No | Proxy password |

The proxy is optional but recommended for Trustpilot scraping to avoid blocks. Reddit uses RSS and does not require a proxy.

## Automation

A GitHub Actions workflow (`.github/workflows/pipeline.yml`) runs the pipeline every Monday at 8am UTC. Add your secrets under **Settings → Secrets → Actions** in your GitHub repo to enable it.
