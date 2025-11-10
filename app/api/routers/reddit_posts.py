from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List

from app.schemas import schemas
from app.crud import crud
from app.core.database import get_db
from app.services.reddit_service import (
    perform_reddit_analysis, 
    generate_reddit_posts, 
    post_generated_reddit_post,
    reply_to_reddit_post_comments # Import the new service function
)

router = APIRouter(
    prefix="/saas-info/{saas_info_id}/leads/{lead_id}/reddit-posts",
    tags=["Reddit Posts"],
    responses={404: {"description": "Not found"}},
)

# New router for comment replies, not tied to a specific lead_id in the path
comments_router = APIRouter(
    prefix="/saas-info/{saas_info_id}/reddit-comments",
    tags=["Reddit Comments"],
    responses={404: {"description": "Not found"}},
)

def verify_lead_and_saas_info(saas_info_id: int, lead_id: int, db: Session):
    db_saas_info = crud.get_saas_info(db, saas_info_id=saas_info_id)
    if db_saas_info is None:
        raise HTTPException(status_code=404, detail="SaaS Info not found")
    db_lead = crud.get_lead(db, lead_id=lead_id)
    if db_lead is None or db_lead.saas_info_id != saas_info_id:
        raise HTTPException(status_code=404, detail="Lead not found for this SaaS Info")
    return db_saas_info, db_lead

@router.post("/", response_model=schemas.RedditPost)
def create_reddit_post_endpoint(
    saas_info_id: int, 
    lead_id: int, 
    post: schemas.RedditPostCreate, 
    db: Session = Depends(get_db)
):
    verify_lead_and_saas_info(saas_info_id, lead_id, db)
    return crud.create_reddit_post(db=db, post=post, lead_id=lead_id)

@router.get("/", response_model=List[schemas.RedditPost])
def read_reddit_posts_for_lead_endpoint(
    saas_info_id: int, 
    lead_id: int, 
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    verify_lead_and_saas_info(saas_info_id, lead_id, db)
    posts = crud.get_reddit_posts_for_lead(db, lead_id=lead_id, skip=skip, limit=limit)
    return posts

@router.get("/{post_id}", response_model=schemas.RedditPost)
def read_reddit_post_endpoint(
    saas_info_id: int, 
    lead_id: int, 
    post_id: int, 
    db: Session = Depends(get_db)
):
    verify_lead_and_saas_info(saas_info_id, lead_id, db)
    db_post = crud.get_reddit_post(db, post_id=post_id)
    if db_post is None or db_post.lead_id != lead_id:
        raise HTTPException(status_code=404, detail="Reddit Post not found for this Lead")
    return db_post

@router.put("/{post_id}", response_model=schemas.RedditPost)
def update_reddit_post_endpoint(
    saas_info_id: int, 
    lead_id: int, 
    post_id: int, 
    post_update: schemas.RedditPostUpdate, 
    db: Session = Depends(get_db)
):
    verify_lead_and_saas_info(saas_info_id, lead_id, db)
    db_post = crud.get_reddit_post(db, post_id=post_id)
    if db_post is None or db_post.lead_id != lead_id:
        raise HTTPException(status_code=404, detail="Reddit Post not found for this Lead")
    return crud.update_reddit_post(db=db, post_id=post_id, post_update=post_update)

@router.delete("/{post_id}", response_model=schemas.RedditPost)
def delete_reddit_post_endpoint(
    saas_info_id: int, 
    lead_id: int, 
    post_id: int, 
    db: Session = Depends(get_db)
):
    verify_lead_and_saas_info(saas_info_id, lead_id, db)
    db_post = crud.get_reddit_post(db, post_id=post_id)
    if db_post is None or db_post.lead_id != lead_id:
        raise HTTPException(status_code=404, detail="Reddit Post not found for this Lead")
    return crud.delete_reddit_post(db=db, post_id=post_id)

@comments_router.post("/reply-to-comments", status_code=202)
async def trigger_reply_to_comments_endpoint(
    saas_info_id: int,
    reddit_post_url: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    db_saas_info = crud.get_saas_info(db, saas_info_id=saas_info_id)
    if db_saas_info is None:
        raise HTTPException(status_code=404, detail="SaaS Info not found")
    
    background_tasks.add_task(reply_to_reddit_post_comments, saas_info_id, reddit_post_url, db)
    return {"message": f"Initiated AI-powered replies to comments for Reddit post: {reddit_post_url}."}

@router.post("/analyze/{subreddit_name}", status_code=202)
async def trigger_reddit_analysis_endpoint(
    saas_info_id: int, 
    lead_id: int, 
    subreddit_name: str,
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db)
):
    db_saas_info, db_lead = verify_lead_and_saas_info(saas_info_id, lead_id, db)
    
    background_tasks.add_task(perform_reddit_analysis, saas_info_id, lead_id, subreddit_name, db)
    return {"message": f"Reddit analysis for subreddit '{subreddit_name}' initiated in the background."}

@router.post("/generate/{post_id}", status_code=202)
async def trigger_post_generation_endpoint(
    saas_info_id: int, 
    lead_id: int, 
    post_id: int,
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db)
):
    db_saas_info, db_lead = verify_lead_and_saas_info(saas_info_id, lead_id, db)
    db_post = crud.get_reddit_post(db, post_id=post_id)
    if db_post is None or db_post.lead_id != lead_id:
        raise HTTPException(status_code=404, detail="Reddit Post not found for this Lead")
    
    background_tasks.add_task(generate_reddit_posts, saas_info_id, post_id, db)
    return {"message": f"Reddit post generation for post ID {post_id} initiated in the background."}

@router.post("/post/{post_id}", status_code=202)
async def trigger_reddit_post_endpoint(
    saas_info_id: int, 
    lead_id: int, 
    post_id: int,
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db)
):
    db_saas_info, db_lead = verify_lead_and_saas_info(saas_info_id, lead_id, db)
    db_post = crud.get_reddit_post(db, post_id=post_id)
    if db_post is None or db_post.lead_id != lead_id:
        raise HTTPException(status_code=404, detail="Reddit Post not found for this Lead")
    if not db_post.generated_title or not db_post.generated_content:
        raise HTTPException(status_code=400, detail="Post content not generated yet.")
    
    background_tasks.add_task(post_generated_reddit_post, post_id, db)
    return {"message": f"Reddit post ID {post_id} scheduled for posting."}
