import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from app.crud import crud
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
