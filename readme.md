# BioLing Cloud Agent

端云协同健康智能体 - 基于 LangGraph 构建的智能健康管家系统。

## 核心定位

扮演健康管家角色，实现：
- **即时闭环**：急性压力时刻联动物理硬件（智能眼罩）提供沉浸式视听放松
- **长期闭环**：基于长周期数据生成健康报告，通过对话引导用户反思

## 系统架构

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

---

## 快速部署

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`：
```bash
# 对话模型 - 阿里云千问
LLM_PROVIDER=dashscope
LLM_DIALOG_MODEL=qwen2.5-7b-instruct
LLM_DIALOG_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_API_KEY=your-api-key

# Embedding - 本地Ollama
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=nomic-embed-text
EMBEDDING_API_BASE=http://localhost:11434
```

### 3. 启动Embedding服务（如需本地）

```bash
ollama serve
ollama pull nomic-embed-text
```

### 4. 启动服务

**开发模式：**
```bash
cd app
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Docker模式：**
```bash
docker-compose up -d
```

---

## ESP32 数据接入

### MQTT连接（推荐）

- Broker: `localhost:1883`
- Topic: `biolid/esp32/sensor_data`

### HTTP POST

```
POST http://localhost:8000/api/v1/sensor/esp32
```

数据格式：
```json
{
  "user_id": "user_001",
  "device_id": "esp32_001",
  "timestamp": "2024-01-01T12:00:00",
  "ibi": [812, 825, 818, 830, 815],
  "sdnn": 28.5
}
```

| 字段 | 描述 |
|------|------|
| ibi | 心跳间隔数组（毫秒） |
| sdnn | 心率变异性标准差（毫秒） |

---

## Web用户端

访问地址：`http://localhost:8000/docs`

| 接口 | 描述 |
|------|------|
| `POST /api/v1/web/login` | 用户登录 |
| `GET /api/v1/web/report/{user_id}` | 获取健康报告 |
| `POST /api/v1/web/chat` | 对话交互 |

---

## 代码结构

```
biolid-cloud-agent/
├── app/
│   ├── agent/                # 核心大脑 (LangGraph)
│   │   ├── graph.py         # StateGraph 定义
│   │   ├── state.py         # 状态定义
│   │   ├── nodes.py         # 节点逻辑
│   │   ├── tools.py         # LLM/Embedding 调用
│   │   └── prompts.py       # System Prompts
│   │
│   ├── ml_services/         # 机器学习
│   │   ├── feature_extractor.py  # HRV特征提取
│   │   ├── inference_engine.py   # 推理引擎
│   │   └── preprocessing.py      # 数据预处理
│   │
│   ├── database/              # 数据持久化
│   │   ├── vector_store.py    # 向量库 (RAG)
│   │   ├── feature_store.py    # 特征库
│   │   └── timeseries.py       # 时序库
│   │
│   └── interfaces/           # 外部接口
│       ├── api_routes.py     # HTTP API
│       └── mqtt_listener.py  # MQTT 监听
│
├── docs/                     # RAG知识库
├── tests/                    # 测试
└── data/                     # 数据存储
```

---

## API 接口

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/v1/sensor/esp32` | ESP32 发送传感器数据 |
| POST | `/api/v1/web/login` | 用户登录 |
| POST | `/api/v1/web/chat` | 用户对话交互 |
| GET | `/api/v1/web/report/{user_id}` | 获取健康报告 |
| GET | `/api/v1/health` | 健康检查 |

---

## ML 特征工程

### HRV 特征

- **时域特征**：mean_ibi, sdnn, rmssd, pnn50
- **频域特征**：lf_power, hf_power, lf_hf_ratio
- **非线性特征**：sample_entropy, correlation_dimension

### 压力评估

| 范围 | 风险等级 | 建议 |
|------|----------|------|
| 0-40 | LOW | 保持良好状态 |
| 40-60 | MODERATE | 适当关注压力管理 |
| 60-75 | HIGH | 建议采取放松措施 |
| 75-100 | CRITICAL | 立即干预，联动设备 |

---

## 节点自定义指南

### 节点列表

| 节点 | 功能 |
|------|------|
| `data_retrieval` | 数据检索 |
| `short_term_memory` | 短记忆：存储最近交互记录 |
| `long_term_memory` | 长记忆：用户画像更新 |
| `ml_emotion_recognition` | 情绪识别ML |
| `anomaly_detection` | 异常检测：判断是否干预 |
| `emergency_response` | 紧急响应：联动设备 |
| `rag_knowledge_base` | RAG知识库检索 |
| `suggestion_generation` | 建议生成 |
| `report_generation` | 报告生成 |
| `interaction_reflection` | 对话反思 |

### 工作流程

```
short_term_memory → long_term_memory → ml_emotion_recognition → anomaly_detection
                                                                    │
                                              ┌─────────────────────┼─────────────────────┐
                                              ▼                     ▼                     ▼
                                       emergency_response    rag_knowledge_base          END
                                              │                     │
                                              ▼                     ▼
                                       suggestion_generation ← ─ ─ ─ ┘
                                              │
                                              ▼
                                       report_generation → interaction_reflection → END
```

### 节点自定义

修改节点逻辑在 `app/agent/nodes.py`：

```python
def suggestion_generation_node(state: HealthState) -> HealthState:
    from app.agent.tools import llm_call
    from app.agent.prompts import SUGGESTION_PROMPT

    custom_prompt = SUGGESTION_PROMPT.format(
        risk_level=state.get("risk_level"),
        # ...
    )
    state["suggestion"] = llm_call(custom_prompt)
    return state
```

添加新节点在 `app/agent/graph.py`：

```python
workflow.add_node("new_node", new_node_func)
workflow.add_edge("source_node", "new_node")
```

---

## 大模型配置

| Provider | 对话模型 | Embedding | 说明 |
|----------|----------|-----------|------|
| `dashscope` | qwen2.5-7b-instruct | - | 阿里云千问（默认） |
| `openai` | GPT-4o, GPT-3.5 | text-embedding-3-small | OpenAI |
| `anthropic` | Claude-3.5 | - | Anthropic |
| `ollama` | llama3, qwen2 | nomic-embed-text | 本地部署 |

切换Provider只需修改 `LLM_PROVIDER` 环境变量。

---

## RAG 配置

向量数据库（默认Chroma）：

```bash
VECTOR_STORE_TYPE=chroma
CHROMA_PERSIST_PATH=./data/db/chroma_db
RAG_TOP_K=5
```

添加知识库文档到 `docs/` 目录（.txt文件自动加载）。

---

## 更新日志

### v0.3.0 (2026-03-24)
- 对话模型默认使用阿里云DashScope千问API
- Embedding保持本地Ollama部署

### v0.2.0 (2026-03-24)
- 默认配置改为千问 + 本地Ollama

### v0.1.0 (2026-03-24)
- 完成LangGraph健康智能体核心架构

---

MIT License
