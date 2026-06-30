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
