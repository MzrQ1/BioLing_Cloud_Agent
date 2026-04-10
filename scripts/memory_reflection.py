"""
记忆反思后台任务

定期执行记忆清理和提炼：
- 每日检查用户记忆数量
- 超过阈值时触发清理
- 生成记忆摘要
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from app.database.conversation_store import ConversationStore, MemoryReflector
from app.database.feature_store import FeatureStore


def run_memory_reflection(user_id: str = None):
    """
    执行记忆反思任务
    
    Args:
        user_id: 指定用户ID，为None时处理所有用户
    """
    print(f"\n{'='*50}")
    print(f"记忆反思任务 - {datetime.now().isoformat()}")
    print(f"{'='*50}")
    
    conv_store = ConversationStore()
    reflector = MemoryReflector()
    feature_store = FeatureStore()
    
    if user_id:
        user_ids = [user_id]
    else:
        user_ids = _get_all_active_users()
    
    total_stats = {
        'users_processed': 0,
        'total_deleted': 0,
        'total_summaries': 0
    }
    
    for uid in user_ids:
        print(f"\n处理用户: {uid}")
        
        stats = conv_store.reflect_and_clean(uid)
        print(f"  记忆清理: {stats['deleted']} 条已删除")
        total_stats['total_deleted'] += stats['deleted']
        
        summary = reflector.generate_summary(uid, days=7)
        print(f"  记忆摘要: {summary[:100]}...")
        
        patterns = reflector.extract_patterns(uid, days=30)
        if patterns.get('frequent_topics'):
            print(f"  关注话题: {', '.join(patterns['frequent_topics'][:3])}")
        
        _update_user_preferences(feature_store, uid, patterns)
        
        total_stats['users_processed'] += 1
    
    print(f"\n{'='*50}")
    print(f"任务完成统计:")
    print(f"  处理用户数: {total_stats['users_processed']}")
    print(f"  删除记忆数: {total_stats['total_deleted']}")
    print(f"{'='*50}")
    
    return total_stats


def _get_all_active_users() -> list:
    """获取所有活跃用户ID"""
    from app.database.database import get_db_context
    from app.database.models import UserProfile
    
    with get_db_context() as db:
        users = db.query(UserProfile.user_id).all()
        return [u[0] for u in users]


def _update_user_preferences(feature_store, user_id: str, patterns: dict):
    """更新用户偏好到画像"""
    if not patterns.get('frequent_topics'):
        return
    
    preferences = {
        'preferred_topics': patterns['frequent_topics'][:5],
        'preferred_interventions': patterns.get('preferred_interventions', [])[:3],
        'last_reflection': datetime.now().isoformat()
    }
    
    feature_store.update_user_profile(user_id, {'preferences': preferences})


def show_user_memory_stats(user_id: str):
    """显示用户记忆统计"""
    conv_store = ConversationStore()
    reflector = MemoryReflector()
    
    print(f"\n用户 {user_id} 记忆统计:")
    print("-" * 40)
    
    stats = conv_store.get_memory_summary(user_id, days=30)
    print(f"  近30天对话数: {stats['total_conversations']}")
    print(f"  平均压力水平: {stats['avg_stress_level']}")
    
    if stats['emotion_distribution']:
        print(f"  情绪分布:")
        for emotion, count in stats['emotion_distribution'].items():
            print(f"    - {emotion}: {count}次")
    
    patterns = reflector.extract_patterns(user_id, days=30)
    if patterns.get('frequent_topics'):
        print(f"  关注话题: {', '.join(patterns['frequent_topics'])}")
    
    recent = conv_store.get_recent_conversations(user_id, limit=5)
    print(f"\n  最近对话:")
    for conv in recent:
        role = "用户" if conv['role'] == 'user' else "助手"
        content = conv['content'][:50] + "..." if len(conv['content']) > 50 else conv['content']
        print(f"    [{role}] {content}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="记忆反思任务")
    parser.add_argument("--user", type=str, default=None, help="指定用户ID")
    parser.add_argument("--stats", type=str, default=None, help="查看用户记忆统计")
    
    args = parser.parse_args()
    
    if args.stats:
        show_user_memory_stats(args.stats)
    else:
        run_memory_reflection(args.user)
