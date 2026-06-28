import logging
import anthropic
from config import ANTHROPIC_API_KEY, BATCH_SIZE

logger = logging.getLogger(__name__)

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

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


def _format_reviews(reviews: list[dict]) -> str:
    lines = []
    for i, r in enumerate(reviews, 1):
        source = r.get("source", "unknown")
        rating = f" | Rating: {r['rating']}/5" if r.get("rating") else ""
        title = f" | Title: {r['title']}" if r.get("title") else ""
        lines.append(f"[{i}] [{source.upper()}{rating}{title}]\n{r['text']}\n")
    return "\n".join(lines)


def analyse(reviews: list[dict], topic: str = "data analytics tools") -> str:
    if not reviews:
        return "No reviews to analyse."

    sources = ", ".join(sorted({r.get("source", "unknown") for r in reviews}))
    batches = [reviews[i:i + BATCH_SIZE] for i in range(0, len(reviews), BATCH_SIZE)]

    if len(batches) == 1:
        return _call_api(batches[0], sources, topic)

    logger.info("Analysing %d batches of reviews", len(batches))
    batch_outputs = []
    for idx, batch in enumerate(batches, 1):
        logger.info("Processing batch %d/%d (%d reviews)", idx, len(batches), len(batch))
        result = _call_api(batch, sources, topic)
        batch_outputs.append(f"### Batch {idx}\n{result}")

    return _synthesise(batch_outputs)


def _call_api(reviews: list[dict], sources: str, topic: str) -> str:
    review_text = _format_reviews(reviews)
    prompt = USER_PROMPT_TEMPLATE.format(
        n=len(reviews),
        sources=sources,
        topic=topic,
        review_text=review_text,
    )
    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text
    except anthropic.APIError as e:
        logger.error("Anthropic API error: %s", e)
        raise


def _synthesise(batch_outputs: list[str]) -> str:
    prompt = SYNTHESIS_PROMPT.format(batch_outputs="\n\n".join(batch_outputs))
    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text
    except anthropic.APIError as e:
        logger.error("Anthropic synthesis API error: %s", e)
        raise
