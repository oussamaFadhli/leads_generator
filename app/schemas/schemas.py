from pydantic import BaseModel, Field, validator
from typing import List, Optional
import json

# Feature Schemas
class FeatureBase(BaseModel):
    name: str
    description: str

class FeatureCreate(FeatureBase):
    pass

class Feature(FeatureBase):
    id: int
    saas_info_id: int

    class Config:
        from_attributes = True

# Pricing Plan Schemas
class PricingPlanBase(BaseModel):
    plan_name: str
    price: str
    features: List[str] # Expecting a list of strings from scraper
    link: Optional[str] = None

    @validator('features', pre=True, always=True)
    def parse_features(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                raise ValueError("features must be a valid JSON string or a list of strings")
        return v

class PricingPlanCreate(PricingPlanBase):
    pass

class PricingPlan(PricingPlanBase):
    id: int
    saas_info_id: int

    class Config:
        from_attributes = True

# SaaS Info Schemas
class SaaSInfoBase(BaseModel):
    name: str
    one_liner: str
    target_segments: Optional[List[str]] = None # Made optional for testing simplified scraper

    @validator('target_segments', pre=True, always=True)
    def parse_target_segments(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                raise ValueError("target_segments must be a valid JSON string or a list of strings")
        return v

class SaaSInfoCreate(SaaSInfoBase):
    features: Optional[List[FeatureCreate]] = None
    pricing: Optional[List[PricingPlanCreate]] = None
    target_segments: Optional[List[str]] = None

class SaaSInfo(SaaSInfoBase):
    id: int
    features: List[Feature] = []
    pricing: List[PricingPlan] = []

    class Config:
        from_attributes = True

# Reddit Post Schemas
class RedditPostBase(BaseModel):
    title: str
    content: str
    score: int
    num_comments: int
    author: str
    url: str
    subreddits: Optional[List[str]] = None # Made optional

    @validator('subreddits', pre=True, always=True)
    def parse_subreddits(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                raise ValueError("subreddits must be a valid JSON string or a list of strings")
        return v

class RedditPostCreate(RedditPostBase):
    pass

class RedditPostUpdate(RedditPostBase):
    # Re-defining subreddits here to ensure optionality is respected,
    # and providing a default factory to ensure it's always a list if not provided.
    subreddits: Optional[List[str]] = Field(default_factory=list)
    lead_score: Optional[float] = None
    score_justification: Optional[str] = None
    generated_title: Optional[str] = None
    generated_content: Optional[str] = None
    is_posted: Optional[bool] = False
    ai_generated: Optional[bool] = False
    posted_url: Optional[str] = None
    # Removed 'subreddit' field as it no longer exists in the model.
    # The 'subreddits' field (plural) is now used.

class RedditPost(RedditPostBase):
    id: int
    lead_id: int
    lead_score: Optional[float] = None
    score_justification: Optional[str] = None
    generated_title: Optional[str] = None
    generated_content: Optional[str] = None
    posted_url: Optional[str] = None
    is_posted: bool = False
    ai_generated: bool = False
    # Removed 'subreddit' field as it no longer exists in the model.
    # The 'subreddits' field (plural) is now used.

    class Config:
        from_attributes = True

# Scored Reddit Post List Schema for DocumentScraperGraph
class ScoredRedditPostList(BaseModel):
    posts: List[RedditPostUpdate]

# Generated Post Content Schema for AI generation
class GeneratedPostContent(BaseModel):
    title: str
    content: str

# Reddit Comment Schemas
class RedditCommentBase(BaseModel):
    comment_id: str
    post_id: str
    author: str
    content: str
    score: int
    permalink: str

class RedditCommentCreate(RedditCommentBase):
    pass

class RedditComment(RedditCommentBase):
    id: int # Internal DB ID
    reddit_post_db_id: int # Foreign key to our internal RedditPost model
    generated_reply_content: Optional[str] = None
    is_replied: bool = False
    ai_generated: bool = False

    class Config:
        from_attributes = True

# Generated Comment Content Schema for AI generation
class GeneratedCommentContent(BaseModel):
    content: str

# Lead Schemas
class LeadBase(BaseModel):
    competitor_name: str
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    related_subreddits: List[str] = Field(default_factory=list)

    @validator('strengths', 'weaknesses', 'related_subreddits', pre=True, always=True)
    def parse_json_list(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                raise ValueError("Field must be a valid JSON string or a list of strings")
        return v

class LeadCreate(LeadBase):
    pass

class LeadsCreate(BaseModel):
    leads: List[LeadCreate]

class Lead(LeadBase):
    id: int
    saas_info_id: int
    reddit_posts: List[RedditPost] = []

    class Config:
        from_attributes = True
