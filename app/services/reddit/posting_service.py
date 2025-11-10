import logging
import time
import random
import praw
from sqlalchemy.orm import Session
from app.schemas import schemas
from app.services.reddit import auth_service, account_service, db_operations_service

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def post_generated_reddit_post(post_id: int, db: Session):
    """
    Post generated content to Reddit with extensive anti-spam measures.
    ONLY posts once per subreddit per lead.
    """
    logging.info(f"Attempting to post generated Reddit post for Post ID: {post_id}")
    reddit = auth_service.get_reddit_instance()
    if not reddit:
        return
    
    if not account_service.check_account_health(reddit):
        logging.error("Account health check failed. Aborting post.")
        return

    db_post = db_operations_service.get_reddit_post_by_id(db, post_id)
    if not db_post:
        logging.error(f"Reddit Post with ID {post_id} not found.")
        return
    
    if not db_post.generated_title or not db_post.generated_content:
        logging.error(f"Post ID {post_id} does not have generated content to post.")
        return
    
    if not db_post.ai_generated:
        logging.warning(f"Post ID {post_id} is not marked as AI-generated. Skipping posting.")
        return
    
    if db_post.is_posted:
        logging.warning(f"Post ID {post_id} is already marked as posted. Skipping duplicate post.")
        return
    
    if db_operations_service.check_if_already_posted(db, db_post.lead_id, db_post.subreddit):
        return

    target_subreddit = "testingground4bots" #db_post.subreddit
    
    delay = 1 #random.uniform(30, 90)
    logging.info(f"Waiting {delay:.1f} seconds before posting (anti-spam delay)...")
    time.sleep(delay)

    try:
        subreddit = reddit.subreddit(target_subreddit)
        
        if db_post.url and 'comments' in db_post.url:
            try:
                submission_id = db_post.url.split('/comments/')[1].split('/')[0]
                submission = reddit.submission(id=submission_id)
                
                time.sleep(random.uniform(5, 15))
                
                comment = submission.reply(db_post.generated_content)
                logging.info(f"Successfully posted comment to r/{target_subreddit} on post: {db_post.title}")
                logging.info(f"Comment ID: {comment.id}")
                
            except Exception as e:
                logging.error(f"Failed to post as comment, trying as new post: {e}")
                raise e
        else:
            submission = subreddit.submit(
                db_post.generated_title, 
                selftext=db_post.generated_content
            )
            logging.info(f"Successfully posted to r/{target_subreddit}: '{db_post.generated_title}'")
            logging.info(f"Submission ID: {submission.id}")
        
        time.sleep(random.uniform(10, 20))

        post_update_schema = schemas.RedditPostUpdate(
            title=db_post.title,
            content=db_post.content,
            score=db_post.score,
            num_comments=db_post.num_comments,
            author=db_post.author,
            url=db_post.url,
            subreddit=db_post.subreddit,
            generated_title=db_post.generated_title,
            generated_content=db_post.generated_content,
            is_posted=True,
            ai_generated=db_post.ai_generated,
            posted_url=f"https://www.reddit.com{comment.permalink}" if 'comment' in locals() else f"https://www.reddit.com{submission.permalink}"
        )
        db_operations_service.update_reddit_post_in_db(db, post_id, post_update_schema)
        
    except Exception as e:
        logging.error(f"Failed to post to r/{target_subreddit} for Post ID {post_id}: {e}")
    finally:
        db.close()
