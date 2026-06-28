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

REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", "review-mining-bot/1.0")

MIN_UPVOTES = 5
MIN_WORD_COUNT = 20
BATCH_SIZE = 30
