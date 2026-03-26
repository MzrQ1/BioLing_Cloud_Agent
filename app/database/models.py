"""SQLAlchemy模型"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(100), unique=True, index=True, nullable=False)
    username = Column(String(100))
    email = Column(String(200))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    is_active = Column(Boolean, default=True)
    settings = Column(Text, default="{}")

class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(100), index=True, nullable=False)
    session_id = Column(String(100))

    report_content = Column(Text)
    suggestion = Column(Text)
    risk_level = Column(String(50))

    ml_features = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    is_read = Column(Boolean, default=False)
    user_feedback = Column(Text)
