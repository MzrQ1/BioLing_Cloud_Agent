"""StateGraph定义 - LangGraph健康智能体"""
from langgraph.graph import StateGraph, END
from .state import HealthState
from .nodes import (
    short_term_memory_node,
    long_term_memory_node,
    ml_emotion_recognition_node,
    anomaly_detection_node,
    rag_knowledge_base_node,
    suggestion_generation_node,
    report_generation_node,
    interaction_reflection_node,
    data_retrieval_node,
    emergency_response_node
)

def create_health_agent_graph():
    """创建健康智能体StateGraph"""
    workflow = StateGraph(HealthState)

    workflow.add_node("data_retrieval", data_retrieval_node)
    workflow.add_node("short_term_memory", short_term_memory_node)
    workflow.add_node("long_term_memory", long_term_memory_node)
    workflow.add_node("ml_emotion_recognition", ml_emotion_recognition_node)
    workflow.add_node("anomaly_detection", anomaly_detection_node)
    workflow.add_node("emergency_response", emergency_response_node)
    workflow.add_node("rag_knowledge_base", rag_knowledge_base_node)
    workflow.add_node("suggestion_generation", suggestion_generation_node)
    workflow.add_node("report_generation", report_generation_node)
    workflow.add_node("interaction_reflection", interaction_reflection_node)

    def should_continue(state: HealthState) -> str:
        if state.get("should_continue") and state.get("intervention_type") == "immediate":
            return "emergency_response"
        if state.get("next_node") == "END":
            return END
        return state.get("next_node", END)

    workflow.set_entry_point("short_term_memory")

    workflow.add_edge("short_term_memory", "long_term_memory")
    workflow.add_edge("long_term_memory", "ml_emotion_recognition")
    workflow.add_edge("ml_emotion_recognition", "anomaly_detection")

    workflow.add_conditional_edges(
        "anomaly_detection",
        should_continue,
        {
            "emergency_response": "emergency_response",
            "rag_knowledge_base": "rag_knowledge_base",
            END: END
        }
    )

    workflow.add_edge("emergency_response", END)
    workflow.add_edge("rag_knowledge_base", "suggestion_generation")
    workflow.add_edge("suggestion_generation", "report_generation")
    workflow.add_edge("report_generation", "interaction_reflection")

    workflow.add_conditional_edges(
        "interaction_reflection",
        lambda state: state.get("next_node", END),
        {
            "suggestion_generation": "suggestion_generation",
            END: END
        }
    )

    return workflow.compile()

def create_data_pipeline_graph():
    """创建数据处理流水线（轻量版，用于快速处理传感器数据）"""
    workflow = StateGraph(HealthState)

    workflow.add_node("short_term_memory", short_term_memory_node)
    workflow.add_node("long_term_memory", long_term_memory_node)
    workflow.add_node("ml_emotion_recognition", ml_emotion_recognition_node)
    workflow.add_node("anomaly_detection", anomaly_detection_node)
    workflow.add_node("suggestion_generation", suggestion_generation_node)

    def route_after_anomaly(state: HealthState) -> str:
        if state.get("intervention_type") == "immediate":
            return "suggestion_generation"
        return "suggestion_generation"

    workflow.set_entry_point("short_term_memory")
    workflow.add_edge("short_term_memory", "long_term_memory")
    workflow.add_edge("long_term_memory", "ml_emotion_recognition")
    workflow.add_edge("ml_emotion_recognition", "anomaly_detection")
    workflow.add_edge("anomaly_detection", "suggestion_generation")

    return workflow.compile()
