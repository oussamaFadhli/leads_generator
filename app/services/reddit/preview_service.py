from typing import Optional
from sqlalchemy.orm import Session
from app.crud import crud

def preview_generated_post(post_id: int, db: Session) -> Optional[dict]:
    """
    Preview a generated post before posting it.
    Returns the post data for manual review.
    """
    db_post = crud.get_reddit_post(db, post_id)
    if not db_post:
        return None
    
    return {
        "post_id": post_id,
        "original_title": db_post.title,
        "original_content": db_post.content,
        "generated_title": db_post.generated_title,
        "generated_content": db_post.generated_content,
        "target_subreddit": db_post.subreddit,
        "lead_score": db_post.lead_score,
        "is_posted": db_post.is_posted
    }
