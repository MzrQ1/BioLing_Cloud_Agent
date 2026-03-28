"""特征库 - SQLite持久化存储用户画像和特征历史"""
from typing import Dict, Optional, List
from datetime import datetime, timedelta
import json
from sqlalchemy.orm import Session
from sqlalchemy import func

from .database import get_db_context
from .models import UserProfile, FeatureHistory

class FeatureStore:
    """
    特征存储 - SQLite持久化
    
    功能：
    - 用户画像长期存储
    - ML特征历史记录
    - 趋势分析统计
    """

    def save_features(self, user_id: str, features: Dict) -> bool:
        """
        保存ML提取的特征到数据库
        
        Args:
            user_id: 用户ID
            features: 特征字典，包含stress_index, emotion, heart_rate等
            
        Returns:
            是否保存成功
        """
        with get_db_context() as db:
            feature_record = FeatureHistory(
                user_id=user_id,
                timestamp=datetime.utcnow(),
                stress_index=features.get("stress_index"),
                emotion=features.get("emotion"),
                emotion_confidence=features.get("emotion_confidence"),
                risk_level=features.get("risk_level"),
                heart_rate=features.get("heart_rate"),
                sdnn=features.get("sdnn"),
                rmssd=features.get("rmssd"),
                raw_features=json.dumps(features)
            )
            db.add(feature_record)
            
            self._update_user_profile(db, user_id, features)
            
        return True

    def _update_user_profile(self, db: Session, user_id: str, features: Dict):
        """更新用户画像"""
        profile = db.query(UserProfile).filter(
            UserProfile.user_id == user_id
        ).first()
        
        if not profile:
            profile = UserProfile(user_id=user_id)
            db.add(profile)
        
        stress_index = features.get("stress_index", 0)
        if stress_index and stress_index > 0.7:
            profile.high_stress_events = (profile.high_stress_events or 0) + 1
        
        profile.total_sessions = (profile.total_sessions or 0) + 1
        
        stats = db.query(
            func.avg(FeatureHistory.heart_rate).label('avg_hr'),
            func.avg(FeatureHistory.sdnn).label('avg_sdnn'),
            func.avg(FeatureHistory.stress_index).label('avg_stress')
        ).filter(FeatureHistory.user_id == user_id).first()
        
        if stats:
            profile.avg_heart_rate = stats.avg_hr or 0
            profile.avg_sdnn = stats.avg_sdnn or 0
            profile.avg_stress_index = stats.avg_stress or 0
        
        profile.updated_at = datetime.utcnow()

    def get_user_profile(self, user_id: str) -> Optional[Dict]:
        """
        获取用户画像
        
        Args:
            user_id: 用户ID
            
        Returns:
            用户画像字典，包含历史统计信息
        """
        with get_db_context() as db:
            profile = db.query(UserProfile).filter(
                UserProfile.user_id == user_id
            ).first()
            
            if not profile:
                return None
            
            return {
                "user_id": profile.user_id,
                "avg_heart_rate": profile.avg_heart_rate,
                "avg_sdnn": profile.avg_sdnn,
                "avg_stress_index": profile.avg_stress_index,
                "total_sessions": profile.total_sessions,
                "high_stress_events": profile.high_stress_events,
                "baseline_heart_rate": profile.baseline_heart_rate,
                "baseline_sdnn": profile.baseline_sdnn,
                "preferences": json.loads(profile.preferences) if profile.preferences else {},
                "health_goals": json.loads(profile.health_goals) if profile.health_goals else [],
                "created_at": profile.created_at.isoformat() if profile.created_at else None,
                "updated_at": profile.updated_at.isoformat() if profile.updated_at else None
            }

    def update_user_profile(self, user_id: str, profile_data: Dict) -> bool:
        """
        更新用户画像特定字段
        
        Args:
            user_id: 用户ID
            profile_data: 要更新的字段
            
        Returns:
            是否更新成功
        """
        with get_db_context() as db:
            profile = db.query(UserProfile).filter(
                UserProfile.user_id == user_id
            ).first()
            
            if not profile:
                profile = UserProfile(user_id=user_id)
                db.add(profile)
            
            if "preferences" in profile_data:
                profile.preferences = json.dumps(profile_data["preferences"])
            if "health_goals" in profile_data:
                profile.health_goals = json.dumps(profile_data["health_goals"])
            if "baseline_heart_rate" in profile_data:
                profile.baseline_heart_rate = profile_data["baseline_heart_rate"]
            if "baseline_sdnn" in profile_data:
                profile.baseline_sdnn = profile_data["baseline_sdnn"]
            
            profile.updated_at = datetime.utcnow()
            
        return True

    def get_feature_trends(
        self,
        user_id: str,
        metric: str,
        days: int = 7
    ) -> List[Dict]:
        """
        获取特征趋势数据
        
        Args:
            user_id: 用户ID
            metric: 指标名称 (stress_index, heart_rate, sdnn等)
            days: 查询天数
            
        Returns:
            趋势数据列表
        """
        with get_db_context() as db:
            cutoff = datetime.utcnow() - timedelta(days=days)
            
            column_map = {
                "stress_index": FeatureHistory.stress_index,
                "heart_rate": FeatureHistory.heart_rate,
                "sdnn": FeatureHistory.sdnn,
                "rmssd": FeatureHistory.rmssd
            }
            
            column = column_map.get(metric, FeatureHistory.stress_index)
            
            results = db.query(
                FeatureHistory.timestamp,
                column.label('value')
            ).filter(
                FeatureHistory.user_id == user_id,
                FeatureHistory.timestamp >= cutoff,
                column.isnot(None)
            ).order_by(FeatureHistory.timestamp).all()
            
            return [
                {
                    "timestamp": r.timestamp.isoformat(),
                    "value": r.value
                }
                for r in results
            ]

    def get_recent_features(self, user_id: str, limit: int = 10) -> List[Dict]:
        """
        获取最近的特征记录
        
        Args:
            user_id: 用户ID
            limit: 返回数量
            
        Returns:
            特征记录列表
        """
        with get_db_context() as db:
            results = db.query(FeatureHistory).filter(
                FeatureHistory.user_id == user_id
            ).order_by(FeatureHistory.timestamp.desc()).limit(limit).all()
            
            return [
                {
                    "timestamp": r.timestamp.isoformat(),
                    "stress_index": r.stress_index,
                    "emotion": r.emotion,
                    "emotion_confidence": r.emotion_confidence,
                    "risk_level": r.risk_level,
                    "heart_rate": r.heart_rate,
                    "sdnn": r.sdnn,
                    "rmssd": r.rmssd
                }
                for r in results
            ]

    def compute_aggregated_stats(self, user_id: str, days: int = 7) -> Dict:
        """
        计算聚合统计数据
        
        Args:
            user_id: 用户ID
            days: 统计天数
            
        Returns:
            聚合统计字典
        """
        with get_db_context() as db:
            cutoff = datetime.utcnow() - timedelta(days=days)
            
            stats = db.query(
                func.avg(FeatureHistory.stress_index).label('avg'),
                func.max(FeatureHistory.stress_index).label('max'),
                func.min(FeatureHistory.stress_index).label('min'),
                func.count(FeatureHistory.id).label('count')
            ).filter(
                FeatureHistory.user_id == user_id,
                FeatureHistory.timestamp >= cutoff,
                FeatureHistory.stress_index.isnot(None)
            ).first()
            
            if not stats or stats.count == 0:
                return {
                    "avg_stress": 0,
                    "max_stress": 0,
                    "min_stress": 0,
                    "stress_trend": 0,
                    "sample_count": 0
                }
            
            first_last = db.query(FeatureHistory.stress_index).filter(
                FeatureHistory.user_id == user_id,
                FeatureHistory.timestamp >= cutoff,
                FeatureHistory.stress_index.isnot(None)
            ).order_by(FeatureHistory.timestamp).limit(1).all()
            
            last_record = db.query(FeatureHistory.stress_index).filter(
                FeatureHistory.user_id == user_id,
                FeatureHistory.timestamp >= cutoff,
                FeatureHistory.stress_index.isnot(None)
            ).order_by(FeatureHistory.timestamp.desc()).limit(1).first()
            
            first_val = first_last[0][0] if first_last else 0
            last_val = last_record[0] if last_record else 0
            trend = last_val - first_val if stats.count > 1 else 0
            
            return {
                "avg_stress": float(stats.avg or 0),
                "max_stress": float(stats.max or 0),
                "min_stress": float(stats.min or 0),
                "stress_trend": float(trend),
                "sample_count": stats.count
            }

    def get_emotion_distribution(self, user_id: str, days: int = 7) -> Dict[str, int]:
        """
        获取情绪分布统计
        
        Args:
            user_id: 用户ID
            days: 统计天数
            
        Returns:
            情绪分布字典
        """
        with get_db_context() as db:
            cutoff = datetime.utcnow() - timedelta(days=days)
            
            results = db.query(
                FeatureHistory.emotion,
                func.count(FeatureHistory.id).label('count')
            ).filter(
                FeatureHistory.user_id == user_id,
                FeatureHistory.timestamp >= cutoff,
                FeatureHistory.emotion.isnot(None)
            ).group_by(FeatureHistory.emotion).all()
            
            return {r.emotion: r.count for r in results}
