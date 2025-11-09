import os
import json
import praw
from dotenv import load_dotenv
import logging
import time
import random

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_reddit_credentials():
    """Loads Reddit API credentials from .env file."""
    load_dotenv()
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    user_agent = os.getenv("REDDIT_USER_AGENT")
    username = os.getenv("REDDIT_USERNAME")
    password = os.getenv("REDDIT_PASSWORD")

    if not all([client_id, client_secret, user_agent, username, password]):
        raise ValueError("One or more Reddit API credentials are not set in the .env file.")
    
    return client_id, client_secret, user_agent, username, password

def get_reddit_instance():
    """Initializes and returns a PRAW Reddit instance."""
    try:
        client_id, client_secret, user_agent, username, password = load_reddit_credentials()
        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
            username=username,
            password=password,
        )
        reddit.read_only = False
        return reddit
    except Exception as e:
        logging.error(f"Failed to initialize Reddit instance: {e}")
        return None

def load_posts_from_file(filename="generated_reddit_posts.json"):
    """Loads posts from a JSON file."""
    try:
        with open(filename, 'r') as f:
            data = json.load(f)
        return data.get("generated_posts", [])
    except FileNotFoundError:
        logging.error(f"Error: The file {filename} was not found.")
        return []
    except json.JSONDecodeError:
        logging.error(f"Error: Could not decode JSON from {filename}.")
        return []

def post_to_reddit(reddit, subreddit_name, title, content):
    """Posts content to a specified subreddit."""
    try:
        subreddit = reddit.subreddit(subreddit_name)
        subreddit.submit(title, selftext=content)
        logging.info(f"Successfully posted to r/{subreddit_name}: '{title}'")
        return True
    except Exception as e:
        logging.error(f"Failed to post to r/{subreddit_name}: {e}")
        return False

def main():
    """Main function to execute the Reddit posting script."""
    reddit = get_reddit_instance()
    if not reddit:
        return

    posts = load_posts_from_file()
    if not posts:
        logging.warning("No posts found to share.")
        return

    subreddits = ["trucking", "freight", "logistics", "smallbusiness"]
    
    # Ensure we don't try to post more than we have subreddits
    if len(posts) > len(subreddits):
        logging.warning("More posts than subreddits. Some posts will not be shared.")
        posts = posts[:len(subreddits)]

    for i, post in enumerate(posts):
        title = post.get("title")
        content = post.get("content")
        if not title or not content:
            logging.warning("Skipping a post due to missing title or content.")
            continue
        
        # Assign each post to a different subreddit
        subreddit_name = subreddits[i]
        post_to_reddit(reddit, subreddit_name, title, content)
        
        # Add a random delay to mimic human behavior
        delay = random.randint(10, 30)
        logging.info(f"Waiting for {delay} seconds before the next post...")
        time.sleep(delay)

if __name__ == "__main__":
    main()
