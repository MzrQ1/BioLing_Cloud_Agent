import sys
import os
import io
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app.agent.graph import create_chat_graph
from app.agent.state import HealthState

graph = create_chat_graph()

state = HealthState(
    user_id='test_user',
    session_id='test_session',
    raw_sensor_data=None,
    processed_features=None,
    short_term_memory=[],
    ml_features=None,
    risk_level='low',
    intervention_type='none',
    next_node='rag_knowledge_base',
    should_continue=False,
    user_input='你好，我想咨询健康问题'
)

print('开始测试工作流（ML特征为None）...')
try:
    result = graph.invoke(state)
    print('✓ 工作流执行成功！')
    print(f'  - reflection_result: {(result.get("reflection_result") or "无")[:80]}')
    print(f'  - suggestion: {(result.get("suggestion") or "无")[:80]}')
    print(f'  - ml_features: {result.get("ml_features")}')
    print(f'  - risk_level: {result.get("risk_level")}')
    print('\n✓ 测试通过：ML节点为None时不会报错！')
except Exception as e:
    print(f'✗ 错误: {str(e)}')
    import traceback
    traceback.print_exc()
