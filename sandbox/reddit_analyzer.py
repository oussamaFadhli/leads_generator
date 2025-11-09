import os
import praw
import json
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import List, Dict
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("reddit_analyzer.log"),
        logging.StreamHandler()
    ]
)

load_dotenv()

# Pydantic model for Reddit post data
class RedditPost(BaseModel):
    title: str
    content: str
    score: int
    num_comments: int
    author: str
    url: str
    subreddit: str

# Reddit API credentials from environment variables
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT")

def get_reddit_instance():
    """Initializes and returns a PRAW Reddit instance."""
    if not all([REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT]):
        logging.error("Reddit API credentials are not fully configured in the .env file.")
        raise ValueError("Missing Reddit API credentials in .env file")
    
    return praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=REDDIT_USER_AGENT,
    )

def get_subreddits_from_file(file_path: str) -> List[str]:
    """Reads a JSON file and returns a list of subreddit names."""
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        # Remove 'r/' prefix and duplicates
        return list(set([sub.replace('r/', '') for sub in data.get("related_subreddits", [])]))
    except FileNotFoundError:
        logging.error(f"File not found: {file_path}")
        return []
    except json.JSONDecodeError:
        logging.error(f"Error decoding JSON from file: {file_path}")
        return []

def get_top_posts(reddit: praw.Reddit, subreddit_name: str, limit: int = 10) -> List[RedditPost]:
    """Fetches the top posts from a subreddit in the last week."""
    posts_data = []
    try:
        subreddit = reddit.subreddit(subreddit_name)
        top_posts = subreddit.top(time_filter="week", limit=limit)
        for post in top_posts:
            post_data = RedditPost(
                title=post.title,
                content=post.selftext,
                score=post.score,
                num_comments=post.num_comments,
                author=str(post.author),
                url=post.url,
                subreddit=subreddit_name
            )
            posts_data.append(post_data)
        logging.info(f"Successfully fetched {len(posts_data)} posts from r/{subreddit_name}")
    except Exception as e:
        logging.error(f"Could not fetch posts from r/{subreddit_name}. Reason: {e}")
    return posts_data

def main():
    """Main function to fetch and save Reddit posts."""
    reddit = get_reddit_instance()
    subreddits = get_subreddits_from_file("leads_search_result.json")
    all_posts = []

    for sub in subreddits:
        posts = get_top_posts(reddit, sub)
        all_posts.extend(posts)

    # Convert Pydantic models to dicts for JSON serialization
    all_posts_dict = [post.dict() for post in all_posts]

    with open("reddit_posts.json", "w") as f:
        json.dump(all_posts_dict, f, indent=4)
    
    logging.info(f"Successfully saved {len(all_posts_dict)} posts to reddit_posts.json")

if __name__ == "__main__":
    main()
