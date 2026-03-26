"""报告格式化服务"""
from typing import Dict, Optional
from datetime import datetime

class ReportFormatter:
    def format_daily_report(self, data: Dict) -> str:
        sections = []

        sections.append("📊 今日健康概览")
        sections.append("-" * 30)
        sections.append(f"平均心率: {data.get('avg_heart_rate', 70)} bpm")
        sections.append(f"压力指数: {data.get('stress_index', 50)}/100")
        sections.append(f"睡眠质量: {data.get('sleep_quality', '良好')}")

        stress_level = data.get('stress_level', 'moderate')
        emoji_map = {
            'low': '🟢',
            'moderate': '🟡',
            'high': '🟠',
            'critical': '🔴'
        }
        emoji = emoji_map.get(stress_level, '🟡')
        sections.append(f"\n整体状态: {emoji} {stress_level.upper()}")

        suggestions = data.get('suggestions', [])
        if suggestions:
            sections.append("\n💡 建议:")
            for s in suggestions[:3]:
                sections.append(f"  • {s}")

        return "\n".join(sections)

    def format_weekly_report(self, data: Dict) -> str:
        sections = []

        sections.append("📈 本周健康周报")
        sections.append("=" * 30)

        sections.append("\n【数据摘要】")
        sections.append(f"记录天数: {data.get('days_recorded', 7)}")
        sections.append(f"平均压力: {data.get('avg_stress', 50)}/100")
        sections.append(f"压力峰值: {data.get('max_stress', 80)} (出现在{data.get('peak_day', '周三')})")

        trends = data.get('trends', {})
        if trends:
            sections.append("\n【趋势分析】")
            for metric, trend in trends.items():
                direction = "↑" if trend > 0 else "↓"
                sections.append(f"  {metric}: {direction} {abs(trend):.1f}%")

        sections.append("\n【亮点与建议】")
        highlights = data.get('highlights', [])
        for h in highlights:
            sections.append(f"  ✨ {h}")

        return "\n".join(sections)

    def format_instant_feedback(self, data: Dict) -> str:
        emotion = data.get('emotion', 'unknown')
        stress = data.get('stress_index', 50)

        messages = {
            'calm': f"🌿 当前状态平静，心率变异性良好。继续保持！",
            'relaxed': f"😊 状态放松，压力指数{stress}，一切正常。",
            'mild_stress': f"🤔 检测到轻度压力({stress})，建议休息片刻。",
            'moderate_stress': f"⚠️ 中度压力({stress})，建议尝试深呼吸放松。",
            'high_stress': f"🚨 高压力状态({stress})，建议立即采取放松措施。"
        }

        return messages.get(emotion, f"当前压力指数: {stress}")
