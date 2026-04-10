"""记忆提取工具 - 从对话历史中提取关键信息并存储到用户画像"""
from typing import Optional, Dict, Any
from datetime import datetime


class MemoryExtractionTool:
    """记忆提取工具：从对话历史中智能提取用户关键信息

    功能：
    1. 分析对话历史，提取用户健康相关信息
    2. 识别用户偏好、习惯、担忧
    3. 更新用户画像
    4. 定期清理不重要记忆

    提取的信息类型：
    - 健康状况：提及的症状、疾病、担忧
    - 生活习惯：作息、饮食、运动、压力源
    - 偏好设置：沟通风格、建议类型偏好
    - 重要事件：生活变化、工作变动、情绪事件
    """

    def __init__(self):
        self.extraction_prompt = """你是一个记忆提取专家。从对话历史中提取用户的个性化信息。

## 对话历史
{conversation_history}

## 用户画像（当前）
{current_profile}

## 提取要求
请分析对话历史，提取以下类型的个性化信息：

1. **健康状况**：
   - 提及的身体症状或不适
   - 已知的健康问题或疾病
   - 健康担忧或疑虑

2. **生活习惯**：
   - 作息时间（如：经常熬夜到2点）
   - 饮食习惯（如：爱吃辣、经常喝咖啡）
   - 运动习惯（如：每周跑步3次）
   - 压力来源（如：工作压力大、项目 deadline）

3. **沟通偏好**：
   - 喜欢的回复风格（简洁/详细）
   - 感兴趣的健康话题

4. **重要事件**：
   - 生活变化（换工作、搬家、结婚等）
   - 情绪状态变化

## 输出格式
请以JSON格式输出提取的信息：

{{
    "health_info": ["从对话中提取的健康相关信息列表"],
    "habits": ["生活习惯列表"],
    "preferences": ["沟通偏好列表"],
    "events": ["重要事件列表"],
    "summary": "一段话总结用户的核心特征（50字以内）"
}}

如果对话中没有提取到任何有用信息，请输出：
{{
    "health_info": [],
    "habits": [],
    "preferences": [],
    "events": [],
    "summary": "暂无有效信息"
}}
"""

    def extract_from_conversations(
        self,
        conversation_history: list,
        current_profile: Optional[dict] = None,
        use_large_model: bool = False
    ) -> Dict[str, Any]:
        """
        从对话历史中提取记忆

        Args:
            conversation_history: 对话历史列表
            current_profile: 当前用户画像
            use_large_model: 是否使用大模型（复杂提取）

        Returns:
            Dict: 提取的记忆信息
        """
        if not conversation_history:
            return {
                "health_info": [],
                "habits": [],
                "preferences": [],
                "events": [],
                "summary": "暂无对话历史"
            }

        history_text = "\n".join([
            f"{c.get('role', 'user')}: {c.get('content', '')}"
            for c in conversation_history[-20:]
            if c.get('content')
        ])

        profile_text = str(current_profile) if current_profile else "暂无用户画像"

        prompt = self.extraction_prompt.format(
            conversation_history=history_text,
            current_profile=profile_text
        )

        if use_large_model:
            from app.agent.tools import llm_call
            result = llm_call(prompt)
        else:
            from app.agent.tools import llm_call_simple
            result = llm_call_simple(prompt)

        return self._parse_extraction_result(result)

    def _parse_extraction_result(self, result: str) -> Dict[str, Any]:
        """解析提取结果"""
        import json
        import re

        try:
            if "```json" in result:
                json_str = re.search(r'```json\s*(.*?)\s*```', result, re.DOTALL)
                if json_str:
                    result = json_str.group(1)

            data = json.loads(result)
            return data
        except json.JSONDecodeError:
            return {
                "health_info": [],
                "habits": [],
                "preferences": [],
                "events": [],
                "summary": result[:100] if result else "解析失败"
            }

    def update_user_profile(self, user_id: str, extraction_result: Dict[str, Any]):
        """将提取的记忆更新到用户画像"""
        from app.database.feature_store import FeatureStore

        if not extraction_result or extraction_result.get("summary") == "暂无有效信息":
            return False

        store = FeatureStore()
        profile = store.get_user_profile(user_id) or {}

        extracted_memories = profile.get("extracted_memories", {})

        now = datetime.now().isoformat()

        if extraction_result.get("health_info"):
            extracted_memories["health_info"] = {
                "items": extraction_result["health_info"],
                "updated_at": now
            }

        if extraction_result.get("habits"):
            extracted_memories["habits"] = {
                "items": extraction_result["habits"],
                "updated_at": now
            }

        if extraction_result.get("preferences"):
            extracted_memories["preferences"] = {
                "items": extraction_result["preferences"],
                "updated_at": now
            }

        if extraction_result.get("events"):
            extracted_memories["events"] = {
                "items": extraction_result["events"],
                "updated_at": now
            }

        if extraction_result.get("summary"):
            extracted_memories["last_summary"] = {
                "content": extraction_result["summary"],
                "updated_at": now
            }

        profile["extracted_memories"] = extracted_memories
        profile["last_memory_extraction"] = now

        store.update_user_profile(user_id, profile)

        return True

    def should_extract(self, conversation_count: int, days_since_last_extraction: int) -> bool:
        """
        判断是否需要进行记忆提取

        触发条件：
        1. 对话数量达到阈值（默认10轮）
        2. 距离上次提取超过指定天数（默认1天）
        """
        CONVERSATION_THRESHOLD = 10
        DAYS_THRESHOLD = 1

        if conversation_count >= CONVERSATION_THRESHOLD:
            return True

        if days_since_last_extraction >= DAYS_THRESHOLD and conversation_count >= 3:
            return True

        return False


memory_extraction_tool = MemoryExtractionTool()
