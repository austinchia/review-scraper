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
