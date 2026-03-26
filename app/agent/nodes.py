"""节点逻辑 - LangGraph健康智能体节点"""
from .state import HealthState, RiskLevel, InterventionType
from datetime import datetime

def short_term_memory_node(state: HealthState) -> HealthState:
    """短记忆节点：存储最近N次交互记录"""
    raw_data = state.get("raw_sensor_data", {})
    if raw_data:
        memory_entry = {
            "timestamp": datetime.now().isoformat(),
            "data": raw_data,
            "processed_features": state.get("processed_features")
        }
        short_memory = state.get("short_term_memory", [])
        short_memory.append(memory_entry)
        if len(short_memory) > 10:
            short_memory = short_memory[-10:]
        state["short_term_memory"] = short_memory
    state["next_node"] = "long_term_memory"
    return state

def long_term_memory_node(state: HealthState) -> HealthState:
    """长记忆节点：用户画像更新"""
    from app.database.feature_store import FeatureStore

    user_id = state["user_id"]
    features = state.get("processed_features", {})

    store = FeatureStore()
    profile = store.get_user_profile(user_id) or {}

    if features:
        profile["last_update"] = datetime.now().isoformat()
        profile["recent_features"] = features
        avg_stress = features.get("stress_index", 0)
        profile["avg_stress"] = avg_stress
        store.update_user_profile(user_id, profile)

    state["long_term_profile"] = profile
    state["next_node"] = "ml_emotion_recognition"
    return state

def ml_emotion_recognition_node(state: HealthState) -> HealthState:
    """情绪识别ML节点：调用预训练模型进行情感分析"""
    from app.ml_services.inference_engine import InferenceEngine

    features = state.get("processed_features", {})
    if not features:
        state["ml_features"] = {"emotion": "unknown", "confidence": 0.0}
        state["risk_level"] = RiskLevel.LOW
        state["next_node"] = "anomaly_detection"
        return state

    engine = InferenceEngine()
    ml_result = engine.predict_emotion(features)

    state["ml_features"] = ml_result
    state["risk_level"] = ml_result.get("risk_level", RiskLevel.LOW)
    state["next_node"] = "anomaly_detection"
    return state

def anomaly_detection_node(state: HealthState) -> HealthState:
    """异常触发判断节点：判断是否需要即时干预"""
    risk_level = state.get("risk_level", RiskLevel.LOW)
    ml_features = state.get("ml_features", {})

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
    elif ml_features.get("stress_trend", 0) > 0.7:
        should_intervene = True
        intervention_type = InterventionType.LONG_TERM

    state["intervention_type"] = intervention_type
    state["device_command"] = device_command
    state["should_continue"] = should_intervene
    state["next_node"] = "rag_knowledge_base"
    return state

def rag_knowledge_base_node(state: HealthState) -> HealthState:
    """RAG知识库节点：检索相关健康知识"""
    from app.database.vector_store import VectorStore

    user_query = f"stress={state.get('ml_features', {}).get('stress_index', 0)}, "
    user_query += f"emotion={state.get('ml_features', {}).get('emotion', 'unknown')}, "
    user_query += f"risk_level={state.get('risk_level', 'unknown')}"

    vector_store = VectorStore()
    rag_results = vector_store.query(user_query, top_k=3)

    state["rag_context"] = rag_results
    state["next_node"] = "suggestion_generation"
    return state

def suggestion_generation_node(state: HealthState) -> HealthState:
    """建议生成节点：基于RAG上下文生成个性化建议"""
    from app.agent.prompts import SUGGESTION_PROMPT
    from app.agent.tools import llm_call

    rag_context = state.get("rag_context", [])
    ml_features = state.get("ml_features", {})
    risk_level = state.get("risk_level", RiskLevel.LOW)
    long_term_profile = state.get("long_term_profile", {})

    context_text = "\n".join([
        f"- {item.get('content', '')}" for item in rag_context[:3]
    ]) if rag_context else "无可用健康知识参考"

    prompt = SUGGESTION_PROMPT.format(
        risk_level=risk_level.value,
        ml_features=str(ml_features),
        long_term_profile=str(long_term_profile),
        rag_context=context_text
    )

    suggestion = llm_call(prompt)
    state["suggestion"] = suggestion
    state["next_node"] = "report_generation"
    return state

def report_generation_node(state: HealthState) -> HealthState:
    """报告生成节点：生成结构化健康报告"""
    from app.agent.prompts import REPORT_GENERATION_PROMPT
    from app.agent.tools import llm_call

    short_memory = state.get("short_term_memory", [])
    ml_features = state.get("ml_features", {})
    long_term_profile = state.get("long_term_profile", {})

    memory_summary = "\n".join([
        f"[{m.get('timestamp', '')}] stress={m.get('processed_features', {}).get('stress_index', 'N/A')}"
        for m in short_memory[-5:]
    ]) if short_memory else "暂无历史数据"

    prompt = REPORT_GENERATION_PROMPT.format(
        memory_summary=memory_summary,
        ml_features=str(ml_features),
        long_term_profile=str(long_term_profile)
    )

    report = llm_call(prompt)
    state["report_content"] = report
    state["next_node"] = "interaction_reflection"
    state["should_continue"] = False
    return state

def interaction_reflection_node(state: HealthState) -> HealthState:
    """交互与反思节点：ReAct模式处理用户反馈"""
    from app.agent.prompts import REFLECTION_PROMPT
    from app.agent.tools import llm_call

    report = state.get("report_content", "")
    suggestion = state.get("suggestion", "")
    user_input = state.get("user_input", "")

    if not user_input:
        state["next_node"] = "END"
        return state

    prompt = REFLECTION_PROMPT.format(
        report=report,
        suggestion=suggestion,
        user_input=user_input
    )

    reflection_result = llm_call(prompt)

    state["reflection_result"] = reflection_result
    state["next_node"] = "suggestion_generation"
    return state

def data_retrieval_node(state: HealthState) -> HealthState:
    """数据检索节点：从时序数据库获取历史数据"""
    from app.database.timeseries import TimeSeriesDB

    user_id = state["user_id"]
    time_range = state.get("time_range", "24h")

    ts_db = TimeSeriesDB()
    historical_data = ts_db.query(user_id, time_range)

    state["historical_data"] = historical_data
    state["next_node"] = "short_term_memory"
    return state

def emergency_response_node(state: HealthState) -> HealthState:
    """紧急响应节点：触发设备联动"""
    device_command = state.get("device_command")
    if device_command:
        from app.services.notification_service import NotificationService
        notifier = NotificationService()
        notifier.send_device_command(device_command)

    state["next_node"] = "END"
    return state
