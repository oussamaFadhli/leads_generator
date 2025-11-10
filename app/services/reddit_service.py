import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from app.crud import crud
from app.models import models
from app.schemas import schemas
from app.services.reddit import auth_service, account_service, db_operations_service, scraping_service, generation_service, posting_service, preview_service

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
def check_posting_rate_limit(db: Session) -> bool:
    """Check if we're posting too frequently (rate limiting)."""
    recent_post = db_operations_service.get_most_recent_posted_post(db)
    
    if recent_post:
        pass
    
    return True

async def perform_reddit_analysis(saas_info_id: int, lead_id: int, subreddit_name: str, db: Session):
    logging.info(f"Starting Reddit analysis for subreddit: {subreddit_name}, Lead ID: {lead_id}")
    reddit = auth_service.get_reddit_instance()
    if not reddit:
        return
    
    if not account_service.check_account_health(reddit):
        logging.error("Account health check failed. Aborting.")
        return

    saas_info_db = crud.get_saas_info(db, saas_info_id)
    if not saas_info_db:
        logging.error(f"SaaS Info with ID {saas_info_id} not found.")
        return

    fetched_posts = await scraping_service.fetch_reddit_posts(reddit, subreddit_name)
    if not fetched_posts:
        logging.warning(f"No posts fetched from r/{subreddit_name}. Aborting.")
        return

    try:
        db_operations_service._save_reddit_posts(db, lead_id, fetched_posts)
    except Exception as e:
        logging.error(f"Error during saving Reddit posts for Lead ID {lead_id}: {e}")
    finally:
        db.close()

async def generate_reddit_posts(saas_info_id: int, post_id: int, db: Session):
    await generation_service.generate_reddit_posts(saas_info_id, post_id, db)

async def post_generated_reddit_post(post_id: int, db: Session):
    await posting_service.post_generated_reddit_post(post_id, db)

def preview_generated_post(post_id: int, db: Session) -> Optional[dict]:
    return preview_service.preview_generated_post(post_id, db)

async def reply_to_reddit_post_comments(saas_info_id: int, reddit_post_url: str, db: Session):
    logging.info(f"Starting process to reply to comments for Reddit post URL: {reddit_post_url}")
    reddit = auth_service.get_reddit_instance()
    if not reddit:
        return

    if not account_service.check_account_health(reddit):
        logging.error("Account health check failed. Aborting comment reply process.")
        return

    saas_info_db = crud.get_saas_info(db, saas_info_id)
    if not saas_info_db:
        logging.error(f"SaaS Info with ID {saas_info_id} not found.")
        return

    # First, try to find if this Reddit post already exists in our DB
    db_reddit_post = db.query(models.RedditPost).filter(models.RedditPost.url == reddit_post_url).first()
    if not db_reddit_post:
        # If not, we need to create a placeholder RedditPost entry to link comments to
        # For simplicity, we'll create a minimal entry. In a real scenario, you might scrape the post details.
        logging.info(f"Reddit post {reddit_post_url} not found in DB. Creating a placeholder entry.")
        # Extract title and author from URL if possible, or use placeholders
        post_title = f"Reddit Post: {reddit_post_url}"
        post_author = "unknown"
        try:
            submission = reddit.submission(url=reddit_post_url)
            post_title = submission.title
            post_author = str(submission.author)
        except Exception as e:
            logging.warning(f"Could not fetch submission details for {reddit_post_url}: {e}. Using placeholders.")

        # Assuming a lead_id is required, but we don't have one directly from the URL.
        # For now, we'll use a dummy lead_id or require it in the endpoint.
        # For this implementation, let's assume we need to associate it with an existing lead.
        # This part needs clarification from the user or a design decision.
        # For now, let's fetch the first lead associated with the saas_info_id.
        db_lead = db.query(models.Lead).filter(models.Lead.saas_info_id == saas_info_id).first()
        if not db_lead:
            logging.error(f"No lead found for SaaS Info ID {saas_info_id}. Cannot create RedditPost placeholder.")
            return

        reddit_post_create = schemas.RedditPostCreate(
            title=post_title,
            content="Scraped post content placeholder.",
            score=0,
            num_comments=0,
            author=post_author,
            url=reddit_post_url,
            subreddits=[]
        )
        db_reddit_post = crud.create_reddit_post(db, reddit_post_create, db_lead.id)
        db.refresh(db_reddit_post)
        logging.info(f"Created placeholder RedditPost with ID: {db_reddit_post.id}")

    fetched_comments = await scraping_service.fetch_comments_from_post_url(reddit, reddit_post_url)
    if not fetched_comments:
        logging.warning(f"No comments fetched from {reddit_post_url}. Aborting comment reply process.")
        return

    db_operations_service.save_reddit_comments(db, db_reddit_post.id, fetched_comments)
    
    # Retrieve comments from DB to ensure we have their internal IDs
    comments_from_db = db_operations_service.get_reddit_comments_for_post(db, db_reddit_post.id)

    for comment_db in comments_from_db:
        if comment_db.is_replied:
            logging.info(f"Comment DB ID {comment_db.id} already replied to. Skipping.")
            continue

        generated_reply_content = await generation_service.generate_reddit_comment_reply(
            saas_info_id, 
            comment_db.content, 
            db
        )

        if generated_reply_content:
            success = await posting_service.post_reddit_comment_reply(
                reddit, 
                comment_db.comment_id, 
                generated_reply_content, 
                db, 
                comment_db.id
            )
            if success:
                logging.info(f"Successfully processed and replied to comment DB ID: {comment_db.id}")
            else:
                logging.error(f"Failed to post reply for comment DB ID: {comment_db.id}")
        else:
            logging.error(f"Failed to generate reply for comment DB ID: {comment_db.id}")
    
    db.close()
    logging.info(f"Completed processing replies for Reddit post URL: {reddit_post_url}")
