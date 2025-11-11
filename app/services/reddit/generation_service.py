import json
import logging
from typing import Optional
from scrapegraphai.graphs import DocumentScraperGraph
from app.core.config import settings
from app.schemas import schemas
from app.core.cqrs import CommandBus, QueryBus
from app.queries.saas_info_queries import GetSaaSInfoByIdQuery
from app.queries.reddit_post_queries import GetRedditPostByIdQuery
from app.commands.reddit_post_commands import UpdateRedditPostCommand
from app.commands.reddit_comment_commands import UpdateRedditCommentCommand

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def generate_reddit_posts(saas_info_id: int, post_id: int, command_bus: CommandBus, query_bus: QueryBus):
    logging.info(f"Starting Reddit post generation for Post ID: {post_id}")
    saas_info_db = await query_bus.dispatch(GetSaaSInfoByIdQuery(saas_info_id=saas_info_id))
    if not saas_info_db:
        logging.error(f"SaaS Info with ID {saas_info_id} not found.")
        return

    db_post = await query_bus.dispatch(GetRedditPostByIdQuery(reddit_post_id=post_id))
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
                
                update_command = UpdateRedditPostCommand(
                    reddit_post_id=db_post.id,
                    generated_title=generated_post_content_obj.title,
                    generated_content=generated_post_content_obj.content,
                    ai_generated=True
                )
                await command_bus.dispatch(update_command)
            except Exception as e:
                logging.error(f"Error validating or updating generated post: {e} - Raw Data: {raw_generated_data}")
        else:
            logging.error(f"AI failed to generate content for Post ID {post_id}. Raw output was empty or None.")

    except Exception as e:
        logging.error(f"Error during Reddit post generation for Post ID {post_id}: {e}")

async def generate_reddit_comment_reply(saas_info_id: int, original_comment_content: str, command_bus: CommandBus, query_bus: QueryBus) -> Optional[str]:
    logging.info(f"Starting Reddit comment reply generation for SaaS Info ID: {saas_info_id}")
    saas_info_db = await query_bus.dispatch(GetSaaSInfoByIdQuery(saas_info_id=saas_info_id))
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
    
    Tone: Sales Manager, Human, Empathetic, Problem-Solving. The goal is to genuinely help the user by subtly introducing a relevant solution (our SaaS) without being overtly promotional.
    
    CRITICAL ANTI-SPAM REQUIREMENTS:
    1. Write in a genuine, conversational tone - like a real person sharing their experience or offering advice.
    2. DO NOT mention the product name directly - instead describe a "tool," "service," "platform," or "approach" you found helpful.
    3. DO NOT include any links or URLs.
    4. DO NOT use aggressive marketing language like "check out," "amazing," "revolutionary," "boost your productivity," "transform your business," etc.
    5. Focus on addressing the user's pain point, sharing a relatable experience, or asking clarifying questions to understand their need better.
    6. Include natural imperfections: casual language, contractions, maybe a slight conversational pause.
    7. Make it about the problem first, solution second. Frame the solution as a helpful discovery or a potential path forward.
    8. Keep it concise and valuable (1-3 paragraphs max).
    9. Use Reddit-style formatting sparingly (e.g., bold for emphasis, but not overly structured).
    
    The reply should:
    - Acknowledge and empathize with the core problem or question mentioned in the original comment.
    - Share a brief, relatable personal experience or observation that aligns with the user's struggle.
    - Subtly introduce the concept of a helpful solution (our SaaS's core value proposition) without naming it directly. Frame it as a general category of tool or service.
    - Gently guide the user towards considering a solution that matches their need, based on the SaaS information provided.
    - Maintain a helpful, advisory, and authentic human tone, as if a sales manager is genuinely trying to assist, not just sell.
    - Feel authentic and human, like a seasoned professional offering a tip.
    
    Example good style: "I totally get what you're saying about [user's problem]. It's a common hurdle, and I've seen many teams struggle with that exact challenge. What often helps is having a system that can [SaaS core benefit, e.g., 'automate those repetitive tasks' or 'centralize all your data for better insights']. It really streamlines things and frees up time for more strategic work. Have you explored solutions that offer that kind of capability?"
    
    Example bad style (TOO PROMOTIONAL): "You should definitely check out [Product]! It's amazing and has all these features. Here's a link!"
    
    The output MUST strictly conform to the JSON schema for a GeneratedCommentContent object.
    {{
        "content": "string"
    }}
    """

    # The AI agent model for comment reply generation is configured within this graph_config dictionary.
    # Specifically, the 'model' key under 'llm' specifies the AI model to be used.
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
    return None
