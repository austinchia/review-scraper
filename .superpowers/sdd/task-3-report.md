# Task 3 Fix Report

Date: 2026-06-30

## Changes Made

### Fix 1 — Use column names instead of positional index (`processing/storage.py`)

Changed `fetch_weekly_counts()` to access row fields by name (`r["week_id"]`, `r["count"]`) instead of positional index (`r[0]`, `r[1]`). This is consistent with the rest of the file which already uses `sqlite3.Row` (set via `conn.row_factory = sqlite3.Row`) and accesses rows by name in `fetch_unprocessed`.

### Fix 2 — Add SRI hashes to CDN script tags (`output/html_generator.py`)

Added `integrity` and `crossorigin="anonymous"` attributes to both CDN script tags in the `_HTML` template:

- Chart.js 4.4.1 UMD (`chart.umd.min.js`):
  `sha512-CQBWl4fJHWbryGE+Pc7UAxWMUMNMWzWxF4SQo9CgkJIN1kx6djDQZjh3Y8SZ1d+6I+1zze6Z7kHXO7q3UyZAWw==`
- marked 9.1.6 (`marked.min.js`):
  `sha512-pmjEJQ7CveksANaAKdCJZMig7eAcCFFzE1b5XnlnxdB/vU3AOStJ5SF7w4tFuqskuU31ETnAaWTYRQOYg2WHKw==`

Hashes fetched from `https://api.cdnjs.com/libraries/{library}/{version}?fields=sri`.

### Fix 3 — Add git commit + push step to GitHub Actions workflow (`.github/workflows/pipeline.yml`)

Added a new step "Commit updated dashboard" between the `python main.py` step and the `upload-artifact` step. The step:
- Configures git user as `github-actions[bot]`
- Stages `public/index.html`
- Commits only if there are staged changes (no empty commits)
- Pushes to the branch, allowing Vercel to pick up the regenerated dashboard

## Test Results

```
8 passed in 0.11s
```

All 8 tests passed:
- `tests/test_html_generator.py` — 6 tests (dashboard file creation, week_id content, sources content, sentiment parsing)
- `tests/test_storage.py` — 2 tests (weekly counts sorted, empty DB)
