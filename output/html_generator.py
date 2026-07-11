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

_SRC_COLORS = {
    "reddit":      "#ff6314",
    "hackernews":  "#fb923c",
    "capterra":    "#34d399",
}


# ── Server-side markdown helpers ─────────────────────────────────────────────

def _inline(text: str) -> str:
    text = _html.escape(text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<em>\1</em>', text)
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
    return text


def _md_to_html(md: str) -> str:
    lines = md.split('\n')
    out = []
    in_ul = in_ol = False

    def close_lists():
        nonlocal in_ul, in_ol
        if in_ul:
            out.append('</ul>')
            in_ul = False
        if in_ol:
            out.append('</ol>')
            in_ol = False

    for line in lines:
        if line.startswith('### '):
            close_lists()
            out.append(f'<h3>{_inline(line[4:])}</h3>')
        elif line.startswith('## '):
            close_lists()
            out.append(f'<h2>{_inline(line[3:])}</h2>')
        elif line.strip() in ('---', '***'):
            close_lists()
            out.append('<hr>')
        elif re.match(r'^[\*\-]\s{1,4}', line):
            text = re.sub(r'^[\*\-]\s+', '', line)
            if not in_ul:
                close_lists()
                out.append('<ul>')
                in_ul = True
            out.append(f'<li>{_inline(text)}</li>')
        elif re.match(r'^\d+\.\s+', line):
            text = re.sub(r'^\d+\.\s+', '', line)
            if not in_ol:
                close_lists()
                out.append('<ol>')
                in_ol = True
            out.append(f'<li>{_inline(text)}</li>')
        elif line.strip() == '':
            close_lists()
            out.append('')
        else:
            close_lists()
            stripped = line.strip()
            if stripped:
                out.append(f'<p>{_inline(stripped)}</p>')

    close_lists()
    return '\n'.join(out)


def _parse_sections(analysis: str) -> list[tuple[str, str]]:
    sections = []
    title = None
    buf: list[str] = []
    for line in analysis.split('\n'):
        if line.startswith('## '):
            if title is not None:
                sections.append((title, '\n'.join(buf)))
            title = line[3:].strip()
            buf = []
        elif title is not None:
            buf.append(line)
    if title is not None:
        sections.append((title, '\n'.join(buf)))
    return sections


def _render_tldr(sections: list[tuple[str, str]]) -> str:
    bullets = []
    bullet_re = re.compile(r'^[\*\-\d][\.\s]+(.+)')
    for _, content in sections:
        for line in content.split('\n'):
            m = bullet_re.match(line.strip())
            if m:
                text = re.sub(r'\*\*(.+?)\*\*', r'\1', m.group(1)).strip()
                text = text[:130] + ('…' if len(text) > 130 else '')
                bullets.append(text)
                break
        if len(bullets) >= 3:
            break
    if not bullets:
        return ''
    items = ''.join(f'<div class="tldr-item">{_html.escape(b)}</div>' for b in bullets)
    return f'''<div class="tldr-banner">
  <div class="tldr-label">Key Insights</div>
  <div class="tldr-items">{items}</div>
</div>'''


def _render_sentiment_rationale(sections: list[tuple[str, str]]) -> str:
    for title, content in sections:
        if 'sentiment' in title.lower():
            for para in content.split('\n\n'):
                clean = re.sub(r'\*\*(.+?)\*\*', r'\1', para).strip()
                if len(clean) > 30:
                    m = re.match(r'([^.!?]+[.!?])', clean)
                    return _html.escape(m.group(1).strip() if m else clean[:140])
    return 'via Gemini AI analysis'


def _render_tabs(sections: list[tuple[str, str]]) -> str:
    if not sections:
        return ''
    btns = ''
    panes = ''
    for i, (title, content) in enumerate(sections):
        active = ' active' if i == 0 else ''
        btns  += f'<button class="tab-btn{active}" onclick="switchTab({i})">{_html.escape(title)}</button>\n'
        panes += f'<div class="tab-pane{active}" id="tab-{i}">{_md_to_html(content)}</div>\n'
    return f'<div class="tabs">{btns}</div><div id="tabContent">{panes}</div>'


def _parse_sentiment(analysis: str) -> str:
    m = re.search(r'## Overall Sentiment\s*(.*?)(?=\n##|\Z)', analysis, re.DOTALL | re.IGNORECASE)
    if m:
        verdict = m.group(1)[:120].lower()
        if 'positive' in verdict and 'negative' not in verdict and 'mixed' not in verdict:
            return 'Positive'
        if 'negative' in verdict and 'positive' not in verdict and 'mixed' not in verdict:
            return 'Negative'
    return 'Mixed'


def _source_badges(sources: dict) -> str:
    return ''.join(
        f'<span class="badge">{_html.escape(name.capitalize())}</span>'
        for name in sorted(sources)
    )


def _source_bars(sources: dict, total: int) -> str:
    if total == 0:
        return ''
    lines = []
    for name, count in sorted(sources.items()):
        pct   = round(count / total * 100)
        color = _SRC_COLORS.get(name, '#22d3ee')
        lines.append(
            f'<div class="source-row">'
            f'<div class="source-name">'
            f'<span class="src-dot" style="background:{color}"></span>'
            f'{_html.escape(name.capitalize())}'
            f'</div>'
            f'<div class="bar-track"><div class="bar-fill" style="width:{pct}%;background:{color}"></div></div>'
            f'<span class="bar-count">{count}</span></div>'
        )
    return ''.join(lines)


# ── HTML template ─────────────────────────────────────────────────────────────

_HTML = Template("""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Pulse Check</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Syne:wght@600;700;800&family=JetBrains+Mono:wght@400;500&family=DM+Sans:opsz,wght@9..40,400;9..40,500&display=swap" rel="stylesheet" />
  <script src="js/chart.umd.min.js"></script>
  <style>
    /* ── TOKENS ─────────────────────────────────────────────────────────────── */
    :root {
      --bg:          #060b11;
      --card:        #0c1521;
      --card-hi:     #101a28;
      --border:      #18293d;
      --border-hi:   #265080;
      --text:        #dce8f5;    /* 15.9:1 — headings, numbers, primary */
      --text-body:   #8ba3be;    /*  7.6:1 — paragraphs, list items     */
      --text-label:  #6b8aaa;    /*  5.5:1 — small UI labels, meta      */
      --text-dim:    #2a3d52;    /* decorative — dividers, footer        */
      --accent:      #22d3ee;    /* 10.9:1 — data, active states         */
      --accent-dim:  rgba(34,211,238,0.07);
      --accent-glow: rgba(34,211,238,0.18);
      --pos:         #34d399;
      --neg:         #f87171;
      --warn:        #fbbf24;
    }

    /* ── RESET ───────────────────────────────────────────────────────────────── */
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: 'DM Sans', sans-serif;
      font-size: 16px;
      background: var(--bg);
      background-image: radial-gradient(circle, rgba(34,211,238,0.035) 1px, transparent 1px);
      background-size: 32px 32px;
      color: var(--text);
      min-height: 100vh;
      -webkit-font-smoothing: antialiased;
    }

    /* ── HEADER ─────────────────────────────────────────────────────────────── */
    header {
      background: rgba(6,11,17,0.95);
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      border-bottom: 1px solid var(--border);
      padding: 0.875rem 1.5rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
      position: sticky;
      top: 0;
      z-index: 100;
    }
    .header-left { display: flex; align-items: center; gap: 0.75rem; min-width: 0; }
    .header-mark {
      width: 8px; height: 8px; flex-shrink: 0;
      background: var(--accent); border-radius: 50%;
      box-shadow: 0 0 8px var(--accent), 0 0 18px var(--accent-glow);
    }
    header h1 {
      font-family: 'Syne', sans-serif;
      font-size: 0.95rem; font-weight: 700;
      color: var(--text); letter-spacing: -0.01em;
      white-space: nowrap;
    }
    header .meta {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.65rem; color: var(--text-label);
      margin-top: 0.1rem; letter-spacing: 0.03em;
    }
    .badges { display: flex; gap: 0.3rem; flex-wrap: wrap; flex-shrink: 0; }
    .badge {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.6rem; font-weight: 500;
      color: var(--accent);
      border: 1px solid rgba(34,211,238,0.25);
      background: var(--accent-dim);
      padding: 0.18rem 0.5rem; border-radius: 4px;
      letter-spacing: 0.08em; text-transform: uppercase;
      white-space: nowrap;
    }

    /* ── KEY INSIGHTS (inside Intelligence Report card) ─────────────────────── */
    .tldr-banner {
      background: rgba(34,211,238,0.05);
      border: 1px solid rgba(34,211,238,0.15);
      border-radius: 8px;
      padding: 1rem 1.25rem;
      margin-bottom: 1.5rem;
    }
    .tldr-label {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.6rem; font-weight: 500;
      color: var(--accent); letter-spacing: 0.12em;
      text-transform: uppercase; margin-bottom: 0.625rem;
    }
    .tldr-items { display: flex; flex-direction: column; gap: 0.5rem; }
    .tldr-item {
      font-size: 0.845rem; color: var(--text-body);
      display: flex; align-items: baseline; gap: 0.5rem;
      line-height: 1.6;
    }
    .tldr-item::before { content: '▸'; color: var(--accent); flex-shrink: 0; font-size: 0.7rem; }

    /* ── LAYOUT ──────────────────────────────────────────────────────────────── */
    main { max-width: 1100px; margin: 1.75rem auto; padding: 0 1.5rem; }

    @keyframes fadeUp {
      from { opacity: 0; transform: translateY(10px); }
      to   { opacity: 1; transform: translateY(0); }
    }

    /* ── TOPIC HERO ─────────────────────────────────────────────────────────── */
    .topic-hero {
      background: linear-gradient(120deg, rgba(34,211,238,0.09) 0%, rgba(34,211,238,0.02) 50%, transparent 100%);
      border: 1px solid rgba(34,211,238,0.2);
      border-radius: 12px;
      padding: 1.5rem 1.5rem 1.5rem 1.875rem;
      margin-bottom: 1.25rem;
      animation: fadeUp 0.35s ease both;
      position: relative; overflow: hidden;
    }
    .topic-hero::before {
      content: ''; position: absolute; top: 0; left: 0;
      width: 3px; height: 100%;
      background: linear-gradient(180deg, var(--accent) 0%, rgba(34,211,238,0.2) 100%);
    }
    .topic-hero-label {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.6rem; font-weight: 500;
      color: var(--accent); letter-spacing: 0.15em;
      text-transform: uppercase; margin-bottom: 0.5rem;
    }
    .topic-hero-value {
      font-family: 'Syne', sans-serif;
      font-size: 1.35rem; font-weight: 700;
      color: var(--text); line-height: 1.25;
      text-transform: capitalize; letter-spacing: -0.01em;
    }
    .topic-hero-meta {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.63rem; color: var(--text-label);
      margin-top: 0.625rem; letter-spacing: 0.02em;
    }

    /* ── STAT CARDS ─────────────────────────────────────────────────────────── */
    .cards {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 1rem; margin-bottom: 1.25rem;
    }
    .card {
      background: var(--card); border: 1px solid var(--border);
      border-radius: 10px; padding: 1.375rem 1.5rem;
      animation: fadeUp 0.4s ease both;
      transition: border-color 0.2s, background 0.2s;
    }
    .card:nth-child(1) { animation-delay: 0.05s; }
    .card:nth-child(2) { animation-delay: 0.10s; }
    .card:nth-child(3) { animation-delay: 0.15s; }
    .card:hover { border-color: var(--border-hi); background: var(--card-hi); }

    /* Typography hierarchy within cards */
    .card-label {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.6rem; font-weight: 500;
      color: var(--text-label);
      text-transform: uppercase; letter-spacing: 0.1em;
      margin-bottom: 0.75rem;
    }
    .card-value {
      font-family: 'Syne', sans-serif;
      font-size: 2.75rem; font-weight: 800;
      color: var(--accent); line-height: 1;
      letter-spacing: -0.02em;
    }
    .card-sub {
      font-size: 0.75rem; color: var(--text-label);
      margin-top: 0.5rem; letter-spacing: 0.01em;
    }

    /* Source bars */
    .source-bar { margin-top: 0.25rem; }
    .source-row { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.625rem; }
    .source-name {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.62rem; color: var(--text-label);
      text-transform: uppercase; letter-spacing: 0.04em;
      width: 88px; flex-shrink: 0;
      display: flex; align-items: center; gap: 0.35rem;
    }
    .src-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
    .bar-count {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.62rem; font-weight: 500;
      color: var(--text-body);
      min-width: 24px; text-align: right;
    }
    .bar-track { flex: 1; background: var(--border); border-radius: 2px; height: 4px; }
    .bar-fill  { height: 4px; border-radius: 2px; }

    /* Sentiment card */
    .sentiment-badge {
      display: inline-flex; align-items: center;
      margin-top: 0.5rem;
      padding: 0.3rem 0.75rem; border-radius: 4px; border: 1px solid;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.7rem; font-weight: 500;
      letter-spacing: 0.1em; text-transform: uppercase;
    }
    .sentiment-rationale {
      font-size: 0.78rem; color: var(--text-body);
      margin-top: 0.625rem; line-height: 1.6;
    }

    /* ── CHARTS ROW ─────────────────────────────────────────────────────────── */
    .charts-row {
      display: grid;
      grid-template-columns: 3fr 2fr;
      gap: 1rem; margin-bottom: 1rem;
    }
    .charts-row .panel { margin-bottom: 0; }
    #sourceChart { max-height: 220px; }

    /* ── PANELS ──────────────────────────────────────────────────────────────── */
    .panel {
      background: var(--card); border: 1px solid var(--border);
      border-radius: 10px; padding: 1.375rem 1.5rem;
      margin-bottom: 1rem;
      animation: fadeUp 0.4s ease both;
      transition: border-color 0.2s;
    }
    .panel:hover { border-color: var(--border-hi); }
    .panel.analysis { padding: 1.5rem; margin-bottom: 0; }

    .section-label {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.6rem; font-weight: 500;
      color: var(--text-label);
      text-transform: uppercase; letter-spacing: 0.1em;
      margin-bottom: 1.25rem;
      display: flex; align-items: center; gap: 0.75rem;
    }
    .section-label::after {
      content: ''; flex: 1; height: 1px;
      background: linear-gradient(90deg, var(--border) 0%, transparent 100%);
    }

    /* ── TABS ────────────────────────────────────────────────────────────────── */
    .tabs {
      display: flex; gap: 0;
      border-bottom: 1px solid var(--border); margin-bottom: 1.5rem;
      overflow-x: auto; -webkit-overflow-scrolling: touch;
      scrollbar-width: none;
    }
    .tabs::-webkit-scrollbar { display: none; }
    .tab-btn {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.63rem; font-weight: 500;
      text-transform: uppercase; letter-spacing: 0.07em;
      color: var(--text-label);
      background: none; border: none;
      border-bottom: 2px solid transparent;
      padding: 0.625rem 1rem 0.75rem;
      cursor: pointer; white-space: nowrap;
      transition: color 0.15s, border-color 0.15s;
      margin-bottom: -1px;
      min-height: 44px; /* touch target */
    }
    .tab-btn:hover { color: var(--text-body); }
    .tab-btn.active { color: var(--accent); border-bottom-color: var(--accent); }
    .tab-pane { display: none; }
    .tab-pane.active { display: block; }

    /* ── ANALYSIS CONTENT HIERARCHY ─────────────────────────────────────────── */
    /* h2: section title — highest weight in content */
    .tab-pane h2 {
      font-family: 'Syne', sans-serif;
      font-size: 0.95rem; font-weight: 700;
      color: var(--text);
      margin: 1.5rem 0 0.625rem;
      padding-bottom: 0.5rem;
      border-bottom: 1px solid var(--border);
      letter-spacing: -0.01em;
    }
    .tab-pane h2:first-child { margin-top: 0; }

    /* h3: subsection — medium weight */
    .tab-pane h3 {
      font-family: 'Syne', sans-serif;
      font-size: 0.85rem; font-weight: 600;
      color: var(--text); /* same hue, distinguished by size */
      margin: 1.125rem 0 0.375rem;
    }

    /* Body copy — legible, ample line height */
    .tab-pane p {
      font-size: 0.875rem; color: var(--text-body);
      line-height: 1.9; margin-bottom: 0.75rem;
    }

    /* Lists */
    .tab-pane ul, .tab-pane ol { padding-left: 1.25rem; margin-bottom: 0.875rem; }
    .tab-pane li {
      font-size: 0.875rem; color: var(--text-body);
      line-height: 1.8; margin-bottom: 0.25rem;
    }
    .tab-pane li::marker { color: var(--accent); }

    /* Emphasis */
    .tab-pane strong { color: var(--text); font-weight: 600; }
    .tab-pane em { color: var(--text-body); font-style: italic; }

    /* Inline code */
    .tab-pane code {
      font-family: 'JetBrains Mono', monospace; font-size: 0.8em;
      background: rgba(34,211,238,0.08); color: var(--accent);
      padding: 0.1em 0.45em; border-radius: 4px;
      border: 1px solid rgba(34,211,238,0.15);
    }
    .tab-pane hr { border: none; border-top: 1px solid var(--border); margin: 1.25rem 0; }

    /* ── FOOTER ──────────────────────────────────────────────────────────────── */
    footer {
      text-align: center;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.6rem; color: var(--text-dim);
      padding: 2.5rem 1.5rem;
      letter-spacing: 0.08em; text-transform: uppercase;
      border-top: 1px solid var(--border);
      margin-top: 2rem;
    }

    /* ── RESPONSIVE ─────────────────────────────────────────────────────────── */
    @media (max-width: 640px) {
      header { padding: 0.75rem 1rem; }
      .badges { display: none; }
      main { padding: 0 1rem; margin-top: 1.25rem; }
      .tldr-banner { padding: 0.75rem 1rem; }
      .tldr-item { max-width: 100%; }
      .cards { grid-template-columns: 1fr; gap: 0.75rem; }
      .charts-row { grid-template-columns: 1fr; }
      .card-value { font-size: 2.25rem; }
      .topic-hero { padding: 1.25rem 1.25rem 1.25rem 1.5rem; }
      .topic-hero-value { font-size: 1.1rem; }
      .panel { padding: 1.125rem; }
      .panel.analysis { padding: 1.125rem; }
      .tab-btn { padding: 0.625rem 0.75rem 0.75rem; font-size: 0.6rem; }
    }
    @media (min-width: 641px) and (max-width: 880px) {
      .cards { grid-template-columns: repeat(2, 1fr); }
      .charts-row { grid-template-columns: 1fr; }
      main { padding: 0 1.25rem; }
    }
  </style>
</head>
<body>

<header>
  <div class="header-left">
    <div class="header-mark"></div>
    <div>
      <h1>Pulse Check</h1>
      <p class="meta">$week_id &nbsp;/&nbsp; $generated_at</p>
    </div>
  </div>
  <div class="badges">$source_badges</div>
</header>

<main>
  <div class="topic-hero">
    <div class="topic-hero-label">Monitoring Topic</div>
    <div class="topic-hero-value">$topic</div>
    <div class="topic-hero-meta">$week_id &nbsp;&bull;&nbsp; $generated_at &nbsp;&bull;&nbsp; $source_names</div>
  </div>

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
      <div class="sentiment-rationale">$sentiment_rationale</div>
    </div>
  </div>

  <div class="charts-row">
    <div class="panel">
      <div class="section-label">Weekly Review Volume</div>
      <canvas id="volumeChart" height="110"></canvas>
    </div>
    <div class="panel">
      <div class="section-label">Source Distribution</div>
      <canvas id="sourceChart"></canvas>
    </div>
  </div>

  <div class="panel" id="themesPanel">
    <div class="section-label">Top Themes</div>
    <canvas id="themesChart" height="150"></canvas>
  </div>

  <div class="panel analysis">
    <div class="section-label">Intelligence Report</div>
    $tldr_html
    $tabs_html
  </div>
</main>

<footer>Pulse Check &nbsp;/&nbsp; $generated_at &nbsp;&bull;&nbsp; Powered by Gemini AI</footer>

<script>
  function switchTab(idx) {
    var btns  = document.querySelectorAll('.tab-btn');
    var panes = document.querySelectorAll('.tab-pane');
    btns.forEach(function(b)  { b.classList.remove('active'); });
    panes.forEach(function(p) { p.classList.remove('active'); });
    if (btns[idx])  btns[idx].classList.add('active');
    if (panes[idx]) panes[idx].classList.add('active');
  }

  if (typeof Chart !== 'undefined') {
    Chart.defaults.color = '#6b8aaa';
    Chart.defaults.borderColor = '#1a2535';
    Chart.defaults.font.family = 'JetBrains Mono';
    Chart.defaults.font.size = 10;

    var tip = {
      backgroundColor: '#0f1520', borderColor: '#1a2535', borderWidth: 1,
      titleColor: '#22d3ee', bodyColor: '#c8d8e8', padding: 10,
    };

    new Chart(document.getElementById('volumeChart'), {
      type: 'bar',
      data: {
        labels: $weekly_labels,
        datasets: [{ label: 'Reviews', data: $weekly_counts,
          backgroundColor: 'rgba(34,211,238,0.55)', borderColor: '#22d3ee',
          borderWidth: 1, borderRadius: 3, borderSkipped: false }]
      },
      options: { responsive: true,
        plugins: { legend: { display: false }, tooltip: tip },
        scales: {
          y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: '#1a2535' } },
          x: { grid: { display: false } }
        }
      }
    });

    var srcData   = $source_distribution;
    var srcNames  = Object.keys(srcData);
    var srcCounts = srcNames.map(function(k) { return srcData[k]; });
    var srcColorMap = { reddit: '#ff6314', hackernews: '#fb923c', capterra: '#34d399' };
    var srcColors = srcNames.map(function(k) { return srcColorMap[k] || '#22d3ee'; });

    new Chart(document.getElementById('sourceChart'), {
      type: 'doughnut',
      data: {
        labels: srcNames.map(function(n) { return n.charAt(0).toUpperCase() + n.slice(1); }),
        datasets: [{ data: srcCounts,
          backgroundColor: srcColors.map(function(c) { return c + 'cc'; }),
          borderColor: srcColors, borderWidth: 2, hoverOffset: 6 }]
      },
      options: { responsive: true, maintainAspectRatio: true, aspectRatio: 1.4, cutout: '68%',
        plugins: { legend: { display: true, position: 'bottom',
          labels: { padding: 14, boxWidth: 10 } }, tooltip: tip }
      }
    });

    var themeLabels = $theme_labels;
    var panel = document.getElementById('themesPanel');
    if (themeLabels.length) {
      var themeColors = ['#34d399','#22d3ee','#818cf8','#f472b6','#fbbf24','#fb923c','#f87171'];
      var weights = themeLabels.map(function(_, i) { return themeLabels.length - i; });
      new Chart(document.getElementById('themesChart'), {
        type: 'bar',
        data: {
          labels: themeLabels,
          datasets: [{ data: weights,
            backgroundColor: themeColors.slice(0, themeLabels.length).map(function(c) { return c + 'bb'; }),
            borderColor: themeColors.slice(0, themeLabels.length),
            borderWidth: 1, borderRadius: 3 }]
        },
        options: { indexAxis: 'y', responsive: true,
          plugins: { legend: { display: false }, tooltip: {
            callbacks: { label: function() { return ''; } },
            backgroundColor: '#0f1520', borderColor: '#1a2535', borderWidth: 1,
            titleColor: '#22d3ee', bodyColor: '#c8d8e8', padding: 10
          }},
          scales: {
            x: { display: false, beginAtZero: true },
            y: { grid: { display: false }, ticks: { color: '#c8d8e8',
              font: { size: 11, family: 'DM Sans' } } }
          }
        }
      });
    } else {
      if (panel) panel.style.display = 'none';
    }
  } else {
    var p = document.getElementById('themesPanel');
    if (p) p.style.display = 'none';
  }
</script>
</body>
</html>
""")


def _extract_theme_labels(sections: list[tuple[str, str]]) -> list[str]:
    for title, content in sections:
        if 'theme' in title.lower():
            labels = []
            for line in content.split('\n'):
                m = re.match(r'^[\d\*\-]+[\.\s]+(.+)', line.strip())
                if m:
                    raw = re.sub(r'\*\*(.+?)\*\*', r'\1', m.group(1))
                    label = re.split(r'[—:\-\(]', raw)[0].strip()
                    if label:
                        labels.append(label[:45])
                if len(labels) >= 7:
                    break
            return labels
    return []


def write_dashboard(week_id: str, analysis: str, stats: dict, topic: str = '') -> str:
    os.makedirs(PUBLIC_DIR, exist_ok=True)
    output_path = os.path.join(PUBLIC_DIR, 'index.html')

    weekly  = fetch_weekly_counts()
    labels  = [w['week_id'] for w in weekly[-8:]]
    counts  = [w['count']   for w in weekly[-8:]]

    sentiment   = _parse_sentiment(analysis)
    total       = stats.get('total', 0)
    sources     = stats.get('sources', {})
    sections    = _parse_sections(analysis)
    source_names = ' / '.join(n.capitalize() for n in sorted(sources))

    html = _HTML.safe_substitute(
        week_id=week_id,
        generated_at=datetime.now().strftime('%Y-%m-%d %H:%M'),
        topic=_html.escape(topic),
        source_names=_html.escape(source_names),
        source_badges=_source_badges(sources),
        total=total,
        source_bars=_source_bars(sources, total),
        sentiment=sentiment,
        sentiment_color=_SENTIMENT_COLORS.get(sentiment, '#d97706'),
        sentiment_rationale=_render_sentiment_rationale(sections),
        tldr_html=_render_tldr(sections),
        tabs_html=_render_tabs(sections),
        weekly_labels=json.dumps(labels),
        weekly_counts=json.dumps(counts),
        source_distribution=json.dumps(sources),
        theme_labels=json.dumps(_extract_theme_labels(sections)),
    )

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    logger.info('Dashboard written to %s', output_path)
    return output_path
