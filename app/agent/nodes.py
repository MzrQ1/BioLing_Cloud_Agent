"""节点逻辑 - LangGraph健康智能体节点"""
from langgraph.graph import END
from .state import HealthState, RiskLevel, InterventionType
from datetime import datetime

def quick_check_node(state: HealthState) -> HealthState:
    """
    快速判断节点：判断问题类型，决定后续路径

    仅做轻量级分析，不加载任何外部数据
    目的：快速判断是简单回复还是复杂分析
    """
    from app.agent.model_router import should_use_large_model

    user_input = state.get("user_input", "")
    ml_features = state.get("ml_features")

    model_type, route_reason = should_use_large_model(
        user_input=user_input,
        ml_features=ml_features,
        conversation_turns=0
    )

    print(f"[快速判断] 类型: {model_type} | 原因: {route_reason}")

    state["query_complexity"] = model_type
    state["route_reason"] = route_reason
    state["next_node"] = "simple_response" if model_type == "small" else "memory_retrieval"

    return state


def simple_response_node(state: HealthState) -> HealthState:
    """
    简单回复节点：使用小模型快速回复

    特点：
    1. 不走 RAG 知识库（节省检索时间）
    2. 不做 ML 情绪识别（因为你没有模型）
    3. 只加载最基本的上下文（用户画像、少量对话历史）
    4. 使用 Ollama 本地小模型
    5. 快速响应（目标 < 2秒）
    """
    from app.agent.tools import llm_call_simple
    from app.agent.prompts import SIMPLE_CHAT_PROMPT
    from app.database.feature_store import FeatureStore
    from app.database.conversation_store import ConversationStore

    user_input = state.get("user_input", "")
    user_id = state.get("user_id", "default_user")

    profile_store = FeatureStore()
    profile = profile_store.get_user_profile(user_id) or {}

    conv_store = ConversationStore()
    recent_convs = conv_store.get_recent_conversations(user_id=user_id, limit=10)

    history_text = "\n".join([
        f"{c.get('role', 'user')}: {c.get('content', '')}"
        for c in recent_convs[-10:]
        if c.get('content')
    ]) if recent_convs else "暂无对话历史"

    profile_text = _build_profile_text(profile)

    prompt = f"""你是BioLid健康助手，进行简单友好的对话。

用户画像:
{profile_text}

对话历史:
{history_text}

用户: {user_input}

要求：
- 回复简洁，1-3句话
- 温暖友好
- 直接回答问题
- 如果涉及健康知识，简单说明即可
- 如果用户提到之前讨论过的内容，可以结合历史对话

请回复用户："""

    try:
        suggestion = llm_call_simple(prompt)
        if not suggestion:
            suggestion = "你好！有什么我可以帮助你的吗？"
    except Exception as e:
        print(f"[简单回复错误] {str(e)}")
        suggestion = "你好！有什么我可以帮助你的吗？"

    state["suggestion"] = suggestion
    state["model_used"] = "small"
    state["query_complexity"] = state.get("query_complexity", "small")
    state["route_reason"] = state.get("route_reason", "快速路径")
    state["next_node"] = "interaction_reflection"
    state["should_continue"] = False

    return state


def _build_profile_text(profile: dict) -> str:
    """构建用户画像文本"""
    if not profile:
        return "暂无用户画像"

    parts = []

    if profile.get("avg_stress"):
        parts.append(f"压力水平: {profile.get('avg_stress')}")

    extracted = profile.get("extracted_memories", {})
    if extracted:
        if extracted.get("health_info"):
            items = extracted["health_info"].get("items", [])
            if items:
                parts.append(f"健康状况: {', '.join(items[:3])}")

        if extracted.get("habits"):
            items = extracted["habits"].get("items", [])
            if items:
                parts.append(f"生活习惯: {', '.join(items[:3])}")

        if extracted.get("last_summary"):
            summary = extracted["last_summary"].get("content", "")
            if summary and summary != "暂无有效信息":
                parts.append(f"用户特征: {summary}")

    return "\n".join(parts) if parts else "暂无详细画像"


def memory_retrieval_node(state: HealthState) -> HealthState:
    """记忆检索节点：始终加载用户画像和对话历史
    
    功能：
    1. 从数据库获取用户画像（长期记忆）
    2. 获取最近的对话历史（短期记忆）
    3. 为后续的个性化建议生成提供上下文
    
    无论是否有传感器数据，此节点都会执行
    """
    from app.database.feature_store import FeatureStore
    from app.database.conversation_store import ConversationStore

    user_id = state["user_id"]

    feature_store = FeatureStore()
    profile = feature_store.get_user_profile(user_id) or {}

    conv_store = ConversationStore()
    recent_conversations = conv_store.get_recent_conversations(
        user_id=user_id,
        limit=10
    )

    conversation_history = []
    for conv in recent_conversations:
        role = conv.get("role", "assistant")
        content = conv.get("content", "")
        if content:
            conversation_history.append({"role": role, "content": content})

    state["long_term_profile"] = profile
    state["short_term_memory"] = conversation_history
    return state


def sensor_processing_node(state: HealthState) -> HealthState:
    """传感器数据处理节点：处理生理数据并进行分析
    
    功能：
    1. 存储传感器数据到短记忆
    2. 更新用户画像
    3. 进行ML情绪识别
    4. 异常检测和风险判断
    
    仅在有传感器数据时执行
    """
    raw_data = state.get("raw_sensor_data", {})

    memory_entry = {
        "timestamp": datetime.now().isoformat(),
        "data": raw_data,
        "processed_features": state.get("processed_features")
    }
    
    short_memory = state.get("short_term_memory", [])
    short_memory.append({
        "type": "sensor_data",
        **memory_entry
    })
    if len(short_memory) > 15:
        short_memory = short_memory[-15:]
    state["short_term_memory"] = short_memory

    from app.database.feature_store import FeatureStore
    user_id = state["user_id"]
    features = state.get("processed_features", {})

    store = FeatureStore()
    profile = state.get("long_term_profile", {}) or {}

    if features:
        profile["last_update"] = datetime.now().isoformat()
        profile["recent_features"] = features
        avg_stress = features.get("stress_index", 0)
        profile["avg_stress"] = avg_stress
        store.update_user_profile(user_id, profile)

    state["long_term_profile"] = profile

    from app.ml_services.inference_engine import InferenceEngine
    if features:
        try:
            engine = InferenceEngine()
            ml_result = engine.predict_emotion(features)
            state["ml_features"] = ml_result
            state["risk_level"] = ml_result.get("risk_level", RiskLevel.LOW)
        except Exception as e:
            state["ml_features"] = {"emotion": "unknown", "confidence": 0.0, "error": str(e)}
            state["risk_level"] = RiskLevel.LOW
    else:
        state["ml_features"] = {"emotion": "unknown", "confidence": 0.0}
        state["risk_level"] = RiskLevel.LOW

    risk_level = state.get("risk_level", RiskLevel.LOW)
    ml_features = state.get("ml_features") or {}

    should_intervene = False
    intervention_type = InterventionType.NONE
    device_command = None

    if risk_level == RiskLevel.CRITICAL:
        should_intervene = True
        intervention_type = InterventionType.IMMEDIATE
        device_command = {
            "device": "smart_eye_mask",
            "action": "activate_relaxation",
            "duration_seconds": 300,
            "intensity": "high"
        }
    elif risk_level == RiskLevel.HIGH:
        should_intervene = True
        intervention_type = InterventionType.IMMEDIATE
        device_command = {
            "device": "smart_eye_mask",
            "action": "activate_relaxation",
            "duration_seconds": 180,
            "intensity": "medium"
        }
    elif isinstance(ml_features, dict) and ml_features.get("stress_trend", 0) > 0.7:
        should_intervene = True
        intervention_type = InterventionType.LONG_TERM

    state["intervention_type"] = intervention_type
    state["device_command"] = device_command
    state["should_continue"] = should_intervene
    return state


def rag_knowledge_base_node(state: HealthState) -> HealthState:
    """RAG知识库节点：智能检索相关健康知识
    
    查询策略：
    1. 如果有用户输入且无传感器数据 → 使用用户输入作为查询
    2. 如果有传感器数据 → 使用ML特征生成查询
    3. 如果两者都有 → 结合两者生成查询
    
    始终执行此节点，确保每次交互都经过知识库检索
    """
    from app.database.vector_store import VectorStore

    user_input = state.get("user_input", "")
    ml_features = state.get("ml_features") or {}
    long_term_profile = state.get("long_term_profile") or {}

    if user_input and not ml_features.get("emotion"):
        user_query = user_input
        
        if long_term_profile:
            user_profile_context = f"用户画像: 压力水平={long_term_profile.get('avg_stress', '未知')}, "
            user_profile_context += f"最近更新={long_term_profile.get('last_update', '未知')}"
            user_query = f"{user_input}\n\n{user_profile_context}"
    elif ml_features and ml_features.get("emotion") != "unknown":
        user_query = f"stress={ml_features.get('stress_index', 0)}, "
        user_query += f"emotion={ml_features.get('emotion', 'unknown')}, "
        user_query += f"risk_level={state.get('risk_level', 'unknown')}"
        
        if user_input:
            user_query = f"{user_input}\n\n{user_query}"
    else:
        user_query = user_input or "健康咨询"

    vector_store = VectorStore()
    
    try:
        rag_results = vector_store.query(user_query, top_k=3)
        if rag_results is None:
            rag_results = []
    except Exception as e:
        print(f"[RAG节点错误] 查询失败: {str(e)}")
        rag_results = []

    state["rag_context"] = rag_results
    return state


def suggestion_generation_node(state: HealthState) -> HealthState:
    """建议生成节点：智能选择大小模型

    路由策略：
    1. 根据问题复杂度选择模型
    2. 简单问答 → 小模型（Ollama本地）
    3. 复杂分析 → 大模型（DashScope）
    4. 小模型失败时自动 fallback 到大模型

    节省成本和响应时间
    """
    from app.agent.prompts import UNIFIED_SUGGESTION_PROMPT, SIMPLE_CHAT_PROMPT
    from app.agent.tools import llm_call, llm_call_simple
    from app.agent.model_router import should_use_large_model, format_conversation_for_simple_model

    rag_context = state.get("rag_context") or []
    ml_features = state.get("ml_features") or {}
    risk_level = state.get("risk_level", RiskLevel.LOW)
    long_term_profile = state.get("long_term_profile") or {}
    user_input = state.get("user_input", "")
    short_term_memory = state.get("short_term_memory") or []

    if not isinstance(rag_context, list):
        rag_context = []

    if not isinstance(short_term_memory, list):
        short_term_memory = []

    conversation_turns = len([m for m in short_term_memory if isinstance(m, dict) and m.get('type') != 'sensor_data'])

    model_type, route_reason = should_use_large_model(
        user_input=user_input,
        ml_features=ml_features if ml_features.get("emotion") != "unknown" else None,
        conversation_turns=conversation_turns
    )

    print(f"[模型路由] 类型: {model_type} | 原因: {route_reason} | 输入: {user_input[:30]}...")

    if model_type == "small":
        context_text = "\n".join([
            f"- {item.get('content', '')}" for item in rag_context[:2] if isinstance(item, dict)
        ]) if rag_context else "无可用健康知识参考"

        conversation_history = format_conversation_for_simple_model(
            [m for m in short_term_memory if isinstance(m, dict) and m.get('type') != 'sensor_data']
        )

        prompt = SIMPLE_CHAT_PROMPT.format(
            user_input=f"{user_input}\n\n[健康知识参考: {context_text}]" if rag_context else user_input,
            conversation_history=conversation_history
        )

        try:
            suggestion = llm_call_simple(prompt)

            if not suggestion:
                print(f"[模型路由] 小模型未返回结果，fallback到大模型")
                model_type = "large"
                suggestion = _generate_large_model_suggestion(
                    user_input, rag_context, ml_features, risk_level,
                    long_term_profile, short_term_memory
                )
        except Exception as e:
            print(f"[小模型调用错误] {str(e)}，fallback到大模型")
            model_type = "large"
            suggestion = _generate_large_model_suggestion(
                user_input, rag_context, ml_features, risk_level,
                long_term_profile, short_term_memory
            )
    else:
        suggestion = _generate_large_model_suggestion(
            user_input, rag_context, ml_features, risk_level,
            long_term_profile, short_term_memory
        )

    state["suggestion"] = suggestion
    state["model_used"] = model_type
    state["next_node"] = "interaction_reflection"
    state["should_continue"] = False

    return state


def _generate_large_model_suggestion(
    user_input: str,
    rag_context: list,
    ml_features: dict,
    risk_level,
    long_term_profile: dict,
    short_term_memory: list
) -> str:
    """生成大模型个性化建议（复杂场景）"""
    from app.agent.prompts import UNIFIED_SUGGESTION_PROMPT
    from app.agent.tools import llm_call

    context_text = "\n".join([
        f"- {item.get('content', '')}" for item in rag_context[:3] if isinstance(item, dict)
    ]) if rag_context else "无可用健康知识参考"

    conversation_history = "\n".join([
        f"{m.get('role', 'user')}: {m.get('content', '')}"
        for m in short_term_memory[-6:]
        if isinstance(m, dict) and m.get('type') != 'sensor_data'
    ]) if short_term_memory else ""

    has_sensor_data = bool(ml_features and ml_features.get("emotion") != "unknown")

    prompt = UNIFIED_SUGGESTION_PROMPT.format(
        user_input=user_input or "请提供一般性健康建议",
        conversation_history=conversation_history or "暂无对话历史",
        user_profile=str(long_term_profile) if long_term_profile else "暂无用户画像",
        ml_analysis=str(ml_features) if has_sensor_data else "无传感器数据",
        risk_level=risk_level.value if isinstance(risk_level, RiskLevel) else str(risk_level),
        rag_context=context_text,
        scenario="health_monitoring" if has_sensor_data else "chat_consultation"
    )

    try:
        suggestion = llm_call(prompt)
        if suggestion is None:
            suggestion = "抱歉，暂时无法生成建议，请稍后重试。"
    except Exception as e:
        print(f"[大模型调用错误] LLM调用失败: {str(e)}")
        suggestion = f"抱歉，生成建议时出现错误：{str(e)}"

    return suggestion


def interaction_reflection_node(state: HealthState) -> HealthState:
    """交互与反思节点：处理用户反馈 + 智能对话存储 + 定期记忆提取

    功能：
    1. 将用户输入存储到对话历史
    2. 存储AI响应到对话历史
    3. 定期调用记忆提取工具，更新用户画像
    4. 可选：生成引导性问题鼓励用户继续对话

    对话存储使用三维筛选机制：
    - 持久性价值
    - 结构化程度
    - 个性化价值
    """
    from app.database.conversation_store import ConversationStore
    from app.database.feature_store import FeatureStore
    from app.agent.memory_extraction_tool import memory_extraction_tool
    from datetime import datetime, timedelta

    suggestion = state.get("suggestion", "")
    user_input = state.get("user_input", "")
    user_id = state.get("user_id", "default_user")
    session_id = state.get("session_id", "")

    if not user_input:
        state["next_node"] = END
        return state

    conv_store = ConversationStore()
    profile_store = FeatureStore()

    ml_features = state.get('ml_features') or {}
    context = {
        'emotion_state': ml_features.get('emotion'),
        'stress_level': ml_features.get('stress_index'),
        'risk_level': state.get('risk_level'),
        'model_used': state.get('model_used', 'unknown')
    }

    conv_store.save_conversation(
        user_id=user_id,
        role='user',
        content=user_input,
        session_id=session_id,
        context=context
    )

    conv_store.save_conversation(
        user_id=user_id,
        role='assistant',
        content=suggestion,
        session_id=session_id,
        context=context
    )

    should_extract_memory = False
    profile = profile_store.get_user_profile(user_id) or {}

    last_extraction = profile.get("last_memory_extraction")
    if last_extraction:
        try:
            last_date = datetime.fromisoformat(last_extraction.replace('Z', '+00:00'))
            days_since = (datetime.now() - last_date).days
            conversation_count = len(conv_store.get_recent_conversations(user_id=user_id, limit=100))
            should_extract_memory = memory_extraction_tool.should_extract(conversation_count, days_since)
        except:
            should_extract_memory = True
    else:
        should_extract_memory = True

    if should_extract_memory:
        print(f"[记忆提取] 开始提取用户 {user_id} 的记忆...")
        recent_convs = conv_store.get_recent_conversations(user_id=user_id, limit=50)

        use_large = state.get("model_used") == "large"
        extraction_result = memory_extraction_tool.extract_from_conversations(
            conversation_history=recent_convs,
            current_profile=profile,
            use_large_model=use_large
        )

        if extraction_result and extraction_result.get("summary") != "暂无有效信息":
            memory_extraction_tool.update_user_profile(user_id, extraction_result)
            print(f"[记忆提取] 完成：{extraction_result.get('summary', '')[:50]}")
        else:
            print(f"[记忆提取] 无需提取")

    state["reflection_result"] = suggestion
    state["query_complexity"] = state.get("query_complexity", "unknown")
    state["model_used"] = state.get("model_used", "unknown")
    state["route_reason"] = state.get("route_reason", "")
    state["next_node"] = END
    return state


def emergency_response_node(state: HealthState) -> HealthState:
    """紧急响应节点：触发设备联动"""
    device_command = state.get("device_command")
    if device_command:
        from app.services.notification_service import NotificationService
        notifier = NotificationService()
        notifier.send_device_command(device_command)

    state["next_node"] = END
    return state
