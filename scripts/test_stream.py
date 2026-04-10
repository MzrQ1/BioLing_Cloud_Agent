"""测试流式输出"""
import sys
import os
import io
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app.agent.tools import llm_call_stream, llm_call_simple_stream

print("=" * 60)
print("流式输出测试")
print("=" * 60)

print("\n【测试 DashScope 大模型流式输出】")
print("-" * 60)

print("输入: 你好，请用简单的语言介绍一下自己")
print("输出: ", end="", flush=True)

full_response = ""
for i, chunk in enumerate(llm_call_stream("你好，请用简单的语言介绍一下自己")):
    full_response += chunk
    print(chunk, end="", flush=True)

print(f"\n\n✅ 大模型流式输出完成！共 {len(full_response)} 字符")

print("\n" + "=" * 60)
print("\n【测试 Ollama 小模型流式输出】")
print("-" * 60)

print("输入: 你好，请用简单的语言介绍一下自己")
print("输出: ", end="", flush=True)

full_response = ""
for i, chunk in enumerate(llm_call_simple_stream("你好，请用简单的语言介绍一下自己")):
    full_response += chunk
    print(chunk, end="", flush=True)

print(f"\n\n✅ 小模型流式输出完成！共 {len(full_response)} 字符")

print("\n" + "=" * 60)
print("测试完成！")
print("=" * 60)
