import logging
from typing import List
from sqlalchemy.orm import Session
from app.models import models
from app.crud import crud
from app.schemas import schemas

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

import json

def check_if_already_posted_to_subreddit(db: Session, lead_id: int, generated_title: str, target_subreddit: str) -> bool:
    """
    Check if a specific generated post (by lead_id and generated_title) has already been posted
    to the given target_subreddit.
    """
    existing_post = db.query(models.RedditPost).filter(
        models.RedditPost.lead_id == lead_id,
        models.RedditPost.generated_title == generated_title,
        models.RedditPost.is_posted == True
    ).first()

    if existing_post and existing_post.subreddits_list and target_subreddit in existing_post.subreddits_list:
        logging.warning(f"Post (Lead ID: {lead_id}, Title: '{generated_title}') already posted to r/{target_subreddit}. Skipping duplicate.")
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

def mark_subreddit_as_posted(db: Session, post_id: int, target_subreddit: str, post_update_schema: schemas.RedditPostUpdate):
    """
    Marks a specific subreddit as posted for a given RedditPost and updates other relevant fields.
    """
    db_post = crud.get_reddit_post(db, post_id)
    if not db_post:
        logging.error(f"Reddit Post with ID {post_id} not found for marking subreddit as posted.")
        return

    # Update the subreddits list
    current_subreddits = db_post.subreddits_list if db_post.subreddits_list else []
    if target_subreddit not in current_subreddits:
        current_subreddits.append(target_subreddit)
        db_post.subreddits = json.dumps(current_subreddits)
    
    # Update other fields from the schema
    db_post.title = post_update_schema.title
    db_post.content = post_update_schema.content
    db_post.score = post_update_schema.score
    db_post.num_comments = post_update_schema.num_comments
    db_post.author = post_update_schema.author
    db_post.url = post_update_schema.url
    # The 'subreddit' field in the schema was intended to represent the *last* subreddit posted to,
    # but the model no longer has a singular 'subreddit' column. The 'subreddits' column (plural)
    # now stores the list of all subreddits this post has been made to.
    # We will not assign post_update_schema.subreddit to db_post.subreddit as it no longer exists.
    db_post.generated_title = post_update_schema.generated_title
    db_post.generated_content = post_update_schema.generated_content
    db_post.is_posted = post_update_schema.is_posted
    db_post.ai_generated = post_update_schema.ai_generated
    db_post.posted_url = post_update_schema.posted_url

    db.add(db_post)
    db.commit()
    db.refresh(db_post)
    logging.info(f"Reddit Post ID {post_id} marked as posted to r/{target_subreddit}.")

def get_most_recent_posted_post(db: Session):
    """Get the most recent posted post."""
    return db.query(models.RedditPost).filter(
        models.RedditPost.is_posted == True
    ).order_by(models.RedditPost.id.desc()).first()

def save_reddit_comments(db: Session, reddit_post_db_id: int, comments: List[schemas.RedditCommentCreate]):
    """Saves fetched Reddit comments to the database."""
    saved_count = 0
    for comment_data in comments:
        try:
            db_comment = db.query(models.RedditComment).filter(
                models.RedditComment.reddit_post_db_id == reddit_post_db_id,
                models.RedditComment.comment_id == comment_data.comment_id
            ).first()

            if not db_comment:
                new_comment = models.RedditComment(
                    comment_id=comment_data.comment_id,
                    post_id=comment_data.post_id,
                    author=comment_data.author,
                    content=comment_data.content,
                    score=comment_data.score,
                    permalink=comment_data.permalink,
                    reddit_post_db_id=reddit_post_db_id
                )
                db.add(new_comment)
                saved_count += 1
            else:
                logging.debug(f"Skipping duplicate comment: {comment_data.comment_id} (Author: {comment_data.author})")
        except Exception as e:
            logging.error(f"Error saving Reddit comment: {e} - Data: {comment_data}")
    db.commit()
    logging.info(f"Successfully saved {saved_count} Reddit comments for Reddit Post DB ID {reddit_post_db_id}.")

def get_reddit_comments_for_post(db: Session, reddit_post_db_id: int) -> List[models.RedditComment]:
    """Retrieves all comments for a given internal Reddit Post ID."""
    return db.query(models.RedditComment).filter(
        models.RedditComment.reddit_post_db_id == reddit_post_db_id
    ).all()

def mark_comment_as_replied(db: Session, reddit_comment_db_id: int, reply_permalink: str, generated_reply_content: str):
    """
    Marks a RedditComment as replied, stores the generated reply content and its permalink.
    """
    db_comment = db.query(models.RedditComment).filter(
        models.RedditComment.id == reddit_comment_db_id
    ).first()

    if not db_comment:
        logging.error(f"Reddit Comment with DB ID {reddit_comment_db_id} not found for marking as replied.")
        return

    db_comment.is_replied = True
    db_comment.ai_generated = True
    db_comment.generated_reply_content = generated_reply_content
    db_comment.permalink = reply_permalink # Update permalink to the reply's permalink

    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)
    logging.info(f"Reddit Comment DB ID {reddit_comment_db_id} marked as replied.")
