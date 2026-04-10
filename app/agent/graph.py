"""StateGraph定义 - LangGraph健康智能体"""
from langgraph.graph import StateGraph, END
from .state import HealthState, InterventionType
from .nodes import (
    quick_check_node,
    simple_response_node,
    memory_retrieval_node,
    sensor_processing_node,
    rag_knowledge_base_node,
    suggestion_generation_node,
    interaction_reflection_node,
    emergency_response_node
)


def create_unified_health_agent_graph():
    """创建统一的健康智能体工作流（兼容有/无传感器数据场景）

    双轨架构：
    - 快速路径（simple）：quick_check → simple_response → interaction_reflection → END
      特点：不经 RAG、不做 ML 情绪识别、使用小模型、快速响应

    - 完整路径（complex）：quick_check → memory_retrieval → [sensor_processing] → rag_knowledge_base → suggestion_generation → interaction_reflection → END
      特点：加载完整上下文、RAG 知识库检索、ML 情绪识别、使用大模型

    快速判断依据：
    1. 简单问候/寒暄 → 快速路径
    2. 通用健康知识问答 → 快速路径
    3. 涉及个人数据/ML特征/建议需求 → 完整路径
    """
    workflow = StateGraph(HealthState)

    workflow.add_node("quick_check", quick_check_node)
    workflow.add_node("simple_response", simple_response_node)
    workflow.add_node("memory_retrieval", memory_retrieval_node)
    workflow.add_node("sensor_processing", sensor_processing_node)
    workflow.add_node("rag_knowledge_base", rag_knowledge_base_node)
    workflow.add_node("suggestion_generation", suggestion_generation_node)
    workflow.add_node("interaction_reflection", interaction_reflection_node)
    workflow.add_node("emergency_response", emergency_response_node)

    def route_after_quick_check(state: HealthState) -> str:
        """路由决策：根据问题复杂度选择路径"""
        query_complexity = state.get("query_complexity", "large")
        if query_complexity == "small":
            return "simple_response"
        return "memory_retrieval"

    def route_after_memory(state: HealthState) -> str:
        """路由决策：是否有传感器数据需要处理"""
        raw_data = state.get("raw_sensor_data")
        if raw_data:
            return "sensor_processing"
        return "rag_knowledge_base"

    def route_after_sensor(state: HealthState) -> str:
        """路由决策：是否需要紧急响应"""
        intervention_type = state.get("intervention_type")
        if intervention_type == InterventionType.IMMEDIATE:
            return "emergency_response"
        return "rag_knowledge_base"

    def route_after_reflection(state: HealthState) -> str:
        """路由决策：是否继续对话循环"""
        next_node = state.get("next_node", END)
        if next_node == "suggestion_generation":
            return "suggestion_generation"
        return END

    workflow.set_entry_point("quick_check")

    workflow.add_conditional_edges(
        "quick_check",
        route_after_quick_check,
        {
            "simple_response": "simple_response",
            "memory_retrieval": "memory_retrieval"
        }
    )

    workflow.add_edge("simple_response", "interaction_reflection")

    workflow.add_conditional_edges(
        "memory_retrieval",
        route_after_memory,
        {
            "sensor_processing": "sensor_processing",
            "rag_knowledge_base": "rag_knowledge_base"
        }
    )

    workflow.add_conditional_edges(
        "sensor_processing",
        route_after_sensor,
        {
            "emergency_response": "emergency_response",
            "rag_knowledge_base": "rag_knowledge_base"
        }
    )

    workflow.add_edge("emergency_response", END)
    workflow.add_edge("rag_knowledge_base", "suggestion_generation")

    workflow.add_conditional_edges(
        "suggestion_generation",
        lambda state: "interaction_reflection",
        {"interaction_reflection": "interaction_reflection"}
    )

    workflow.add_conditional_edges(
        "interaction_reflection",
        route_after_reflection,
        {
            "suggestion_generation": "suggestion_generation",
            END: END
        }
    )

    return workflow.compile()


def create_chat_graph():
    """创建纯对话工作流（轻量版，用于无传感器数据的对话场景）

    与 unified_health_agent_graph 的区别：
    - 不包含 sensor_processing 和 emergency_response 节点
    - 专用于纯聊天场景（无传感器数据）

    双轨架构：
    - 快速路径（simple）：quick_check → simple_response → interaction_reflection → END
    - 完整路径（complex）：quick_check → memory_retrieval → rag_knowledge_base → suggestion_generation → interaction_reflection → END
    """
    workflow = StateGraph(HealthState)

    workflow.add_node("quick_check", quick_check_node)
    workflow.add_node("simple_response", simple_response_node)
    workflow.add_node("memory_retrieval", memory_retrieval_node)
    workflow.add_node("rag_knowledge_base", rag_knowledge_base_node)
    workflow.add_node("suggestion_generation", suggestion_generation_node)
    workflow.add_node("interaction_reflection", interaction_reflection_node)

    def route_after_quick_check(state: HealthState) -> str:
        """路由决策：根据问题复杂度选择路径"""
        query_complexity = state.get("query_complexity", "large")
        if query_complexity == "small":
            return "simple_response"
        return "memory_retrieval"

    def route_after_reflection(state: HealthState) -> str:
        """路由决策：是否继续对话循环"""
        next_node = state.get("next_node", END)
        if next_node == "suggestion_generation":
            return "suggestion_generation"
        return END

    workflow.set_entry_point("quick_check")

    workflow.add_conditional_edges(
        "quick_check",
        route_after_quick_check,
        {
            "simple_response": "simple_response",
            "memory_retrieval": "memory_retrieval"
        }
    )

    workflow.add_edge("simple_response", "interaction_reflection")

    workflow.add_edge("memory_retrieval", "rag_knowledge_base")
    workflow.add_edge("rag_knowledge_base", "suggestion_generation")
    workflow.add_edge("suggestion_generation", "interaction_reflection")

    workflow.add_conditional_edges(
        "interaction_reflection",
        route_after_reflection,
        {
            "suggestion_generation": "suggestion_generation",
            END: END
        }
    )

    return workflow.compile()
