from dotenv import load_dotenv
import os

load_dotenv()

SEARCH_QUERIES = {
    "trustpilot": ["data analytics course", "online data training"],
    "reddit": ["r/PowerBI", "r/dataengineering", "r/learnpython"],
}

MAX_REVIEWS_PER_SOURCE = 50
OUTPUT_FORMAT = "markdown"

PROXY_HOST = os.getenv("PROXY_HOST")
PROXY_PORT = os.getenv("PROXY_PORT")
PROXY_USER = os.getenv("PROXY_USER")
PROXY_PASS = os.getenv("PROXY_PASS")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")


MIN_UPVOTES = 5
MIN_WORD_COUNT = 20
BATCH_SIZE = 30

# Guardrails
MAX_REVIEWS_FOR_ANALYSIS = 150   # hard cap on reviews sent to Claude per run
MAX_TOKEN_BUDGET = 100_000       # input + output tokens allowed per run before stopping
INTER_BATCH_DELAY = 2            # seconds to wait between API calls
