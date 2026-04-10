# BioLing Cloud Agent — Claude Code 项目指南

## 项目概述

端云协同健康智能体，基于 LangGraph 构建。ESP32-S3 采集生理数据 → 云端 Agent 分析 → 智能眼罩干预 + 对话健康报告。

**关键路径**：
- Agent 核心：[app/agent/](app/agent/) — `graph.py`(StateGraph) → `nodes.py`(节点逻辑) → `tools.py`(LLM调用) → `prompts.py`(提示词)
- 数据库层：[app/database/](app/database/) — SQLite(持久化) + ChromaDB(向量库) + 内存(Checkpoint)
- 记忆系统：[app/database/conversation_store.py](app/database/conversation_store.py) — 三维筛选 + 动态反思
- ML 服务：[app/ml_services/](app/ml_services/) — HRV 特征提取 + 情绪推理
- 接口层：[app/interfaces/](app/interfaces/) — FastAPI 路由 + MQTT 监听

## 协作规范

### 代码修改审查清单
每次对话结束前，如果涉及代码修改，自动检查：
1. 新增 import 是否必要，有无循环依赖
2. 数据库操作是否使用 `get_db_context()` 上下文管理器
3. 异常处理是否覆盖了失败路径（尤其是 LLM 调用、DB 查询、网络请求）
4. 节点返回值是否设置了 `state["next_node"]`（LangGraph 路由依赖此字段）
5. Prompt 中的 `{placeholder}` 与 `format()` 参数是否一一对应

### 记忆管理审查
当讨论记忆系统时，关注以下文件：
- **三维筛选**：[conversation_store.py](app/database/conversation_store.py) — `MemoryScorer` 类（持久性/结构化/个性化）
- **动态反思**：[memory_reflection.py](scripts/memory_reflection.py) — 定期清理 + 摘要生成
- **评分公式**：`score = 0.4*persistence + 0.3*structure + 0.3*personalization`
- **清理规则**：score<0.3 且>3天 / score<0.4 且>7天 / score<0.5 且>14天 → 删除

### LangGraph 工作流
```
short_term_memory → long_term_memory → ml_emotion_recognition → anomaly_detection
                                                                    │
                               ┌─────────────────────┬──────────────┘
                               ▼                     ▼
                        emergency_response    rag_knowledge_base
                               │                     │
                               ▼                     ▼
                              END              suggestion_generation
                                                    │
                                                    ▼
                                             report_generation → interaction_reflection
```

### 常用命令
```bash
# 启动开发服务
cd app && uvicorn main:app --reload --host 0.0.0.0 --port 8001

# 记忆反思
python scripts/memory_reflection.py
python scripts/memory_reflection.py --stats <user_id>

# 知识库导入
python scripts/import_knowledge.py --import
python scripts/import_knowledge.py --test "查询内容"
python scripts/import_knowledge.py --stats
```

### 技术栈
- **框架**：LangGraph + FastAPI + SQLAlchemy
- **LLM**：DashScope(千问) / OpenAI / Anthropic / Ollama
- **Embedding**：Ollama (nomic-embed-text)
- **向量库**：ChromaDB + BM25 混合检索 + Cross-Encoder Rerank
- **持久化**：SQLite + 内存 Checkpoint
- **通信**：MQTT (设备) + HTTP/REST (前端)
