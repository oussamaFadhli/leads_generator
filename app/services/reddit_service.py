import json
import praw
import logging
import time # Import time module
from typing import List
from sqlalchemy.orm import Session
from scrapegraphai.graphs import DocumentScraperGraph
from app.core.config import settings
from app.models import models
from app.crud import crud
from app.schemas import schemas

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_reddit_instance():
    """Initializes and returns a PRAW Reddit instance."""
    try:
        reddit = praw.Reddit(
            client_id=settings.REDDIT_CLIENT_ID,
            client_secret=settings.REDDIT_CLIENT_SECRET,
            user_agent=settings.REDDIT_USER_AGENT,
            username=settings.REDDIT_USERNAME,
            password=settings.REDDIT_PASSWORD,
        )
        reddit.read_only = False
        return reddit
    except Exception as e:
        logging.error(f"Failed to initialize Reddit instance: {e}")
        return None

async def perform_reddit_analysis(saas_info_id: int, lead_id: int, subreddit_name: str, db: Session):
    logging.info(f"Starting Reddit analysis for subreddit: {subreddit_name}, Lead ID: {lead_id}")
    reddit = get_reddit_instance()
    if not reddit:
        return

    saas_info_db = crud.get_saas_info(db, saas_info_id)
    if not saas_info_db:
        logging.error(f"SaaS Info with ID {saas_info_id} not found.")
        return

    posts_data = []
    try:
        subreddit = reddit.subreddit(subreddit_name)
        top_posts = subreddit.top(time_filter="week", limit=10) # Limit to 10 posts for analysis
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
    db.commit() # Commit after creating all posts

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
        schema=schemas.ScoredRedditPostList, # Expecting a ScoredRedditPostList object
        config=graph_config,
    )

    try:
        analysis_results_obj = document_scraper_graph.run()
        logging.info(f"Reddit lead analysis completed for Lead ID: {lead_id}")

        if isinstance(analysis_results_obj, schemas.ScoredRedditPostList):
            for scored_post_data in analysis_results_obj.posts:
                try:
                    # Find the corresponding post in the database and update it
                    original_post_url = scored_post_data.url
                    if original_post_url:
                        db_post = db.query(models.RedditPost).filter(
                            models.RedditPost.lead_id == lead_id,
                            models.RedditPost.url == original_post_url
                        ).first()
                        if db_post:
                            # Create RedditPostUpdate schema from the scored_post_data
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

    prompt = f"""
    Based on the provided SaaS information and the original Reddit post, generate a new, similar Reddit post.
    The new post should be written in a human-like, friendly, and youthful tone, suitable for Reddit. It should not sound like a generic AI.
    The post should address the core problem or topic of the original post, but from a new perspective.
    Subtly hint at a solution related to the '{saas_info_db.name}' SaaS product without being an obvious advertisement.
    Crucially, the generated post must be engaging, thought-provoking, and blend seamlessly with typical Reddit discussions to avoid being flagged by spam filters. Avoid overly promotional language, direct calls to action, or repetitive phrasing. Focus on genuine discussion and value.
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
            "temperature": 0.7,
            "format": "json",
            "model_tokens": 4000,
        },
        "verbose": True,
        "headless": False,
    }

    document_scraper_graph = DocumentScraperGraph(
        prompt=prompt,
        source=source_content,
        schema=schemas.GeneratedPostContent, # Expecting a GeneratedPostContent object
        config=graph_config,
    )

    try:
        raw_generated_data = document_scraper_graph.run()
        logging.info(f"Reddit post generation completed for Post ID: {post_id}")

        if raw_generated_data:
            try:
                # Explicitly validate the raw dictionary against the Pydantic schema
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
                    ai_generated=True # Mark as AI generated
                )
                crud.update_reddit_post(db, post_id, post_update_schema)
                db.commit() # Commit the changes to the database
            except Exception as e:
                logging.error(f"Error validating or updating generated post: {e} - Raw Data: {raw_generated_data}")
        else:
            logging.error(f"AI failed to generate content for Post ID {post_id}. Raw output was empty or None.")

    except Exception as e:
        logging.error(f"Error during Reddit post generation for Post ID {post_id}: {e}")
    finally:
        db.close()


async def post_generated_reddit_post(post_id: int, db: Session):
    logging.info(f"Attempting to post generated Reddit post for Post ID: {post_id}")
    reddit = get_reddit_instance()
    if not reddit:
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

    # For now, we'll post to a hardcoded subreddit for testing.
    # In a real scenario, you might select a subreddit based on lead data or user input.
    target_subreddit = "test" # Replace with a suitable subreddit for actual posting

    try:
        subreddit = reddit.subreddit(target_subreddit)
        submission = subreddit.submit(db_post.generated_title, selftext=db_post.generated_content)
        
        # Add a small delay after posting to avoid rate limiting issues
        time.sleep(5) # Wait for 5 seconds

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
            ai_generated=db_post.ai_generated # Preserve the ai_generated flag
        )
        crud.update_reddit_post(db, post_id, post_update_schema)
        db.commit() # Commit the changes to the database
        
        logging.info(f"Successfully posted to r/{target_subreddit}: '{db_post.generated_title}' (Submission ID: {submission.id})")
        # You can also check submission.mod.removed here if needed for debugging
    except Exception as e:
        logging.error(f"Failed to post to r/{target_subreddit} for Post ID {post_id}: {e}")
    finally:
        db.close()
