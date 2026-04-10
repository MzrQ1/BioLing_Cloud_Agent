# BioLing Cloud Agent

端云协同健康智能体 - 基于 LangGraph 构建的智能健康管家系统。

## 核心架构

```
┌─────────────┐     MQTT/HTTPS      ┌──────────────┐     设备指令     ┌─────────────┐
│  ESP32-S3   │ ──────────────────> │  云端智能体   │ ───────────────> │ 智能眼罩    │
│  (端侧)     │ <────────────────── │  (LangGraph) │                  │ (反馈调节)  │
└─────────────┘     状态反馈         └──────────────┘                  └─────────────┘
                                              │
                                              ▼
                                       ┌──────────────┐
                                       │   Web前端    │
                                       │ (用户交互)   │
                                       └──────────────┘
```

## 双轨工作流架构

### 快速路径（简单问答）
```
用户输入 → quick_check → simple_response → interaction_reflection → END
```
- 🤖 使用 Ollama 本地小模型（qwen2.5:latest）
- ⚡ 快速响应（目标 < 2秒）
- 📚 加载 10 轮对话历史
- 🧠 利用提取的用户记忆增强上下文
- ❌ 不走 RAG 知识库

### 完整路径（复杂分析）
```
用户输入 → quick_check → memory_retrieval → rag_knowledge_base →
suggestion_generation → interaction_reflection → END
```
- 🧠 使用 DashScope 大模型（qwen-plus）
- 📖 检索 RAG 知识库
- 💾 定期记忆提取到用户画像
- 🔄 支持流式输出

### 路由决策规则

| 问题类型 | 示例 | 路径 | 模型 |
|---------|------|------|------|
| 问候/寒暄 | "你好" | 快速路径 | 🤖 小模型 |
| 简单知识问答 | "血压正常范围？" | 快速路径 | 🤖 小模型 |
| 涉及个人数据 | "我最近压力大..." | 完整路径 | 🧠 大模型 |
| 需要深度分析 | "根据我的数据..." | 完整路径 | 🧠 大模型 |

---

## 快速启动

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置环境变量
```bash
cp .env.local .env
```

编辑 `.env`：
```bash
# 大模型配置
LLM_PROVIDER=dashscope
LLM_DIALOG_MODEL=qwen-plus
DASHSCOPE_API_KEY=your-api-key

# 小模型配置（Ollama）
OLLAMA_LLM_MODEL=qwen2.5:latest
EMBEDDING_API_BASE=http://localhost:11434
```

### 3. 启动服务
```bash
# 启动 Ollama（小模型服务）
ollama serve

# 启动应用
cd app
uvicorn main:app --reload --host 0.0.0.0 --port 8001
```

### 4. 验证
- Web前端：http://localhost:8001/
- API文档：http://localhost:8001/docs

---

## 代码结构

```
app/
├── agent/
│   ├── graph.py              # StateGraph 定义（双轨架构）
│   ├── state.py              # 状态定义
│   ├── nodes.py              # 节点逻辑
│   ├── tools.py              # LLM/Embedding 调用
│   ├── model_router.py      # 模型路由决策
│   ├── memory_extraction_tool.py  # 记忆提取工具
│   └── prompts.py            # System Prompts
│
├── database/
│   ├── conversation_store.py  # 对话存储（三维筛选）
│   ├── feature_store.py      # 用户画像
│   ├── vector_store.py       # 向量库 (RAG)
│   └── ibi_buffer.py         # IBI缓冲区
│
└── interfaces/
    ├── api_routes.py         # HTTP API
    ├── auth.py                # 用户认证
    └── mqtt_listener.py       # MQTT 监听

static/
└── index.html                # Web 前端（SPA）

scripts/
├── import_knowledge.py       # RAG 知识库导入
└── memory_reflection.py       # 记忆反思
```

---

## API 接口

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/v1/web/chat/stream` | 流式对话（推荐） |
| GET | `/api/v1/web/chat/history` | 对话历史 |
| GET | `/api/v1/web/report/{user_id}` | 健康报告 |
| POST | `/api/v1/sensor/esp32` | ESP32 传感器数据 |

---

## 记忆系统

### 三维筛选评分
```
memory_score = 0.4 × persistence + 0.3 × structure + 0.3 × personalization
```

### 记忆提取
- **触发条件**：对话 ≥10轮 或 距上次提取 ≥1天
- **提取内容**：健康状况、生活习惯、偏好、重要事件
- **存储位置**：用户画像的 `extracted_memories` 字段

### 清理规则
- 评分 < 0.3 且超过 3 天 → 删除
- 评分 < 0.4 且超过 7 天 → 删除
- 评分 < 0.5 且超过 14 天 → 删除

---

## RAG 配置

```bash
# 混合检索
RAG_ENABLE_HYBRID_SEARCH=true
RAG_HYBRID_ALPHA=0.5

# 添加知识库
python scripts/import_knowledge.py --import
python scripts/import_knowledge.py --test "如何缓解压力"
```

---

## 更新日志

### v0.10.0 (2026-04-10)
- 新增双轨工作流架构（快速路径 + 完整路径）
- 新增模型路由器 `model_router.py`
- 新增记忆提取工具 `memory_extraction_tool.py`
- 新增流式输出支持 `/api/v1/web/chat/stream`
- 大模型：DashScope qwen-plus
- 小模型：Ollama qwen2.5:latest
- 前端流式输出逐字显示

### v0.9.0 (2026-04-09)
- 新增 Web 前端界面 `static/index.html`
- 新增用户认证模块

### v0.8.0 (2026-04-09)
- 新增 IBI 缓冲区模块

---

## MIT License
