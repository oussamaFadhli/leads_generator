import json
import logging
from sqlalchemy.orm import Session
from scrapegraphai.graphs import DocumentScraperGraph
from app.core.config import settings
from app.crud import crud
from app.schemas import schemas
from app.services.reddit import db_operations_service

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def generate_reddit_posts(saas_info_id: int, post_id: int, db: Session):
    logging.info(f"Starting Reddit post generation for Post ID: {post_id}")
    saas_info_db = crud.get_saas_info(db, saas_info_id)
    if not saas_info_db:
        logging.error(f"SaaS Info with ID {saas_info_id} not found.")
        return

    db_post = db_operations_service.get_reddit_post_by_id(db, post_id)
    if not db_post:
        logging.error(f"Reddit Post with ID {post_id} not found.")
        return

    saas_info_dict = {
        "name": saas_info_db.name,
        "one_liner": saas_info_db.one_liner,
        "features": [{"name": f.name, "desc": f.description} for f in saas_info_db.features],
        "target_segments": saas_info_db.target_segments
    }
    original_post_dict = schemas.RedditPost.model_validate(db_post).model_dump()

    source_content = f"SaaS Information:\n{json.dumps(saas_info_dict, indent=2)}\n\nOriginal Reddit Post:\n{json.dumps(original_post_dict, indent=2)}"

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
            "temperature": 0.8,
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
                
                post_update_schema = schemas.RedditPostUpdate(
                    title=db_post.title,
                    content=db_post.content,
                    score=db_post.score,
                    num_comments=db_post.num_comments,
                    author=db_post.author,
                    url=db_post.url,
                    subreddits=db_post.subreddits_list if db_post.subreddits_list is not None else [], # Ensure subreddits is always a list
                    generated_title=generated_post_content_obj.title,
                    generated_content=generated_post_content_obj.content,
                    ai_generated=True
                )
                db_operations_service.update_reddit_post_in_db(db, post_id, post_update_schema)
            except Exception as e:
                logging.error(f"Error validating or updating generated post: {e} - Raw Data: {raw_generated_data}")
        else:
            logging.error(f"AI failed to generate content for Post ID {post_id}. Raw output was empty or None.")

    except Exception as e:
        logging.error(f"Error during Reddit post generation for Post ID {post_id}: {e}")
    finally:
        db.close()

async def generate_reddit_comment_reply(saas_info_id: int, original_comment_content: str, db: Session):
    logging.info(f"Starting Reddit comment reply generation for SaaS Info ID: {saas_info_id}")
    saas_info_db = crud.get_saas_info(db, saas_info_id)
    if not saas_info_db:
        logging.error(f"SaaS Info with ID {saas_info_id} not found.")
        return

    saas_info_dict = {
        "name": saas_info_db.name,
        "one_liner": saas_info_db.one_liner,
        "features": [{"name": f.name, "desc": f.description} for f in saas_info_db.features],
        "target_segments": saas_info_db.target_segments
    }

    source_content = f"SaaS Information:\n{json.dumps(saas_info_dict, indent=2)}\n\nOriginal Reddit Comment:\n{original_comment_content}"

    prompt = f"""
    Based on the provided SaaS information and the original Reddit comment, generate a new Reddit reply.
    
    CRITICAL ANTI-SPAM REQUIREMENTS:
    1. Write in a genuine, conversational tone - like a real person sharing their experience
    2. DO NOT mention the product name directly - instead describe a "tool" or "service" you found helpful
    3. DO NOT include any links or URLs
    4. DO NOT use marketing language like "check out", "amazing", "revolutionary", etc.
    5. Focus on sharing personal experience or asking for advice
    6. Include natural imperfections: casual language, contractions, maybe a typo
    7. Make it about the problem first, solution second
    8. Keep it relatively short (1-3 paragraphs max)
    9. Use Reddit-style formatting sparingly (not too perfect)
    
    The reply should:
    - Address the core problem or question mentioned in the original comment
    - Share a relatable personal experience or question
    - Subtly reference that you found something helpful (without naming it directly)
    - Try to give a solution if the SaaS info can really help the user
    - Feel authentic and human
    
    Example good style: "I totally get what you're saying. I was in a similar spot a while back trying to manage [problem]. What really helped me was finding a service that automates a lot of that. It's made a huge difference for my workflow. Have you looked into anything like that?"
    
    Example bad style (TOO PROMOTIONAL): "You should definitely check out [Product]! It's amazing and has all these features. Here's a link!"
    
    The output MUST strictly conform to the JSON schema for a GeneratedCommentContent object.
    {{
        "content": "string"
    }}
    """

    graph_config = {
        "llm": {
            "api_key": settings.NVIDIA_KEY,
            "model": "nvidia/mistralai/mistral-nemotron",
            "temperature": 0.8,
            "format": "json",
            "model_tokens": 4000,
        },
        "verbose": True,
        "headless": False,
    }

    document_scraper_graph = DocumentScraperGraph(
        prompt=prompt,
        source=source_content,
        schema=schemas.GeneratedCommentContent,
        config=graph_config,
    )

    try:
        raw_generated_data = document_scraper_graph.run()
        logging.info(f"Reddit comment reply generation completed for SaaS Info ID: {saas_info_id}")

        if raw_generated_data:
            try:
                generated_comment_content_obj = schemas.GeneratedCommentContent(**raw_generated_data)
                return generated_comment_content_obj.content
            except Exception as e:
                logging.error(f"Error validating generated comment reply: {e} - Raw Data: {raw_generated_data}")
        else:
            logging.error(f"AI failed to generate content for SaaS Info ID {saas_info_id}. Raw output was empty or None.")

    except Exception as e:
        logging.error(f"Error during Reddit comment reply generation for SaaS Info ID {saas_info_id}: {e}")
    finally:
        db.close()
    return None
