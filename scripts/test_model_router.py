"""测试大小模型路由功能"""
import sys
import os
import io
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app.agent.model_router import should_use_large_model, classify_query_heuristic

print("=" * 60)
print("大小模型路由测试")
print("=" * 60)

test_cases = [
    ("你好", None, 0, "简单问候"),
    ("今天天气不错", None, 0, "日常闲聊"),
    ("请问血压正常范围是多少？", None, 0, "简单健康知识"),
    ("什么是心率变异性？", None, 0, "知识问答"),
    ("我最近睡不好怎么办？", None, 0, "一般咨询"),
    ("根据我的数据，我应该怎么调整？", {"emotion": "anxious", "stress_index": 75}, 0, "复杂分析"),
    ("我的HRV数据显示压力大，建议我做什么？", {"emotion": "stressed", "risk_level": "high"}, 0, "涉及ML数据"),
    ("最近工作压力大，睡眠质量差，心情也不好", None, 0, "需要建议"),
    ("帮我分析一下我的健康状况", {"emotion": "unknown"}, 0, "请求分析"),
    ("谢谢你的帮助！", None, 0, "结束语"),
]

print("\n【路由决策测试】")
print("-" * 60)

for user_input, ml_features, conv_turns, description in test_cases:
    model_type, reason = should_use_large_model(
        user_input=user_input,
        ml_features=ml_features,
        conversation_turns=conv_turns
    )

    emoji = "🤖" if model_type == "small" else "🧠"
    print(f"\n{emoji} [{description}]")
    print(f"   输入: {user_input}")
    if ml_features:
        print(f"   ML特征: emotion={ml_features.get('emotion')}, stress={ml_features.get('stress_index', 0)}")
    print(f"   → 模型: {model_type} | 原因: {reason}")

print("\n" + "=" * 60)
print("【测试 Ollama 小模型连接】")
print("=" * 60)

from app.agent.tools import llm_call_simple

test_prompt = "你好，请用一句话介绍自己。"

print(f"\n测试提示词: {test_prompt}")
print("正在调用 Ollama...")

result = llm_call_simple(test_prompt)

if result:
    print(f"✓ Ollama 调用成功！")
    print(f"  响应: {result[:100]}...")
else:
    print("✗ Ollama 调用失败或返回空")
    print("  请确保 Ollama 服务正在运行: ollama serve")

print("\n" + "=" * 60)
print("【完整工作流测试】")
print("=" * 60)

from app.agent.graph import create_chat_graph
from app.agent.state import HealthState

graph = create_chat_graph()

test_inputs = [
    ("你好", "简单问候"),
    ("我最近压力大怎么办？", "一般咨询"),
]

for user_input, description in test_inputs:
    print(f"\n测试: {description} | 输入: {user_input}")

    state = HealthState(
        user_id='test_user',
        session_id=f'test_session_{description}',
        raw_sensor_data=None,
        processed_features=None,
        short_term_memory=[],
        ml_features=None,
        risk_level='low',
        intervention_type='none',
        next_node='rag_knowledge_base',
        should_continue=False,
        user_input=user_input
    )

    try:
        result = graph.invoke(state)
        model_used = result.get("model_used", "unknown")
        suggestion = result.get("suggestion") or result.get("reflection_result") or ""

        emoji = "🤖" if model_used == "small" else "🧠"
        print(f"  {emoji} 使用模型: {model_used}")
        print(f"  回复: {suggestion[:80]}..." if len(suggestion) > 80 else f"  回复: {suggestion}")
        print(f"  ✓ 测试通过")
    except Exception as e:
        print(f"  ✗ 错误: {str(e)}")
        import traceback
        traceback.print_exc()

print("\n" + "=" * 60)
print("【响应速度对比测试】")
print("=" * 60)

import time

test_queries = [
    ("血压正常范围是多少？", "简单问答"),
    ("我最近压力大怎么办？", "复杂咨询"),
]

for query, qtype in test_queries:
    print(f"\n测试: {qtype} | 查询: {query}")

    state = HealthState(
        user_id='speed_test',
        session_id=f'speed_test_{qtype}',
        raw_sensor_data=None,
        processed_features=None,
        short_term_memory=[],
        ml_features=None,
        risk_level='low',
        intervention_type='none',
        next_node='rag_knowledge_base',
        should_continue=False,
        user_input=query
    )

    start = time.time()
    result = graph.invoke(state)
    elapsed = time.time() - start

    model_used = result.get("model_used", "unknown")
    emoji = "🤖" if model_used == "small" else "🧠"

    print(f"  {emoji} 模型: {model_used} | 耗时: {elapsed:.2f}秒")

print("\n" + "=" * 60)
print("测试完成！")
print("=" * 60)
