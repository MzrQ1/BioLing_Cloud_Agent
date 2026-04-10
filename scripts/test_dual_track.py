"""测试双轨工作流 - 验证快速路径是否生效"""
import sys
import os
import io
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import time

from app.agent.graph import create_chat_graph
from app.agent.state import HealthState

print("=" * 70)
print("双轨工作流测试 - 验证快速路径 vs 完整路径")
print("=" * 70)

graph = create_chat_graph()

test_cases = [
    ("你好", "简单问候", "small", "应该走快速路径"),
    ("今天天气怎么样？", "日常闲聊", "small", "应该走快速路径"),
    ("血压正常范围是多少？", "简单知识问答", "small", "应该走快速路径"),
    ("我最近压力大怎么办？", "复杂咨询", "large", "应该走完整路径"),
    ("根据我的数据分析一下我的状况", "复杂分析", "large", "应该走完整路径"),
]

print("\n【测试用例】")
print("-" * 70)
for query, desc, expected_route, note in test_cases:
    print(f"  [{desc}] {query} → 期望: {expected_route} ({note})")

print("\n" + "=" * 70)
print("【执行测试】")
print("=" * 70)

results = []

for query, desc, expected_route, note in test_cases:
    print(f"\n{'─' * 70}")
    print(f"测试: {desc}")
    print(f"输入: {query}")
    print(f"期望: {expected_route} ({note})")
    print("-" * 70)

    state = HealthState(
        user_id='test_user',
        session_id=f'test_{desc}',
        raw_sensor_data=None,
        processed_features=None,
        short_term_memory=[],
        ml_features=None,
        risk_level='low',
        intervention_type='none',
        next_node='quick_check',
        should_continue=False,
        user_input=query
    )

    start = time.time()
    try:
        result = graph.invoke(state)
        elapsed = time.time() - start

        actual_route = result.get("query_complexity", "unknown")
        model_used = result.get("model_used", "unknown")
        response = result.get("suggestion") or result.get("reflection_result") or ""
        route_reason = result.get("route_reason", "")

        emoji = "✅" if actual_route == expected_route else "❌"
        speed_emoji = "⚡" if actual_route == "small" else "🐢"

        print(f"{emoji} 路由结果: {actual_route} | 原因: {route_reason}")
        print(f"{speed_emoji} 使用模型: {model_used} | 耗时: {elapsed:.2f}秒")
        print(f"回复: {response[:100]}..." if len(response) > 100 else f"回复: {response}")

        results.append({
            "desc": desc,
            "query": query,
            "expected": expected_route,
            "actual": actual_route,
            "elapsed": elapsed,
            "success": actual_route == expected_route
        })

    except Exception as e:
        elapsed = time.time() - start
        print(f"❌ 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        results.append({
            "desc": desc,
            "query": query,
            "expected": expected_route,
            "actual": "ERROR",
            "elapsed": elapsed,
            "success": False
        })

print("\n" + "=" * 70)
print("【测试结果汇总】")
print("=" * 70)

small_queries = [r for r in results if r["expected"] == "small"]
large_queries = [r for r in results if r["expected"] == "large"]

if small_queries:
    avg_small = sum(r["elapsed"] for r in small_queries) / len(small_queries)
    small_success = sum(1 for r in small_queries if r["success"])
    print(f"\n快速路径 (small) 平均耗时: {avg_small:.2f}秒 | 成功率: {small_success}/{len(small_queries)}")

if large_queries:
    avg_large = sum(r["elapsed"] for r in large_queries) / len(large_queries)
    large_success = sum(1 for r in large_queries if r["success"])
    print(f"\n完整路径 (large) 平均耗时: {avg_large:.2f}秒 | 成功率: {large_success}/{len(large_queries)}")

print("\n【详细结果】")
print("-" * 70)
for r in results:
    status = "✅" if r["success"] else "❌"
    print(f"{status} [{r['desc']}] {r['query'][:20]}... -> 期望:{r['expected']} 实际:{r['actual']} ({r['elapsed']:.2f}秒)")

total_success = sum(1 for r in results if r["success"])
print(f"\n总计: {total_success}/{len(results)} 测试通过")

if total_success == len(results):
    print("\n🎉 所有测试通过！")
else:
    print("\n⚠️ 部分测试失败，请检查路由逻辑")

print("=" * 70)
