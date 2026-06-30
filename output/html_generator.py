import os
import json
import logging
import re
import html as _html
from string import Template
from datetime import datetime

from processing.storage import fetch_weekly_counts

logger = logging.getLogger(__name__)

PUBLIC_DIR = os.path.join(os.path.dirname(__file__), "..", "public")

_SENTIMENT_COLORS = {
    "Positive": "#34d399",
    "Negative": "#f87171",
    "Mixed":    "#fbbf24",
}

_HTML = Template("""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Review Mining Dashboard</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Syne:wght@600;700;800&family=JetBrains+Mono:wght@400;500&family=DM+Sans:opsz,wght@9..40,400;9..40,500&display=swap" rel="stylesheet" />
  <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js" integrity="sha512-CQBWl4fJHWbryGE+Pc7UAxWMUMNMWzWxF4SQo9CgkJIN1kx6djDQZjh3Y8SZ1d+6I+1zze6Z7kHXO7q3UyZAWw==" crossorigin="anonymous"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/marked/9.1.6/marked.min.js" integrity="sha512-pmjEJQ7CveksANaAKdCJZMig7eAcCFFzE1b5XnlnxdB/vU3AOStJ5SF7w4tFuqskuU31ETnAaWTYRQOYg2WHKw==" crossorigin="anonymous"></script>
  <style>
    :root {
      --bg:          #070b12;
      --surface:     #0c1018;
      --card:        #0f1520;
      --border:      #1a2535;
      --border-hi:   #253550;
      --text:        #c8d8e8;
      --text-muted:  #4a6080;
      --text-dim:    #1e2d40;
      --accent:      #22d3ee;
      --accent-dim:  rgba(34,211,238,0.08);
      --accent-glow: rgba(34,211,238,0.18);
    }

    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: 'DM Sans', sans-serif;
      background-color: var(--bg);
      background-image: radial-gradient(circle, rgba(34,211,238,0.055) 1px, transparent 1px);
      background-size: 28px 28px;
      color: var(--text);
      min-height: 100vh;
    }

    header {
      background: rgba(12,16,24,0.92);
      backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--border);
      padding: 1.1rem 2rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
      position: sticky;
      top: 0;
      z-index: 10;
    }
    .header-left { display: flex; align-items: center; gap: 0.875rem; }
    .header-mark {
      width: 7px; height: 7px;
      background: var(--accent);
      border-radius: 50%;
      box-shadow: 0 0 10px var(--accent), 0 0 20px rgba(34,211,238,0.4);
      flex-shrink: 0;
    }
    header h1 {
      font-family: 'Syne', sans-serif;
      font-size: 1rem;
      font-weight: 700;
      color: #deeef8;
      letter-spacing: 0.01em;
    }
    header p {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.68rem;
      color: var(--text-muted);
      margin-top: 0.15rem;
      letter-spacing: 0.05em;
    }
    .badges { display: flex; gap: 0.375rem; flex-wrap: wrap; }
    .badge {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.62rem;
      color: var(--accent);
      border: 1px solid rgba(34,211,238,0.28);
      background: var(--accent-dim);
      padding: 0.18rem 0.5rem;
      border-radius: 3px;
      letter-spacing: 0.07em;
      text-transform: uppercase;
    }

    main { max-width: 1100px; margin: 2rem auto; padding: 0 1.5rem; }

    @keyframes fadeUp {
      from { opacity: 0; transform: translateY(14px); }
      to   { opacity: 1; transform: translateY(0); }
    }

    .cards {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 1rem;
      margin-bottom: 1.25rem;
    }
    .card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 1.25rem 1.5rem;
      animation: fadeUp 0.45s ease both;
      transition: border-color 0.25s, box-shadow 0.25s;
    }
    .card:nth-child(1) { animation-delay: 0.05s; }
    .card:nth-child(2) { animation-delay: 0.15s; }
    .card:nth-child(3) { animation-delay: 0.25s; }
    .card:hover {
      border-color: var(--border-hi);
      box-shadow: 0 0 24px rgba(34,211,238,0.05);
    }
    .card-label {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.62rem;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.1em;
      margin-bottom: 0.7rem;
    }
    .card-value {
      font-family: 'Syne', sans-serif;
      font-size: 2.75rem;
      font-weight: 800;
      color: var(--accent);
      line-height: 1;
    }
    .card-sub { font-size: 0.72rem; color: var(--text-muted); margin-top: 0.5rem; }

    .source-bar { margin-top: 0.25rem; }
    .source-row { display: flex; align-items: center; gap: 0.6rem; margin-bottom: 0.65rem; }
    .source-row span:first-child {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.62rem;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.04em;
      width: 72px;
      flex-shrink: 0;
    }
    .source-row span:last-child {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.62rem;
      color: var(--text-muted);
      min-width: 22px;
      text-align: right;
    }
    .bar-track { flex: 1; background: var(--border); border-radius: 2px; height: 3px; }
    .bar-fill  { height: 3px; border-radius: 2px; background: var(--accent);
                 box-shadow: 0 0 6px var(--accent-glow); }

    .sentiment-badge {
      display: inline-block;
      margin-top: 0.6rem;
      padding: 0.28rem 0.7rem;
      border-radius: 3px;
      border: 1px solid;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.68rem;
      font-weight: 500;
      letter-spacing: 0.1em;
      text-transform: uppercase;
    }

    .panel {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 1.5rem;
      margin-bottom: 1.25rem;
      animation: fadeUp 0.45s ease both;
      transition: border-color 0.25s;
    }
    .panel:nth-of-type(1) { animation-delay: 0.3s; }
    .panel:nth-of-type(2) { animation-delay: 0.38s; }
    .panel:hover { border-color: var(--border-hi); }
    .panel.analysis { padding: 1.75rem 2rem; }

    .section-label {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.62rem;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.1em;
      margin-bottom: 1.25rem;
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }
    .section-label::after { content: ''; flex: 1; height: 1px; background: var(--border); }

    #digest h2 {
      font-family: 'Syne', sans-serif;
      font-size: 0.95rem;
      font-weight: 700;
      color: #deeef8;
      margin: 1.5rem 0 0.55rem;
      padding-bottom: 0.4rem;
      border-bottom: 1px solid var(--border);
    }
    #digest h2:first-child { margin-top: 0; }
    #digest h3 {
      font-family: 'Syne', sans-serif;
      font-size: 0.875rem;
      font-weight: 600;
      color: var(--text);
      margin: 1rem 0 0.35rem;
    }
    #digest p  { font-size: 0.85rem; color: var(--text-muted); line-height: 1.85; margin-bottom: 0.7rem; }
    #digest ul { padding-left: 1.25rem; margin-bottom: 0.75rem; }
    #digest li { font-size: 0.85rem; color: var(--text-muted); line-height: 1.85; }
    #digest li::marker { color: var(--accent); }
    #digest strong { color: var(--text); font-weight: 500; }
    #digest code {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.78em;
      background: var(--border);
      color: var(--accent);
      padding: 0.1em 0.4em;
      border-radius: 3px;
    }

    footer {
      text-align: center;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.62rem;
      color: var(--text-dim);
      padding: 2rem;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }

    @media (max-width: 640px) {
      header { flex-direction: column; align-items: flex-start; gap: 0.75rem; }
      .card-value { font-size: 2.25rem; }
      .panel.analysis { padding: 1.25rem; }
    }
  </style>
</head>
<body>
<header>
  <div class="header-left">
    <div class="header-mark"></div>
    <div>
      <h1>Review Mining Dashboard</h1>
      <p>$week_id &nbsp;/&nbsp; $generated_at</p>
    </div>
  </div>
  <div class="badges">$source_badges</div>
</header>

<main>
  <div class="cards">
    <div class="card">
      <div class="card-label">Total Reviews</div>
      <div class="card-value">$total</div>
      <div class="card-sub">collected this week</div>
    </div>
    <div class="card">
      <div class="card-label">By Source</div>
      <div class="source-bar">$source_bars</div>
    </div>
    <div class="card">
      <div class="card-label">Overall Sentiment</div>
      <div class="sentiment-badge" style="color:$sentiment_color;border-color:$sentiment_color">$sentiment</div>
      <div class="card-sub">via Claude analysis</div>
    </div>
  </div>

  <div class="panel">
    <div class="section-label">Weekly Review Volume</div>
    <canvas id="volumeChart" height="70"></canvas>
    <p id="chart-fallback" style="display:none;font-family:'JetBrains Mono',monospace;font-size:0.72rem;color:var(--text-muted);text-align:center;padding:2rem 0;">
      chart unavailable — Chart.js failed to load
    </p>
  </div>

  <div class="panel analysis">
    <div class="section-label">Intelligence Report</div>
    <div id="digest"></div>
  </div>
</main>

<footer>Review Mining Pipeline &nbsp;/&nbsp; $generated_at</footer>

<script>
  const weeklyLabels = $weekly_labels;
  const weeklyCounts = $weekly_counts;
  const digestMarkdown = $digest_json;

  if (typeof marked !== 'undefined') {
    document.getElementById('digest').innerHTML = marked.parse(digestMarkdown);
  } else {
    document.getElementById('digest').innerText = digestMarkdown;
  }

  const canvas = document.getElementById('volumeChart');
  if (typeof Chart !== 'undefined') {
    new Chart(canvas, {
      type: 'bar',
      data: {
        labels: weeklyLabels,
        datasets: [{
          label: 'Reviews',
          data: weeklyCounts,
          backgroundColor: 'rgba(34,211,238,0.6)',
          borderColor: '#22d3ee',
          borderWidth: 1,
          borderRadius: 3,
          borderSkipped: false,
        }]
      },
      options: {
        responsive: true,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#0f1520',
            borderColor: '#1a2535',
            borderWidth: 1,
            titleColor: '#22d3ee',
            bodyColor: '#c8d8e8',
            titleFont: { family: 'JetBrains Mono', size: 11 },
            bodyFont:  { family: 'JetBrains Mono', size: 11 },
            padding: 10,
          }
        },
        scales: {
          y: {
            beginAtZero: true,
            ticks: { precision: 0, color: '#4a6080', font: { family: 'JetBrains Mono', size: 10 } },
            grid: { color: '#1a2535' },
            border: { color: '#1a2535' }
          },
          x: {
            grid: { display: false },
            ticks: { color: '#4a6080', font: { family: 'JetBrains Mono', size: 10 } },
            border: { color: '#1a2535' }
          }
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
        f'<span class="badge">{_html.escape(name.capitalize())}</span>'
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
            f'<span>{_html.escape(name.capitalize())}</span>'
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

    html = _HTML.safe_substitute(
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
