import logging
import time
import random
import praw
from typing import List
from app.schemas import schemas

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def fetch_reddit_posts(reddit: praw.Reddit, subreddit_name: str, limit: int = 10) -> List[schemas.RedditPostCreate]:
    """Fetches posts from a specified subreddit."""
    posts_data = []
    try:
        subreddit = reddit.subreddit(subreddit_name)
        
        try:
            rules = subreddit.rules()
            logging.info(f"Found {len(rules)} rules for r/{subreddit_name}. Review them before posting.")
        except Exception:
            logging.debug(f"Could not fetch rules for r/{subreddit_name}.")
        
        time.sleep(random.uniform(2, 5))
        
        top_posts = subreddit.top(time_filter="week", limit=limit)
        for post in top_posts:
            posts_data.append(
                schemas.RedditPostCreate(
                    title=post.title,
                    content=post.selftext,
                    score=post.score,
                    num_comments=post.num_comments,
                    author=str(post.author),
                    url=post.url,
                    subreddit=subreddit_name
                )
            )
        logging.info(f"Successfully fetched {len(posts_data)} posts from r/{subreddit_name}")
    except Exception as e:
        logging.error(f"Could not fetch posts from r/{subreddit_name}. Reason: {e}")
    return posts_data
