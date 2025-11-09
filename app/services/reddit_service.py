import json
import praw
import logging
import time
import random
from typing import List, Optional
from sqlalchemy.orm import Session
from scrapegraphai.graphs import DocumentScraperGraph
from app.core.config import settings
from app.models import models
from app.crud import crud
from app.schemas import schemas

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_reddit_instance():
    """Initializes and returns a PRAW Reddit instance with proper user agent."""
    try:
        # CRITICAL: Use a descriptive, unique user agent
        # Format: platform:app_name:version (by /u/username)
        user_agent = f"python:octopus:v1.0 (by /u/{settings.REDDIT_USERNAME})"
        
        reddit = praw.Reddit(
            client_id=settings.REDDIT_CLIENT_ID,
            client_secret=settings.REDDIT_CLIENT_SECRET,
            user_agent=user_agent,
            username=settings.REDDIT_USERNAME,
            password=settings.REDDIT_PASSWORD,
        )
        reddit.read_only = False
        
        # Verify the account is valid
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

def check_account_health(reddit) -> bool:
    """Check if the Reddit account is in good standing."""
    try:
        user = reddit.user.me()
        karma = user.link_karma + user.comment_karma
        account_age_days = (time.time() - user.created_utc) / 86400
        
        logging.info(f"Account: u/{user.name}")
        logging.info(f"Total Karma: {karma}")
        logging.info(f"Account Age: {account_age_days:.1f} days")
        logging.info(f"Verified Email: {user.has_verified_email}")
        
        # Warnings for risky account states
        if karma < 50:
            logging.warning("⚠️ Low karma account - high spam detection risk")
        if account_age_days < 7:
            logging.warning("⚠️ New account - high spam detection risk")
        if not user.has_verified_email:
            logging.warning("⚠️ Email not verified - posts may be auto-removed")
            
        return True
    except Exception as e:
        logging.error(f"Failed to check account health: {e}")
        return False

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

def check_posting_rate_limit(db: Session) -> bool:
    """Check if we're posting too frequently (rate limiting)."""
    # Get the most recent posted post
    recent_post = db.query(models.RedditPost).filter(
        models.RedditPost.is_posted == True
    ).order_by(models.RedditPost.id.desc()).first()
    
    if recent_post:
        # Assume there's a created_at or updated_at timestamp
        # If not, you'll need to add this to your model
        # For now, we'll add a simple time-based check
        pass  # You can implement this based on your model
    
    return True  # Allow posting for now

async def perform_reddit_analysis(saas_info_id: int, lead_id: int, subreddit_name: str, db: Session):
    logging.info(f"Starting Reddit analysis for subreddit: {subreddit_name}, Lead ID: {lead_id}")
    reddit = get_reddit_instance()
    if not reddit:
        return
    
    # Check account health before proceeding
    if not check_account_health(reddit):
        logging.error("Account health check failed. Aborting.")
        return

    saas_info_db = crud.get_saas_info(db, saas_info_id)
    if not saas_info_db:
        logging.error(f"SaaS Info with ID {saas_info_id} not found.")
        return

    posts_data = []
    try:
        subreddit = reddit.subreddit(subreddit_name)
        
        # Check if subreddit allows bots/self-promotion
        try:
            rules = subreddit.rules()
            logging.info(f"Found {len(rules)} rules for r/{subreddit_name}. Review them before posting.")
        except:
            pass
        
        # Fetch posts with random delay to appear more human
        time.sleep(random.uniform(2, 5))
        
        top_posts = subreddit.top(time_filter="week", limit=10)
        for post in top_posts:
            post_data = schemas.RedditPostCreate(
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
        return

    # Save raw posts to DB
    for post_create_schema in posts_data:
        crud.create_reddit_post(db, post_create_schema, lead_id)
    db.commit()

    # Now perform lead analysis on these posts
    all_posts_db = crud.get_reddit_posts_for_lead(db, lead_id)
    if not all_posts_db:
        logging.warning(f"No Reddit posts found for lead ID {lead_id} to analyze.")
        return

    # Convert SQLAlchemy models to dictionaries for the AI prompt
    saas_info_dict = {
        "name": saas_info_db.name,
        "one_liner": saas_info_db.one_liner,
        "features": [{"name": f.name, "desc": f.description} for f in saas_info_db.features],
        "target_segments": saas_info_db.target_segments
    }
    reddit_posts_dicts = [schemas.RedditPost.model_validate(p).model_dump() for p in all_posts_db]

    source_content = f"SaaS Information:\n{json.dumps(saas_info_dict, indent=2)}\n\nReddit Posts:\n{json.dumps(reddit_posts_dicts, indent=2)}"

    prompt = """
    Analyze the provided SaaS Information and Reddit Posts.
    Identify which Reddit posts represent high-quality leads for the SaaS product.
    A high-quality lead is a Reddit post where the user expresses a problem or need that can be directly addressed by the SaaS product's features, one-liner, or targets segments.
    Consider the SaaS product's name, one_liner, features (name and description), and target segments.
    For each identified lead, provide a 'lead_score' (a numerical value indicating the strength of the match) and a 'score_justification' (a brief explanation of why it's a good lead, referencing specific SaaS features or target segments and post content).
    Order the leads by 'lead_score' in descending order.
    The output MUST strictly conform to the JSON schema for a JSON object with a key "posts" containing a list of ScoredRedditPost objects, where each object includes all original fields of the Reddit post plus "lead_score" (float) and "score_justification" (string).
    If no relevant leads are found, return an empty list for the "posts" key.
    """

    graph_config = {
        "llm": {
            "api_key": settings.NVIDIA_KEY,
            "model": "nvidia/mistralai/mistral-nemotron",
            "temperature": 0,
            "format": "json",
            "model_tokens": 4000,
        },
        "verbose": True,
        "headless": False,
    }

    document_scraper_graph = DocumentScraperGraph(
        prompt=prompt,
        source=source_content,
        schema=schemas.ScoredRedditPostList,
        config=graph_config,
    )

    try:
        analysis_results_obj = document_scraper_graph.run()
        logging.info(f"Reddit lead analysis completed for Lead ID: {lead_id}")

        if isinstance(analysis_results_obj, schemas.ScoredRedditPostList):
            for scored_post_data in analysis_results_obj.posts:
                try:
                    original_post_url = scored_post_data.url
                    if original_post_url:
                        db_post = db.query(models.RedditPost).filter(
                            models.RedditPost.lead_id == lead_id,
                            models.RedditPost.url == original_post_url
                        ).first()
                        if db_post:
                            post_update_schema = schemas.RedditPostUpdate(
                                title=scored_post_data.title,
                                content=scored_post_data.content,
                                score=scored_post_data.score,
                                num_comments=scored_post_data.num_comments,
                                author=scored_post_data.author,
                                url=scored_post_data.url,
                                subreddit=scored_post_data.subreddit,
                                lead_score=scored_post_data.lead_score,
                                score_justification=scored_post_data.score_justification
                            )
                            crud.update_reddit_post(db, db_post.id, post_update_schema)
                        else:
                            logging.warning(f"Original post with URL {original_post_url} not found for update.")
                    else:
                        logging.warning(f"Scored post data missing 'url' field: {scored_post_data}")
                except Exception as e:
                    logging.error(f"Error processing analyzed Reddit post: {e} - Data: {scored_post_data}")
        else:
            logging.error(f"Unexpected format from DocumentScraperGraph.run() for analysis: {analysis_results_obj}")

    except Exception as e:
        logging.error(f"Error during Reddit lead analysis for Lead ID {lead_id}: {e}")
    finally:
        db.close()


async def generate_reddit_posts(saas_info_id: int, post_id: int, db: Session):
    logging.info(f"Starting Reddit post generation for Post ID: {post_id}")
    saas_info_db = crud.get_saas_info(db, saas_info_id)
    if not saas_info_db:
        logging.error(f"SaaS Info with ID {saas_info_id} not found.")
        return

    db_post = crud.get_reddit_post(db, post_id)
    if not db_post:
        logging.error(f"Reddit Post with ID {post_id} not found.")
        return

    # Convert SQLAlchemy models to dictionaries for the AI prompt
    saas_info_dict = {
        "name": saas_info_db.name,
        "one_liner": saas_info_db.one_liner,
        "features": [{"name": f.name, "desc": f.description} for f in saas_info_db.features],
        "target_segments": saas_info_db.target_segments
    }
    original_post_dict = schemas.RedditPost.model_validate(db_post).model_dump()

    source_content = f"SaaS Information:\n{json.dumps(saas_info_dict, indent=2)}\n\nOriginal Reddit Post:\n{json.dumps(original_post_dict, indent=2)}"

    # CRITICAL: Enhanced prompt to avoid spam detection
    prompt = f"""
    Based on the provided SaaS information and the original Reddit post, generate a new Reddit comment or discussion post.
    
    CRITICAL ANTI-SPAM REQUIREMENTS:
    1. Write in a genuine, conversational tone - like a real person sharing their experience
    2. DO NOT mention the product name directly - instead describe a "tool" or "service" you found helpful
    3. DO NOT include any links or URLs
    4. DO NOT use marketing language like "check out", "amazing", "revolutionary", etc.
    5. Focus on sharing personal experience or asking for advice
    6. Include natural imperfections: casual language, contractions, maybe a typo
    7. Make it about the problem first, solution second
    8. Keep it relatively short (2-4 paragraphs max)
    9. Use Reddit-style formatting sparingly (not too perfect)
    
    The post should:
    - Address the core problem mentioned in the original post
    - Share a relatable personal experience or question
    - Subtly reference that you found something helpful (without naming it directly)
    - Encourage genuine discussion
    - Feel authentic and human
    
    Example good style: "I was struggling with the same thing last month. After trying a few different approaches, I found a service that helped me automate this process. Still learning how to use it properly but it's been pretty useful so far. Anyone else dealt with this?"
    
    Example bad style (TOO PROMOTIONAL): "You should definitely check out [Product]! It's amazing and has all these features. Here's a link!"
    
    The output MUST strictly conform to the JSON schema for a GeneratedPostContent object.
    {{
        "title": "string",
        "content": "string"
    }}
    """

    graph_config = {
        "llm": {
            "api_key": settings.NVIDIA_KEY,
            "model": "nvidia/mistralai/mistral-nemotron",
            "temperature": 0.8,  # Higher temperature for more human-like variation
            "format": "json",
            "model_tokens": 4000,
        },
        "verbose": True,
        "headless": False,
    }

    document_scraper_graph = DocumentScraperGraph(
        prompt=prompt,
        source=source_content,
        schema=schemas.GeneratedPostContent,
        config=graph_config,
    )

    try:
        raw_generated_data = document_scraper_graph.run()
        logging.info(f"Reddit post generation completed for Post ID: {post_id}")

        if raw_generated_data:
            try:
                generated_post_content_obj = schemas.GeneratedPostContent(**raw_generated_data)
                
                # Update the original RedditPost with generated content
                post_update_schema = schemas.RedditPostUpdate(
                    title=db_post.title,
                    content=db_post.content,
                    score=db_post.score,
                    num_comments=db_post.num_comments,
                    author=db_post.author,
                    url=db_post.url,
                    subreddit=db_post.subreddit,
                    generated_title=generated_post_content_obj.title,
                    generated_content=generated_post_content_obj.content,
                    ai_generated=True
                )
                crud.update_reddit_post(db, post_id, post_update_schema)
                db.commit()
            except Exception as e:
                logging.error(f"Error validating or updating generated post: {e} - Raw Data: {raw_generated_data}")
        else:
            logging.error(f"AI failed to generate content for Post ID {post_id}. Raw output was empty or None.")

    except Exception as e:
        logging.error(f"Error during Reddit post generation for Post ID {post_id}: {e}")
    finally:
        db.close()


async def post_generated_reddit_post(post_id: int, db: Session):
    """
    Post generated content to Reddit with extensive anti-spam measures.
    ONLY posts once per subreddit per lead.
    """
    logging.info(f"Attempting to post generated Reddit post for Post ID: {post_id}")
    reddit = get_reddit_instance()
    if not reddit:
        return
    
    # Check account health before posting
    if not check_account_health(reddit):
        logging.error("Account health check failed. Aborting post.")
        return

    db_post = crud.get_reddit_post(db, post_id)
    if not db_post:
        logging.error(f"Reddit Post with ID {post_id} not found.")
        return
    
    if not db_post.generated_title or not db_post.generated_content:
        logging.error(f"Post ID {post_id} does not have generated content to post.")
        return
    
    if not db_post.ai_generated:
        logging.warning(f"Post ID {post_id} is not marked as AI-generated. Skipping posting.")
        return
    
    # CRITICAL: Check if already posted to this subreddit
    if db_post.is_posted:
        logging.warning(f"Post ID {post_id} is already marked as posted. Skipping duplicate post.")
        return
    
    # Check if we've already posted to this subreddit for this lead
    if check_if_already_posted(db, db_post.lead_id, db_post.subreddit):
        return

    # Use the original subreddit from the analyzed post
    target_subreddit = "testingground4bots" #db_post.subreddit
    
    # Add human-like delays before posting
    delay = 1 #random.uniform(30, 90)  # Random delay between 30-90 seconds
    logging.info(f"Waiting {delay:.1f} seconds before posting (anti-spam delay)...")
    time.sleep(delay)

    try:
        subreddit = reddit.subreddit(target_subreddit)
        
        # Try to post as a comment if it's a reply to an existing post
        # Otherwise post as a new submission
        if db_post.url and 'comments' in db_post.url:
            # This is a reply to an existing post - post as comment
            try:
                submission_id = db_post.url.split('/comments/')[1].split('/')[0]
                submission = reddit.submission(id=submission_id)
                
                # Add another small delay
                time.sleep(random.uniform(5, 15))
                
                comment = submission.reply(db_post.generated_content)
                logging.info(f"Successfully posted comment to r/{target_subreddit} on post: {db_post.title}")
                logging.info(f"Comment ID: {comment.id}")
                
            except Exception as e:
                logging.error(f"Failed to post as comment, trying as new post: {e}")
                # Fall back to posting as new submission
                raise e
        else:
            # Post as a new submission
            submission = subreddit.submit(
                db_post.generated_title, 
                selftext=db_post.generated_content
            )
            logging.info(f"Successfully posted to r/{target_subreddit}: '{db_post.generated_title}'")
            logging.info(f"Submission ID: {submission.id}")
        
        # Add post-posting delay
        time.sleep(random.uniform(10, 20))

        # Update the post status in the database
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
            ai_generated=db_post.ai_generated
        )
        crud.update_reddit_post(db, post_id, post_update_schema)
        db.commit()
        
    except Exception as e:
        logging.error(f"Failed to post to r/{target_subreddit} for Post ID {post_id}: {e}")
        # Don't mark as posted if it failed
    finally:
        db.close()


# Additional utility function to manually review posts before posting
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
        "original_content": db_post.content[:200] + "..." if len(db_post.content) > 200 else db_post.content,
        "generated_title": db_post.generated_title,
        "generated_content": db_post.generated_content,
        "target_subreddit": db_post.subreddit,
        "lead_score": db_post.lead_score,
        "is_posted": db_post.is_posted
    }