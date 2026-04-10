"""测试对话功能"""
import sys
import os
import io
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 设置标准输出编码为 UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app.agent.tools import llm_call
from app.config import LLMConfig

print("=" * 60)
print("对话模型配置测试")
print("=" * 60)
print(f"Provider: {LLMConfig.PROVIDER}")
print(f"Model: {LLMConfig.DIALOG_MODEL}")
print(f"API Base: {LLMConfig.DIALOG_API_BASE}")
print(f"API Key: {LLMConfig.DIALOG_API_KEY[:10]}...{LLMConfig.DIALOG_API_KEY[-10:]}")
print(f"Temperature: {LLMConfig.TEMPERATURE}")
print(f"Max Tokens: {LLMConfig.MAX_TOKENS}")
print("=" * 60)

print("\n测试1：简单对话")
print("-" * 60)
response = llm_call("你好，请介绍一下你自己。")
print(f"回复: {response}")

print("\n测试2：健康咨询")
print("-" * 60)
response = llm_call("如何缓解压力？")
print(f"回复: {response}")

print("\n" + "=" * 60)
print("测试完成！")
print("=" * 60)
