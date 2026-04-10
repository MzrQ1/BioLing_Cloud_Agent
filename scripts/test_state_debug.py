"""测试 - 追踪 state 传递问题"""
import sys
import os
import io
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app.agent.graph import create_chat_graph
from app.agent.state import HealthState

print("=" * 60)
print("State 传递追踪测试")
print("=" * 60)

graph = create_chat_graph()

state = HealthState(
    user_id='debug_test',
    session_id='debug_session',
    raw_sensor_data=None,
    processed_features=None,
    short_term_memory=[],
    ml_features=None,
    risk_level='low',
    intervention_type='none',
    next_node='quick_check',
    should_continue=False,
    user_input='你好'
)

print(f"\n初始 state:")
print(f"  query_complexity: {state.get('query_complexity')}")
print(f"  next_node: {state.get('next_node')}")

print(f"\n执行 graph.invoke()...")

result = graph.invoke(state)

print(f"\n最终 result:")
print(f"  query_complexity: {result.get('query_complexity')}")
print(f"  model_used: {result.get('model_used')}")
print(f"  route_reason: {result.get('route_reason')}")
print(f"  suggestion: {result.get('suggestion', '')[:50]}...")

print("\n" + "=" * 60)
