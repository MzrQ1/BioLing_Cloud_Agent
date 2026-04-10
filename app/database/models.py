"""SQLAlchemy数据模型"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, JSON, Index
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(100), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True)
    email = Column(String(200))
    password_hash = Column(String(200))
    nickname = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime)
    is_active = Column(Boolean, default=True)
    settings = Column(Text, default="{}")

class PhysiologicalData(Base):
    """生理数据表 - 存储传感器原始数据"""
    __tablename__ = "physiological_data"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(100), index=True, nullable=False)
    device_id = Column(String(100))
    timestamp = Column(DateTime, index=True, nullable=False)
    
    heart_rate = Column(Float)
    ibi_mean = Column(Float)
    ibi_list = Column(Text)
    sdnn = Column(Float)
    rmssd = Column(Float)
    
    stress_index = Column(Float)
    emotion = Column(String(50))
    risk_level = Column(String(20))
    
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_user_timestamp', 'user_id', 'timestamp'),
    )

class UserProfile(Base):
    """用户画像表 - 长期记忆"""
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(100), unique=True, index=True, nullable=False)
    
    avg_heart_rate = Column(Float, default=0)
    avg_sdnn = Column(Float, default=0)
    avg_stress_index = Column(Float, default=0)
    
    total_sessions = Column(Integer, default=0)
    high_stress_events = Column(Integer, default=0)
    
    baseline_heart_rate = Column(Float)
    baseline_sdnn = Column(Float)
    
    preferences = Column(Text, default="{}")
    health_goals = Column(Text, default="[]")
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ConversationHistory(Base):
    """对话历史表 - 用户与智能体的交互记录"""
    __tablename__ = "conversation_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(100), index=True, nullable=False)
    session_id = Column(String(100), index=True)
    
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    
    emotion_state = Column(String(50))
    stress_level = Column(Float)
    risk_level = Column(String(20))
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index('idx_user_session', 'user_id', 'session_id'),
    )

class FeatureHistory(Base):
    """特征历史表 - ML提取的特征记录"""
    __tablename__ = "feature_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(100), index=True, nullable=False)
    
    timestamp = Column(DateTime, index=True, nullable=False)
    
    stress_index = Column(Float)
    emotion = Column(String(50))
    emotion_confidence = Column(Float)
    risk_level = Column(String(20))
    
    heart_rate = Column(Float)
    sdnn = Column(Float)
    rmssd = Column(Float)
    
    raw_features = Column(Text)
    
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_feature_user_time', 'user_id', 'timestamp'),
    )

class Report(Base):
    """报告表 - 生成的健康报告"""
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
