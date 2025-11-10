import praw
import logging
from app.core.config import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_reddit_instance():
    """Initializes and returns a PRAW Reddit instance with proper user agent."""
    try:
        user_agent = f"python:octopus:v1.0 (by /u/{settings.REDDIT_USERNAME})"
        
        reddit = praw.Reddit(
            client_id=settings.REDDIT_CLIENT_ID,
            client_secret=settings.REDDIT_CLIENT_SECRET,
            user_agent=user_agent,
            username=settings.REDDIT_USERNAME,
            password=settings.REDDIT_PASSWORD,
        )
        reddit.read_only = False
        
        try:
            reddit.user.me()
            logging.info(f"Successfully authenticated as u/{reddit.user.me().name}")
        except Exception as e:
            logging.error(f"Failed to verify Reddit authentication: {e}")
            return None
            
        return reddit
    except Exception as e:
        logging.error(f"Failed to initialize Reddit instance: {e}")
        return None
