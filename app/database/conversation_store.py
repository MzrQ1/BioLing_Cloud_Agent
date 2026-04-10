"""
对话记忆存储模块 - 智能筛选与动态反思

核心机制：
1. 三维筛选评分：持久性价值 + 结构化程度 + 个性化价值
2. 动态反思机制：定期提炼内容，删除低价值记忆

记忆评分公式：
    memory_score = w1 * persistence + w2 * structure + w3 * personalization
    
    其中 w1=0.4, w2=0.3, w3=0.3（可配置）
"""
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import json
import re
from sqlalchemy import and_, func, or_

from .database import get_db_context
from .models import ConversationHistory


class MemoryScorer:
    """
    记忆评分器 - 三维筛选机制
    
    评估维度：
    1. 持久性价值 (persistence): 信息是否具有长期参考价值
    2. 结构化程度 (structure): 信息是否清晰、有条理
    3. 个性化价值 (personalization): 信息是否与用户个人相关
    """
    
    PERSISTENCE_KEYWORDS = {
        'high': [
            '习惯', '偏好', '目标', '计划', '规律', '周期', '长期', '持续',
            '总是', '经常', '每天', '每周', '定期', '习惯性', '慢性'
        ],
        'medium': [
            '最近', '这段', '目前', '现在', '当前', '近期', '一阵子'
        ],
        'low': [
            '刚才', '临时', '偶尔', '一次', '突然', '暂时', '片刻'
        ]
    }
    
    STRUCTURE_PATTERNS = {
        'list': r'^\s*[-•]\s+|^\s*\d+[.、]\s+',
        'steps': r'首先|其次|然后|最后|第一步|第二步',
        'condition': r'如果|当|若|假如|一旦',
        'summary': r'总之|综上|总结|概括|要点'
    }
    
    PERSONALIZATION_KEYWORDS = {
        'high': [
            '我', '我的', '我觉得', '我感觉', '我认为', '我希望', '我需要',
            '对我', '帮我', '给我', '适合我', '根据我的'
        ],
        'medium': [
            '用户', '大家', '人们', '一般人', '普通人'
        ],
        'low': [
            '任何人', '所有人', '每个人', '普遍', '一般'
        ]
    }
    
    def __init__(
        self,
        persistence_weight: float = 0.4,
        structure_weight: float = 0.3,
        personalization_weight: float = 0.3
    ):
        self.w_persistence = persistence_weight
        self.w_structure = structure_weight
        self.w_personalization = personalization_weight
    
    def score(self, content: str, context: Optional[Dict] = None) -> Dict[str, float]:
        """
        计算记忆的综合评分
        
        Args:
            content: 对话内容
            context: 上下文信息（情绪状态、压力等级等）
            
        Returns:
            包含各维度分数和总分的字典
        """
        persistence = self._score_persistence(content)
        structure = self._score_structure(content)
        personalization = self._score_personalization(content, context)
        
        total = (
            self.w_persistence * persistence +
            self.w_structure * structure +
            self.w_personalization * personalization
        )
        
        return {
            'persistence': round(persistence, 3),
            'structure': round(structure, 3),
            'personalization': round(personalization, 3),
            'total': round(total, 3)
        }
    
    def _score_persistence(self, content: str) -> float:
        """评估持久性价值 (0-1)"""
        score = 0.5
        
        for keyword in self.PERSISTENCE_KEYWORDS['high']:
            if keyword in content:
                score += 0.15
        
        for keyword in self.PERSISTENCE_KEYWORDS['medium']:
            if keyword in content:
                score += 0.05
        
        for keyword in self.PERSISTENCE_KEYWORDS['low']:
            if keyword in content:
                score -= 0.1
        
        return max(0.0, min(1.0, score))
    
    def _score_structure(self, content: str) -> float:
        """评估结构化程度 (0-1)"""
        score = 0.3
        
        for pattern_name, pattern in self.STRUCTURE_PATTERNS.items():
            matches = re.findall(pattern, content, re.MULTILINE)
            if matches:
                if pattern_name == 'list':
                    score += min(0.2, len(matches) * 0.05)
                elif pattern_name == 'steps':
                    score += min(0.25, len(matches) * 0.08)
                elif pattern_name == 'condition':
                    score += 0.1
                elif pattern_name == 'summary':
                    score += 0.15
        
        sentences = re.split(r'[。！？.!?]', content)
        if len(sentences) >= 3:
            score += 0.1
        
        return max(0.0, min(1.0, score))
    
    def _score_personalization(self, content: str, context: Optional[Dict]) -> float:
        """评估个性化价值 (0-1)"""
        score = 0.4
        
        for keyword in self.PERSONALIZATION_KEYWORDS['high']:
            if keyword in content:
                score += 0.15
        
        for keyword in self.PERSONALIZATION_KEYWORDS['medium']:
            if keyword in content:
                score += 0.05
        
        for keyword in self.PERSONALIZATION_KEYWORDS['low']:
            if keyword in content:
                score -= 0.1
        
        if context:
            stress = context.get('stress_level') or 0
            if stress > 0.7:
                score += 0.1
            emotion = context.get('emotion_state', '')
            if emotion in ['焦虑', '紧张', '疲惫', '压力大']:
                score += 0.1
        
        return max(0.0, min(1.0, score))


class ConversationStore:
    """
    对话记忆存储器
    
    功能：
    - 智能筛选存储：只保存高价值对话
    - 动态反思：定期提炼和清理记忆
    - 查询接口：支持多维度检索
    """
    
    STORAGE_THRESHOLD = 0.5
    MAX_MEMORIES_PER_USER = 500
    REFLECTION_INTERVAL_DAYS = 7
    
    def __init__(self, storage_threshold: float = None):
        self.scorer = MemoryScorer()
        if storage_threshold:
            self.STORAGE_THRESHOLD = storage_threshold
    
    def save_conversation(
        self,
        user_id: str,
        role: str,
        content: str,
        session_id: Optional[str] = None,
        context: Optional[Dict] = None
    ) -> Optional[int]:
        """
        保存对话（带智能筛选）
        
        Args:
            user_id: 用户ID
            role: 角色 (user/assistant)
            content: 对话内容
            session_id: 会话ID
            context: 上下文信息
            
        Returns:
            保存成功返回记录ID，否则返回None
        """
        scores = self.scorer.score(content, context)
        
        if scores['total'] < self.STORAGE_THRESHOLD:
            return None
        
        with get_db_context() as db:
            record = ConversationHistory(
                user_id=user_id,
                session_id=session_id,
                role=role,
                content=content,
                emotion_state=context.get('emotion_state') if context else None,
                stress_level=context.get('stress_level') if context else None,
                risk_level=context.get('risk_level') if context else None
            )
            db.add(record)
            db.flush()
            record_id = record.id
        
        return record_id
    
    def save_conversation_batch(
        self,
        user_id: str,
        conversations: List[Dict],
        session_id: Optional[str] = None
    ) -> int:
        """
        批量保存对话（自动筛选）
        
        Args:
            user_id: 用户ID
            conversations: 对话列表，每项包含role, content, context
            session_id: 会话ID
            
        Returns:
            成功保存的数量
        """
        saved_count = 0
        for conv in conversations:
            record_id = self.save_conversation(
                user_id=user_id,
                role=conv.get('role', 'user'),
                content=conv.get('content', ''),
                session_id=session_id,
                context=conv.get('context')
            )
            if record_id:
                saved_count += 1
        
        return saved_count
    
    def get_recent_conversations(
        self,
        user_id: str,
        limit: int = 20
    ) -> List[Dict]:
        """
        获取最近的对话记录
        
        Args:
            user_id: 用户ID
            limit: 返回数量
            
        Returns:
            对话记录列表
        """
        with get_db_context() as db:
            results = db.query(ConversationHistory).filter(
                ConversationHistory.user_id == user_id
            ).order_by(
                ConversationHistory.created_at.desc()
            ).limit(limit).all()
            
            return [self._record_to_dict(r) for r in reversed(results)]
    
    def search_conversations(
        self,
        user_id: str,
        query: str,
        limit: int = 10
    ) -> List[Dict]:
        """
        搜索对话记录
        
        Args:
            user_id: 用户ID
            query: 搜索关键词
            limit: 返回数量
            
        Returns:
            匹配的对话记录
        """
        with get_db_context() as db:
            results = db.query(ConversationHistory).filter(
                and_(
                    ConversationHistory.user_id == user_id,
                    ConversationHistory.content.contains(query)
                )
            ).order_by(
                ConversationHistory.created_at.desc()
            ).limit(limit).all()
            
            return [self._record_to_dict(r) for r in results]
    
    def get_conversations_by_emotion(
        self,
        user_id: str,
        emotion: str,
        days: int = 30
    ) -> List[Dict]:
        """
        按情绪状态获取对话
        
        Args:
            user_id: 用户ID
            emotion: 情绪类型
            days: 查询天数
            
        Returns:
            对话记录列表
        """
        with get_db_context() as db:
            cutoff = datetime.utcnow() - timedelta(days=days)
            
            results = db.query(ConversationHistory).filter(
                and_(
                    ConversationHistory.user_id == user_id,
                    ConversationHistory.emotion_state == emotion,
                    ConversationHistory.created_at >= cutoff
                )
            ).order_by(ConversationHistory.created_at).all()
            
            return [self._record_to_dict(r) for r in results]
    
    def reflect_and_clean(self, user_id: str) -> Dict:
        """
        动态反思机制：提炼内容，清理低价值记忆
        
        流程：
        1. 统计当前记忆数量
        2. 如果超过阈值，触发清理
        3. 重新评分历史记忆
        4. 删除低价值记忆
        5. 提炼高价值记忆摘要
        
        Args:
            user_id: 用户ID
            
        Returns:
            清理统计信息
        """
        stats = {
            'total_before': 0,
            'deleted': 0,
            'summarized': 0,
            'total_after': 0
        }
        
        with get_db_context() as db:
            total_count = db.query(func.count(ConversationHistory.id)).filter(
                ConversationHistory.user_id == user_id
            ).scalar()
            
            stats['total_before'] = total_count
            
            if total_count <= self.MAX_MEMORIES_PER_USER * 0.8:
                return stats
            
            all_records = db.query(ConversationHistory).filter(
                ConversationHistory.user_id == user_id
            ).order_by(ConversationHistory.created_at).all()
            
            to_delete = []
            
            for record in all_records:
                scores = self.scorer.score(record.content, {
                    'emotion_state': record.emotion_state,
                    'stress_level': record.stress_level
                })
                
                age_days = (datetime.utcnow() - record.created_at).days
                
                if scores['total'] < 0.3 and age_days > 3:
                    to_delete.append(record.id)
                elif scores['total'] < 0.4 and age_days > 7:
                    to_delete.append(record.id)
                elif scores['total'] < 0.5 and age_days > 14:
                    to_delete.append(record.id)
            
            if to_delete:
                db.query(ConversationHistory).filter(
                    ConversationHistory.id.in_(to_delete)
                ).delete(synchronize_session=False)
                stats['deleted'] = len(to_delete)
            
            final_count = db.query(func.count(ConversationHistory.id)).filter(
                ConversationHistory.user_id == user_id
            ).scalar()
            stats['total_after'] = final_count
        
        return stats
    
    def get_memory_summary(self, user_id: str, days: int = 7) -> Dict:
        """
        获取记忆摘要统计
        
        Args:
            user_id: 用户ID
            days: 统计天数
            
        Returns:
            摘要统计信息
        """
        with get_db_context() as db:
            cutoff = datetime.utcnow() - timedelta(days=days)
            
            total = db.query(func.count(ConversationHistory.id)).filter(
                and_(
                    ConversationHistory.user_id == user_id,
                    ConversationHistory.created_at >= cutoff
                )
            ).scalar()
            
            emotion_dist = db.query(
                ConversationHistory.emotion_state,
                func.count(ConversationHistory.id)
            ).filter(
                and_(
                    ConversationHistory.user_id == user_id,
                    ConversationHistory.created_at >= cutoff,
                    ConversationHistory.emotion_state.isnot(None)
                )
            ).group_by(ConversationHistory.emotion_state).all()
            
            avg_stress = db.query(
                func.avg(ConversationHistory.stress_level)
            ).filter(
                and_(
                    ConversationHistory.user_id == user_id,
                    ConversationHistory.created_at >= cutoff,
                    ConversationHistory.stress_level.isnot(None)
                )
            ).scalar()
            
            return {
                'total_conversations': total,
                'emotion_distribution': {e: c for e, c in emotion_dist if e},
                'avg_stress_level': round(float(avg_stress or 0), 2),
                'period_days': days
            }
    
    def _record_to_dict(self, record: ConversationHistory) -> Dict:
        """将数据库记录转换为字典"""
        return {
            'id': record.id,
            'user_id': record.user_id,
            'session_id': record.session_id,
            'role': record.role,
            'content': record.content,
            'emotion_state': record.emotion_state,
            'stress_level': record.stress_level,
            'risk_level': record.risk_level,
            'created_at': record.created_at.isoformat() if record.created_at else None
        }


class MemoryReflector:
    """
    记忆反思器 - 定期提炼和总结
    
    功能：
    - 提取用户偏好模式
    - 生成记忆摘要
    - 识别重要事件
    """
    
    def __init__(self):
        self.store = ConversationStore()
    
    def extract_patterns(self, user_id: str, days: int = 30) -> Dict:
        """
        提取用户行为模式
        
        Args:
            user_id: 用户ID
            days: 分析天数
            
        Returns:
            模式分析结果
        """
        conversations = self.store.get_recent_conversations(user_id, limit=100)
        
        user_messages = [c for c in conversations if c['role'] == 'user']
        
        patterns = {
            'frequent_topics': self._extract_topics(user_messages),
            'emotion_trends': self._analyze_emotion_trends(conversations),
            'stress_patterns': self._analyze_stress_patterns(conversations),
            'preferred_interventions': self._extract_interventions(conversations)
        }
        
        return patterns
    
    def generate_summary(self, user_id: str, days: int = 7) -> str:
        """
        生成记忆摘要
        
        Args:
            user_id: 用户ID
            days: 摘要天数
            
        Returns:
            摘要文本
        """
        stats = self.store.get_memory_summary(user_id, days)
        patterns = self.extract_patterns(user_id, days)
        
        summary_parts = []
        
        summary_parts.append(f"过去{days}天共记录{stats['total_conversations']}次对话。")
        
        if stats['emotion_distribution']:
            top_emotion = max(stats['emotion_distribution'].items(), key=lambda x: x[1])
            summary_parts.append(f"主要情绪状态：{top_emotion[0]}（{top_emotion[1]}次）。")
        
        if stats['avg_stress_level'] > 0:
            stress_level = "较高" if stats['avg_stress_level'] > 0.6 else "中等" if stats['avg_stress_level'] > 0.3 else "较低"
            summary_parts.append(f"平均压力水平{stress_level}（{stats['avg_stress_level']:.1f}）。")
        
        if patterns.get('frequent_topics'):
            topics = '、'.join(patterns['frequent_topics'][:3])
            summary_parts.append(f"关注话题：{topics}。")
        
        return ''.join(summary_parts)
    
    def _extract_topics(self, messages: List[Dict]) -> List[str]:
        """提取高频话题"""
        topic_keywords = {
            '睡眠': ['睡眠', '睡觉', '失眠', '入睡', '早醒'],
            '压力': ['压力', '紧张', '焦虑', '烦躁'],
            '运动': ['运动', '锻炼', '跑步', '健身'],
            '饮食': ['饮食', '吃饭', '营养', '食欲'],
            '情绪': ['情绪', '心情', '感受', '感觉'],
            '工作': ['工作', '加班', '任务', '项目']
        }
        
        topic_counts = {topic: 0 for topic in topic_keywords}
        
        for msg in messages:
            content = msg.get('content', '')
            for topic, keywords in topic_keywords.items():
                for kw in keywords:
                    if kw in content:
                        topic_counts[topic] += 1
                        break
        
        sorted_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)
        return [t for t, c in sorted_topics if c > 0]
    
    def _analyze_emotion_trends(self, conversations: List[Dict]) -> Dict:
        """分析情绪趋势"""
        emotions = [c['emotion_state'] for c in conversations if c.get('emotion_state')]
        
        if not emotions:
            return {'trend': 'unknown', 'dominant': None}
        
        from collections import Counter
        emotion_counts = Counter(emotions)
        
        return {
            'trend': 'stable',
            'dominant': emotion_counts.most_common(1)[0][0] if emotion_counts else None,
            'distribution': dict(emotion_counts)
        }
    
    def _analyze_stress_patterns(self, conversations: List[Dict]) -> Dict:
        """分析压力模式"""
        stress_levels = [c['stress_level'] for c in conversations if c.get('stress_level') is not None]
        
        if not stress_levels:
            return {'pattern': 'unknown', 'avg': 0}
        
        return {
            'pattern': 'fluctuating',
            'avg': round(sum(stress_levels) / len(stress_levels), 2),
            'max': max(stress_levels),
            'min': min(stress_levels)
        }
    
    def _extract_interventions(self, conversations: List[Dict]) -> List[str]:
        """提取用户偏好的干预方式"""
        intervention_keywords = {
            '呼吸练习': ['呼吸', '深呼吸', '4-7-8'],
            '冥想': ['冥想', '正念', '放松'],
            '运动': ['运动', '散步', '跑步'],
            '休息': ['休息', '睡觉', '小憩']
        }
        
        found_interventions = []
        
        for conv in conversations:
            content = conv.get('content', '')
            for intervention, keywords in intervention_keywords.items():
                for kw in keywords:
                    if kw in content and intervention not in found_interventions:
                        found_interventions.append(intervention)
                        break
        
        return found_interventions
