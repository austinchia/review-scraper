import logging
import praw
from config import REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT, MIN_UPVOTES

logger = logging.getLogger(__name__)


class RedditScraper:
    def __init__(self):
        self.reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent=REDDIT_USER_AGENT,
        )

    def scrape(self, subreddit_name: str, max_posts: int = 50) -> list[dict]:
        sub = subreddit_name.lstrip("r/")
        results = []
        try:
            subreddit = self.reddit.subreddit(sub)
            for post in subreddit.hot(limit=max_posts * 2):
                if len(results) >= max_posts:
                    break
                if post.score < MIN_UPVOTES:
                    continue

                entry = {
                    "source": "reddit",
                    "title": post.title,
                    "text": post.selftext or post.title,
                    "rating": None,
                    "date": str(int(post.created_utc)),
                    "url": f"https://reddit.com{post.permalink}",
                    "subreddit": sub,
                    "score": post.score,
                }
                results.append(entry)

                post.comments.replace_more(limit=0)
                for comment in post.comments[:5]:
                    if comment.score >= MIN_UPVOTES and len(comment.body.split()) >= 10:
                        results.append({
                            "source": "reddit",
                            "title": f"Comment on: {post.title}",
                            "text": comment.body,
                            "rating": None,
                            "date": str(int(comment.created_utc)),
                            "url": f"https://reddit.com{post.permalink}",
                            "subreddit": sub,
                            "score": comment.score,
                        })
                        if len(results) >= max_posts:
                            break

        except Exception as e:
            logger.error("Reddit scrape failed for r/%s: %s", sub, e)

        logger.info("Reddit: collected %d posts/comments from r/%s", len(results), sub)
        return results[:max_posts]
