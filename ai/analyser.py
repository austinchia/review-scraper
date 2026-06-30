import logging
import time
import anthropic
from config import (
    ANTHROPIC_API_KEY,
    BATCH_SIZE,
    MAX_REVIEWS_FOR_ANALYSIS,
    MAX_TOKEN_BUDGET,
    INTER_BATCH_DELAY,
)

logger = logging.getLogger(__name__)

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# Claude Sonnet 4.6 pricing (USD per token)
_INPUT_COST_PER_TOKEN  = 3.00  / 1_000_000
_OUTPUT_COST_PER_TOKEN = 15.00 / 1_000_000

SYSTEM_PROMPT = "You are an analytical assistant. Extract structured insights from customer reviews and online discussions."

USER_PROMPT_TEMPLATE = """Here are {n} reviews/posts collected from {sources} this week about {topic}.

Your task:
1. Identify the top 5 recurring themes (positive and negative)
2. Summarise the overall sentiment (positive / mixed / negative) with a brief rationale
3. Flag any emerging or unusual signals not seen in typical reviews
4. Note any specific product features, competitors, or pain points mentioned repeatedly

Return your response in structured Markdown with clear headings.

Reviews:
{review_text}"""

SYNTHESIS_PROMPT = """You have been given analysis from multiple batches of reviews. Synthesise them into a single cohesive analysis.

Remove duplicates across batches, prioritise the most prominent themes, and produce a final structured Markdown report with these sections:
## Top Themes
## Overall Sentiment
## Emerging Signals
## Notable Pain Points & Features

Batch analyses:
{batch_outputs}"""


class _UsageTracker:
    def __init__(self):
        self.input_tokens = 0
        self.output_tokens = 0
        self.api_calls = 0

    def record(self, usage):
        self.input_tokens  += usage.input_tokens
        self.output_tokens += usage.output_tokens
        self.api_calls     += 1

    @property
    def total_tokens(self):
        return self.input_tokens + self.output_tokens

    @property
    def estimated_cost(self):
        return (
            self.input_tokens  * _INPUT_COST_PER_TOKEN +
            self.output_tokens * _OUTPUT_COST_PER_TOKEN
        )

    def log_summary(self):
        logger.info(
            "API usage — calls: %d | tokens: %d in / %d out | est. cost: $%.4f",
            self.api_calls,
            self.input_tokens,
            self.output_tokens,
            self.estimated_cost,
        )

    def over_budget(self):
        return self.total_tokens >= MAX_TOKEN_BUDGET


def _format_reviews(reviews: list[dict]) -> str:
    lines = []
    for i, r in enumerate(reviews, 1):
        source = r.get("source", "unknown")
        rating = f" | Rating: {r['rating']}/5" if r.get("rating") else ""
        title  = f" | Title: {r['title']}"    if r.get("title")  else ""
        lines.append(f"[{i}] [{source.upper()}{rating}{title}]\n{r['text']}\n")
    return "\n".join(lines)


def _call_api(
    reviews: list[dict],
    sources: str,
    topic: str,
    tracker: _UsageTracker,
    retries: int = 4,
) -> str:
    review_text = _format_reviews(reviews)
    prompt = USER_PROMPT_TEMPLATE.format(
        n=len(reviews),
        sources=sources,
        topic=topic,
        review_text=review_text,
    )
    delay = 5
    for attempt in range(retries):
        try:
            message = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            tracker.record(message.usage)
            logger.info(
                "Batch call — %d in / %d out tokens (run total: %d / budget: %d)",
                message.usage.input_tokens,
                message.usage.output_tokens,
                tracker.total_tokens,
                MAX_TOKEN_BUDGET,
            )
            return message.content[0].text
        except anthropic.RateLimitError:
            logger.warning("Rate limited — retrying in %ds (attempt %d/%d)", delay, attempt + 1, retries)
            time.sleep(delay)
            delay *= 2
        except anthropic.APIError as e:
            logger.error("Anthropic API error: %s", e)
            raise
    raise RuntimeError(f"All {retries} API attempts failed (rate limited)")


def _synthesise(batch_outputs: list[str], tracker: _UsageTracker) -> str:
    prompt = SYNTHESIS_PROMPT.format(batch_outputs="\n\n".join(batch_outputs))
    delay = 5
    for attempt in range(4):
        try:
            message = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            tracker.record(message.usage)
            return message.content[0].text
        except anthropic.RateLimitError:
            logger.warning("Rate limited on synthesis — retrying in %ds", delay)
            time.sleep(delay)
            delay *= 2
        except anthropic.APIError as e:
            logger.error("Anthropic synthesis API error: %s", e)
            raise
    raise RuntimeError("Synthesis failed after retries")


def analyse(reviews: list[dict], topic: str = "data analytics tools") -> str:
    if not reviews:
        return "No reviews to analyse."

    # Guardrail: cap reviews before sending to API
    if len(reviews) > MAX_REVIEWS_FOR_ANALYSIS:
        logger.warning(
            "Review count (%d) exceeds MAX_REVIEWS_FOR_ANALYSIS (%d) — truncating",
            len(reviews),
            MAX_REVIEWS_FOR_ANALYSIS,
        )
        reviews = reviews[:MAX_REVIEWS_FOR_ANALYSIS]

    tracker = _UsageTracker()
    sources = ", ".join(sorted({r.get("source", "unknown") for r in reviews}))
    batches = [reviews[i:i + BATCH_SIZE] for i in range(0, len(reviews), BATCH_SIZE)]

    if len(batches) == 1:
        result = _call_api(batches[0], sources, topic, tracker)
        tracker.log_summary()
        return result

    logger.info("Analysing %d batches of reviews", len(batches))
    batch_outputs = []
    for idx, batch in enumerate(batches, 1):
        if tracker.over_budget():
            logger.warning(
                "Token budget (%d) reached after %d/%d batches — stopping early",
                MAX_TOKEN_BUDGET,
                idx - 1,
                len(batches),
            )
            break

        logger.info("Processing batch %d/%d (%d reviews)", idx, len(batches), len(batch))
        result = _call_api(batch, sources, topic, tracker)
        batch_outputs.append(f"### Batch {idx}\n{result}")

        if idx < len(batches):
            time.sleep(INTER_BATCH_DELAY)

    result = _synthesise(batch_outputs, tracker)
    tracker.log_summary()
    return result
