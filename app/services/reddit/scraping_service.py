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
                    subreddits=[subreddit_name] # Changed to subreddits (list)
                )
            )
        logging.info(f"Successfully fetched {len(posts_data)} posts from r/{subreddit_name}")
    except Exception as e:
        logging.error(f"Could not fetch posts from r/{subreddit_name}. Reason: {e}")
    return posts_data

async def fetch_comments_from_post_url(reddit: praw.Reddit, post_url: str) -> List[schemas.RedditCommentCreate]:
    """Fetches top-level comments from a specified Reddit post URL."""
    comments_data = []
    try:
        submission = reddit.submission(url=post_url)
        submission.comments.replace_more(limit=0) # Flatten comment tree, limit=0 means only top-level
        
        time.sleep(random.uniform(2, 5))

        for comment in submission.comments.list():
            if comment.author and comment.body: # Ensure comment has an author and content
                comments_data.append(
                    schemas.RedditCommentCreate(
                        comment_id=comment.id,
                        post_id=submission.id,
                        author=str(comment.author),
                        content=comment.body,
                        score=comment.score,
                        permalink=comment.permalink
                    )
                )
        logging.info(f"Successfully fetched {len(comments_data)} top-level comments from {post_url}")
    except Exception as e:
        logging.error(f"Could not fetch comments from {post_url}. Reason: {e}")
    return comments_data
