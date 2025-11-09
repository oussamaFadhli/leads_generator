from sqlalchemy import Column, Integer, String, Text, ForeignKey, Boolean, Float
import json
from typing import List, Optional
from sqlalchemy.orm import relationship
from app.core.database import Base

class Feature(Base):
    __tablename__ = "features"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(Text)
    saas_info_id = Column(Integer, ForeignKey("saas_info.id"))

class PricingPlan(Base):
    __tablename__ = "pricing_plans"
    id = Column(Integer, primary_key=True, index=True)
    plan_name = Column(String, index=True)
    price = Column(String)
    features = Column(Text)  # Storing as text, could be JSON or a separate table
    link = Column(String, nullable=True)
    saas_info_id = Column(Integer, ForeignKey("saas_info.id"))

class SaaSInfo(Base):
    __tablename__ = "saas_info"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    one_liner = Column(Text)
    target_segments = Column(Text) # Storing as JSON string

    @property
    def target_segments_list(self) -> Optional[List[str]]:
        if self.target_segments:
            return json.loads(self.target_segments)
        return None

    features = relationship("Feature", backref="saas_info", cascade="all, delete-orphan")
    pricing = relationship("PricingPlan", backref="saas_info", cascade="all, delete-orphan")
    leads = relationship("Lead", backref="saas_info", cascade="all, delete-orphan")

class Lead(Base):
    __tablename__ = "leads"
    id = Column(Integer, primary_key=True, index=True)
    competitor_name = Column(String, index=True)
    strengths = Column(Text) # Storing as JSON string
    weaknesses = Column(Text) # Storing as JSON string
    related_subreddits = Column(Text) # Storing as JSON string
    saas_info_id = Column(Integer, ForeignKey("saas_info.id"))
    reddit_posts = relationship("RedditPost", backref="lead", cascade="all, delete-orphan")

    @property
    def strengths_list(self) -> Optional[List[str]]:
        if self.strengths:
            return json.loads(self.strengths)
        return None

    @property
    def weaknesses_list(self) -> Optional[List[str]]:
        if self.weaknesses:
            return json.loads(self.weaknesses)
        return None

    @property
    def related_subreddits_list(self) -> Optional[List[str]]:
        if self.related_subreddits:
            return json.loads(self.related_subreddits)
        return None

class RedditPost(Base):
    __tablename__ = "reddit_posts"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    content = Column(Text)
    score = Column(Integer)
    num_comments = Column(Integer)
    author = Column(String)
    url = Column(String)
    subreddit = Column(String, index=True)
    lead_score = Column(Float, nullable=True)
    score_justification = Column(Text, nullable=True)
    generated_title = Column(String, nullable=True)
    generated_content = Column(Text, nullable=True)
    is_posted = Column(Boolean, default=False)
    ai_generated = Column(Boolean, default=False)
    lead_id = Column(Integer, ForeignKey("leads.id"))
