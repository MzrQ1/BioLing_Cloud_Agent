"""状态定义 - LangGraph健康智能体"""
from typing import TypedDict, Annotated, Optional
from datetime import datetime
from enum import Enum

class RiskLevel(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"

class InterventionType(str, Enum):
    NONE = "none"
    IMMEDIATE = "immediate"
    LONG_TERM = "long_term"

class HealthState(TypedDict):
    user_id: str
    session_id: str
    user_input: Optional[str]

    raw_sensor_data: Optional[dict]
    processed_features: Optional[dict]

    short_term_memory: list[dict]
    long_term_profile: Optional[dict]

    ml_features: Optional[dict]
    risk_level: RiskLevel

    rag_context: Optional[list[dict]]
    suggestion: Optional[str]

    intervention_type: InterventionType
    device_command: Optional[dict]

    next_node: str
    should_continue: bool

    reflection_result: Optional[str]

    query_complexity: Optional[str]
    model_used: Optional[str]
    route_reason: Optional[str]
