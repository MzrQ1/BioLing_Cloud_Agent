"""测试Agent流程"""
import pytest
from app.agent.graph import create_health_agent_graph, create_data_pipeline_graph
from app.agent.state import HealthState, RiskLevel, InterventionType

class TestHealthAgentGraph:
    def setup_method(self):
        self.graph = create_health_agent_graph()
        self.pipeline_graph = create_data_pipeline_graph()

    def test_graph_creation(self):
        assert self.graph is not None
        assert self.pipeline_graph is not None

    def test_initial_state(self):
        state = HealthState(
            user_id="test_user",
            session_id="test_session",
            raw_sensor_data={
                "hr": 75,
                "hrv": 40,
                "sc": 0.5,
                "temp": 36.5,
                "spo2": 98
            },
            processed_features={
                "heart_rate": 75,
                "heart_rate_variability": 40,
                "skin_conductance": 0.5,
                "temperature": 36.5,
                "blood_oxygen": 98
            },
            short_term_memory=[],
            ml_features=None,
            risk_level=RiskLevel.LOW,
            intervention_type=InterventionType.NONE,
            next_node="short_term_memory",
            should_continue=False
        )

        assert state["user_id"] == "test_user"
        assert state["risk_level"] == RiskLevel.LOW

    def test_state_transitions(self):
        state = HealthState(
            user_id="test_user",
            session_id="test_session",
            raw_sensor_data={"hr": 85, "hrv": 30, "sc": 0.8},
            processed_features={"heart_rate": 85, "hrv_sdnn": 30},
            short_term_memory=[],
            ml_features=None,
            risk_level=RiskLevel.MODERATE,
            intervention_type=InterventionType.NONE,
            next_node="short_term_memory",
            should_continue=False
        )

        assert state["next_node"] == "short_term_memory"

    def test_risk_levels(self):
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.CRITICAL.value == "critical"

    def test_intervention_types(self):
        assert InterventionType.NONE.value == "none"
        assert InterventionType.IMMEDIATE.value == "immediate"
        assert InterventionType.LONG_TERM.value == "long_term"
