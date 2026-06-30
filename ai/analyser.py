import logging
import time
from google import genai
from google.genai import errors as gerrors
from config import (
    GEMINI_API_KEY,
    BATCH_SIZE,
    MAX_REVIEWS_FOR_ANALYSIS,
    MAX_TOKEN_BUDGET,
    INTER_BATCH_DELAY,
)

logger = logging.getLogger(__name__)

_client = None  # initialised lazily on first call
_MODEL  = "gemini-2.5-flash"


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is not set. Add it to your .env file.")
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client

_SYSTEM = "You are an analytical assistant. Extract structured insights from customer reviews and online discussions."

# Gemini 1.5 Flash pricing (free tier: $0; paid tier rates shown for reference)
_INPUT_COST_PER_TOKEN  = 0.075 / 1_000_000
_OUTPUT_COST_PER_TOKEN = 0.30  / 1_000_000

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

    def record(self, input_tokens: int, output_tokens: int):
        self.input_tokens  += input_tokens
        self.output_tokens += output_tokens
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
            "API usage -- calls: %d | tokens: %d in / %d out | est. cost: $%.4f",
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
    retries: int = 8,
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
            response = _get_client().models.generate_content(
                model=_MODEL,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    system_instruction=_SYSTEM,
                    max_output_tokens=2048,
                ),
            )
            usage = response.usage_metadata
            in_tok  = (usage.prompt_token_count or 0) if usage else 0
            out_tok = (usage.candidates_token_count or 0) if usage else 0
            tracker.record(in_tok, out_tok)
            logger.info(
                "Batch call -- %d in / %d out tokens (run total: %d / budget: %d)",
                in_tok, out_tok, tracker.total_tokens, MAX_TOKEN_BUDGET,
            )
            return response.text or ""
        except (gerrors.ClientError, gerrors.ServerError) as e:
            code = str(e)
            if "429" in code or "503" in code or "RESOURCE_EXHAUSTED" in code or "UNAVAILABLE" in code or "quota" in code.lower():
                logger.warning("Retrying in %ds — %s (attempt %d/%d)", delay, code[:80], attempt + 1, retries)
                time.sleep(delay)
                delay *= 2
            else:
                logger.error("Gemini API error: %s", e)
                raise
    raise RuntimeError(f"All {retries} API attempts failed (rate limited)")


def _synthesise(batch_outputs: list[str], tracker: _UsageTracker) -> str:
    prompt = SYNTHESIS_PROMPT.format(batch_outputs="\n\n".join(batch_outputs))
    delay = 5
    for attempt in range(8):
        try:
            response = _get_client().models.generate_content(
                model=_MODEL,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    system_instruction=_SYSTEM,
                    max_output_tokens=2048,
                ),
            )
            usage = response.usage_metadata
            in_tok  = (usage.prompt_token_count or 0) if usage else 0
            out_tok = (usage.candidates_token_count or 0) if usage else 0
            tracker.record(in_tok, out_tok)
            return response.text or ""
        except (gerrors.ClientError, gerrors.ServerError) as e:
            code = str(e)
            if "429" in code or "503" in code or "RESOURCE_EXHAUSTED" in code or "UNAVAILABLE" in code or "quota" in code.lower():
                logger.warning("Rate limited on synthesis -- retrying in %ds", delay)
                time.sleep(delay)
                delay *= 2
            else:
                logger.error("Gemini synthesis API error: %s", e)
                raise
    raise RuntimeError("Synthesis failed after retries")


def analyse(reviews: list[dict], topic: str = "data analytics tools") -> str:
    if not reviews:
        return "No reviews to analyse."

    if len(reviews) > MAX_REVIEWS_FOR_ANALYSIS:
        logger.warning(
            "Review count (%d) exceeds MAX_REVIEWS_FOR_ANALYSIS (%d) -- truncating",
            len(reviews), MAX_REVIEWS_FOR_ANALYSIS,
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
                "Token budget (%d) reached after %d/%d batches -- stopping early",
                MAX_TOKEN_BUDGET, idx - 1, len(batches),
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
