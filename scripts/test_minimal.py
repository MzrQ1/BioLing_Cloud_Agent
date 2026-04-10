"""测试 - 最小化测试"""
import sys
import os
import io
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app.agent.graph import create_chat_graph
from app.agent.state import HealthState

print("=" * 60)
print("最小化测试")
print("=" * 60)

graph = create_chat_graph()

state = HealthState(
    user_id='brand_new_user_xyz',
    session_id='brand_new_session_xyz',
    raw_sensor_data=None,
    processed_features=None,
    short_term_memory=[],
    ml_features=None,
    risk_level='low',
    intervention_type='none',
    next_node='quick_check',
    should_continue=False,
    user_input='你好呀'
)

print(f"\n初始 state['query_complexity']: {state.get('query_complexity')}")

result = graph.invoke(state)

print(f"\n最终 result keys: {list(result.keys())}")
print(f"最终 result['query_complexity']: {result.get('query_complexity')}")
print(f"最终 result['model_used']: {result.get('model_used')}")
print(f"最终 result['route_reason']: {result.get('route_reason')}")

suggestion = result.get('suggestion') or result.get('reflection_result') or ''
print(f"最终 result['suggestion']: {suggestion[:80]}...")

print("\n" + "=" * 60)
