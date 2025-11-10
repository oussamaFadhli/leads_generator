from fastapi import FastAPI
from app.api.routers import saas_info, leads, reddit_posts
from app.core.database import Base, engine
from app.models import models

# Create database tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Reddit Engagement API",
    description="API for managing SaaS information, Reddit leads, and post generation/posting.",
    version="1.0.0",
)

app.include_router(saas_info.router)
app.include_router(leads.router)
app.include_router(reddit_posts.router)
app.include_router(reddit_posts.comments_router) # Include the new comments router

@app.get("/")
async def root():
    return {"message": "Welcome to the Reddit Engagement API!"}
