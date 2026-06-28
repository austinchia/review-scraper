import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

DIGESTS_DIR = os.path.join(os.path.dirname(__file__), "..", "digests")


def write_digest(week_id: str, analysis: str, stats: dict) -> str:
    os.makedirs(DIGESTS_DIR, exist_ok=True)
    filename = f"{week_id}.md"
    filepath = os.path.join(DIGESTS_DIR, filename)

    date_str = datetime.now().strftime("%Y-%m-%d")
    sources = ", ".join(sorted(stats.get("sources", {}).keys())).upper() or "N/A"
    total = stats.get("total", 0)

    raw_stats_lines = []
    for source, count in sorted(stats.get("sources", {}).items()):
        label = "posts/comments" if source == "reddit" else "reviews"
        raw_stats_lines.append(f"- {source.capitalize()}: {count} {label}")

    raw_stats = "\n".join(raw_stats_lines) if raw_stats_lines else "- No data"

    content = f"""# Weekly Review Digest

**Week of:** {date_str} ({week_id})
**Sources:** {sources}
**Reviews analysed:** {total}

---

{analysis}

---

## Raw Stats

{raw_stats}

---

*Generated automatically by the Review Mining Pipeline*
"""

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info("Digest written to %s", filepath)
    return filepath
