import logging
from typing import List
from sqlalchemy.orm import Session
from app.models import models
from app.crud import crud
from app.schemas import schemas

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def check_if_already_posted(db: Session, lead_id: int, subreddit_name: str) -> bool:
    """Check if we've already posted to this subreddit for this lead."""
    existing_post = db.query(models.RedditPost).filter(
        models.RedditPost.lead_id == lead_id,
        models.RedditPost.subreddit == subreddit_name,
        models.RedditPost.is_posted == True
    ).first()
    
    if existing_post:
        logging.warning(f"Already posted to r/{subreddit_name} for Lead ID {lead_id}. Skipping duplicate.")
        return True
    return False

def _save_reddit_posts(db: Session, lead_id: int, posts: List[schemas.RedditPostCreate]):
    """Saves fetched Reddit posts to the database."""
    saved_count = 0
    for post_data in posts:
        try:
            db_post = db.query(models.RedditPost).filter(
                models.RedditPost.lead_id == lead_id,
                models.RedditPost.url == post_data.url
            ).first()

            if not db_post:
                crud.create_reddit_post(db, post_data, lead_id)
                saved_count += 1
            else:
                logging.debug(f"Skipping duplicate post: {post_data.title} (URL: {post_data.url})")
        except Exception as e:
            logging.error(f"Error saving Reddit post: {e} - Data: {post_data}")
    db.commit()
    logging.info(f"Successfully saved {saved_count} Reddit posts for Lead ID {lead_id}.")

def get_reddit_post_by_id(db: Session, post_id: int):
    """Retrieves a Reddit post by its ID."""
    return crud.get_reddit_post(db, post_id)

def update_reddit_post_in_db(db: Session, post_id: int, post_update_schema: schemas.RedditPostUpdate):
    """Updates a Reddit post in the database."""
    crud.update_reddit_post(db, post_id, post_update_schema)
    db.commit()

def get_most_recent_posted_post(db: Session):
    """Get the most recent posted post."""
    return db.query(models.RedditPost).filter(
        models.RedditPost.is_posted == True
    ).order_by(models.RedditPost.id.desc()).first()
