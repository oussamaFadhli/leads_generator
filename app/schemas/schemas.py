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
    subreddit: str

class RedditPostCreate(RedditPostBase):
    pass

class RedditPostUpdate(RedditPostBase):
    lead_score: Optional[float] = None
    score_justification: Optional[str] = None
    generated_title: Optional[str] = None
    generated_content: Optional[str] = None
    is_posted: Optional[bool] = False

class RedditPost(RedditPostBase):
    id: int
    lead_id: int
    lead_score: Optional[float] = None
    score_justification: Optional[str] = None
    generated_title: Optional[str] = None
    generated_content: Optional[str] = None
    is_posted: bool = False

    class Config:
        from_attributes = True

# Scored Reddit Post List Schema for DocumentScraperGraph
class ScoredRedditPostList(BaseModel):
    posts: List[RedditPostUpdate]

# Generated Post Content Schema for AI generation
class GeneratedPostContent(BaseModel):
    title: str
    content: str

# Lead Schemas
class LeadBase(BaseModel):
    competitor_name: str
    strength: str
    weakness: str
    related_subreddits: List[str]

    @validator('related_subreddits', pre=True, always=True)
    def parse_related_subreddits(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                raise ValueError("related_subreddits must be a valid JSON string or a list of strings")
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
