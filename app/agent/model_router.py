"""模型路由 - 大小模型协同架构"""
from typing import Optional

SIMPLE_KEYWORDS = [
    "你好", "嗨", "hey", "hi", "hello", "早上好", "下午好", "晚上好",
    "再见", "拜拜", "谢谢", "辛苦了", "打扰一下",
    "什么是", "请问", "问一下", "问一下", "你能告诉我",
    "正常吗", "可以吗", "有用吗", "是这样吗",
    "有没有", "是不是", "算不算",
    "吗", "嘛", "呀", "啊", "哦", "噢",
    "不错", "好的", "好吧", "行", "可以"
]

COMPLEX_KEYWORDS = [
    "根据我的", "我的数据", "我的情况", "最近体检",
    "压力大", "焦虑", "紧张", "失眠", "睡不着", "睡不好",
    "建议", "怎么办", "如何缓解", "怎么改善", "怎么调整",
    "为什么", "原因是什么", "是怎么回事",
    "应该", "要不要", "能不能", "可不可以",
    "麻烦", "帮我", "给我", "希望", "想要",
    "但是", "可是", "不过", "然而",
    "最近", "这段时间", "这一阵子",
    "难受", "不舒服", "不爽", "心情不好",
    "控制不住", "忍不住", "没办法"
]


def classify_query_heuristic(user_input: str, ml_features: Optional[dict] = None) -> str:
    """
    基于规则的快速分类（零延迟）

    返回: "simple" | "complex"

    分类逻辑：
    1. 如果用户直接问"根据我的数据..."，一定是复杂
    2. 如果有 ml_features 且有明确情绪/压力数据，结合关键词判断
    3. 纯关键词匹配作为兜底
    """
    if not user_input:
        return "simple"

    user_input_lower = user_input.lower()

    if ml_features and isinstance(ml_features, dict):
        emotion = ml_features.get("emotion", "unknown")
        risk_level = ml_features.get("risk_level", "low")
        stress_index = ml_features.get("stress_index", 0)

        has_meaningful_data = (
            emotion and emotion != "unknown"
        ) or (
            risk_level and risk_level not in ["low", "normal"]
        ) or (
            isinstance(stress_index, (int, float)) and stress_index > 50
        )

        if has_meaningful_data:
            if any(kw in user_input for kw in COMPLEX_KEYWORDS):
                return "complex"
            if any(kw in user_input_lower for kw in ["建议", "怎么办", "为什么", "怎么"]):
                return "complex"

            return "simple"

    if any(kw in user_input for kw in COMPLEX_KEYWORDS):
        return "complex"

    if any(kw in user_input_lower for kw in ["建议", "怎么办", "为什么", "怎么改善", "如何"]):
        return "complex"

    return "simple"


def should_use_large_model(
    user_input: str,
    ml_features: Optional[dict] = None,
    conversation_turns: int = 0
) -> tuple[str, str]:
    """
    综合路由决策：判断使用哪个模型

    返回: (model_type, reason)
        model_type: "small" | "large"
        reason: 决策原因说明

    决策规则（优先级从高到低）：
    1. 如果涉及个人数据/画像 → 大模型
    2. 如果有多轮对话上下文 → 大模型
    3. 如果有有意义的 ML 特征 → 大模型
    4. 其他情况 → 小模型
    """
    if not user_input:
        return "small", "空输入"

    if ml_features and isinstance(ml_features, dict):
        emotion = ml_features.get("emotion", "unknown")
        risk_level = ml_features.get("risk_level", "low")
        stress_index = ml_features.get("stress_index", 0)

        has_meaningful_data = (
            emotion and emotion != "unknown"
        ) or (
            risk_level and risk_level not in ["low", "normal", "low"]
        ) or (
            isinstance(stress_index, (int, float)) and stress_index > 50
        )

        if has_meaningful_data:
            return "large", "有有意义的ML特征数据"

    if conversation_turns > 3:
        return "large", f"多轮对话({conversation_turns}轮)"

    if any(pattern in user_input for pattern in [
        "根据", "我的", "我最近", "我这段时间",
        "你建议", "你觉得", "帮我分析", "麻烦帮我"
    ]):
        return "large", "涉及个人化分析"

    heuristic_result = classify_query_heuristic(user_input, ml_features)
    if heuristic_result == "complex":
        return "large", "问题复杂度较高"

    return "small", "简单问答"


def format_conversation_for_simple_model(conversation_history: list) -> str:
    """
    格式化对话历史，用于小模型的上下文窗口

    小模型上下文有限，只保留最近3轮对话
    """
    if not conversation_history:
        return "暂无对话历史"

    recent = conversation_history[-3:] if len(conversation_history) > 3 else conversation_history

    formatted = []
    for msg in recent:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if content:
            formatted.append(f"{role}: {content[:100]}")

    return "\n".join(formatted) if formatted else "暂无对话历史"
