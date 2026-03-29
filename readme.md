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

## 阿里云服务器部署指南

### 前置条件

- 阿里云ECS实例（推荐配置：2核4G及以上）
- 操作系统：Ubuntu 20.04/22.04 或 CentOS 7/8
- 安全组开放端口：8000（API）、1883（MQTT）、11434（Ollama）

### 步骤一：服务器环境准备

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装依赖
sudo apt install -y build-essential libssl-dev zlib1g-dev \
    libbz2-dev libreadline-dev libsqlite3-dev curl \
    libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev git

# 安装pyenv（Python版本管理）
curl https://pyenv.run | bash

# 配置pyenv环境变量
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
echo '[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
echo 'eval "$(pyenv init -)"' >> ~/.bashrc
source ~/.bashrc

# 安装Python 3.11（推荐，兼容性最佳）
pyenv install 3.11.9

# 安装Docker（可选，用于Docker部署）
curl -fsSL https://get.docker.com | bash
sudo usermod -aG docker $USER
```

### 步骤二：安装Ollama（Embedding服务）

```bash
# 安装Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 启动Ollama服务
ollama serve &

# 下载Embedding模型
ollama pull nomic-embed-text

# 验证安装
ollama list
```

### 步骤三：配置项目

```bash
# 克隆仓库
git clone https://github.com/MzrQ1/BioLing_Cloud_Agent.git
cd BioLing_Cloud_Agent

# 设置项目Python版本为3.11
pyenv local 3.11.9

# 验证Python版本
python --version  # 应显示 Python 3.11.9

# 创建虚拟环境
python -m venv venv
source venv/bin/activate

# 安装依赖
pip install --upgrade pip
pip install -r requirements.txt

# 创建配置文件
cp .env.example .env
```

### 步骤四：编辑配置文件

```bash
nano .env
```

**必须修改的配置：**

```bash
# 阿里云千问API密钥（必填）
DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxxxxx

# 服务器公网IP或域名
MQTT_BROKER=0.0.0.0

# Ollama地址（本地部署）
EMBEDDING_API_BASE=http://localhost:11434
```

**可选修改的配置：**

```bash
# 对话模型配置
LLM_PROVIDER=dashscope
LLM_DIALOG_MODEL=qwen2.5-7b-instruct
LLM_TEMPERATURE=0.7

# RAG配置
RAG_ENABLE_HYBRID_SEARCH=true
RAG_ENABLE_RERANK=true
```

### 步骤五：启动服务

**方式一：直接启动（开发/测试）**

```bash
# 启动API服务
cd app
uvicorn main:app --host 0.0.0.0 --port 8000
```

**方式二：后台运行（生产环境）**

```bash
# 使用nohup后台运行
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > logs/app.log 2>&1 &

# 查看日志
tail -f logs/app.log
```

**方式三：使用Supervisor（推荐生产环境）**

```bash
# 安装Supervisor
sudo apt install -y supervisor

# 创建配置文件
sudo nano /etc/supervisor/conf.d/biolid.conf
```

配置内容：
```ini
[program:biolid]
directory=/root/BioLing_Cloud_Agent
command=/root/BioLing_Cloud_Agent/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
user=root
autostart=true
autorestart=true
startsecs=10
stopwaitsecs=60
redirect_stderr=true
stdout_logfile=/root/BioLing_Cloud_Agent/logs/app.log
```

启动服务：
```bash
# 创建日志目录
mkdir -p logs

# 重新加载配置
sudo supervisorctl reread
sudo supervisorctl update

# 启动服务
sudo supervisorctl start biolid

# 查看状态
sudo supervisorctl status
```

**方式四：Docker部署**

```bash
# 构建并启动
docker-compose up -d --build

# 查看日志
docker-compose logs -f app

# 停止服务
docker-compose down
```

### 步骤六：验证部署

```bash
# 健康检查
curl http://localhost:8000/api/v1/health

# 查看API文档
# 浏览器访问：http://<服务器公网IP>:8000/docs
```

### 步骤七：配置安全组

在阿里云控制台配置安全组规则：

| 端口 | 协议 | 用途 | 来源 |
|------|------|------|------|
| 8000 | TCP | API服务 | 0.0.0.0/0 或指定IP |
| 1883 | TCP | MQTT | ESP32设备IP |
| 11434 | TCP | Ollama | 127.0.0.1（仅本地） |
| 22 | TCP | SSH | 管理员IP |

### 步骤八：ESP32连接配置

ESP32代码中修改服务器地址：

```cpp
const char* mqtt_server = "你的服务器公网IP";
const int mqtt_port = 1883;
const char* mqtt_topic = "biolid/esp32/sensor_data";
```

### 常见问题

**Q: Ollama连接失败**
```bash
# 检查Ollama服务状态
systemctl status ollama

# 重启Ollama
ollama serve &

# 测试连接
curl http://localhost:11434/api/tags
```

**Q: API无法访问**
```bash
# 检查端口占用
netstat -tlnp | grep 8000

# 检查防火墙
sudo ufw status
sudo ufw allow 8000
```

**Q: 内存不足**
```bash
# 查看内存使用
free -h

# 创建交换空间
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

### 部署架构图

```
┌─────────────────────────────────────────────────────────────┐
│                      阿里云ECS服务器                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   Ollama    │  │   FastAPI   │  │      ChromaDB       │  │
│  │  (Embedding)│  │  (Port 8000)│  │    (向量数据库)      │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
│         │                │                    │              │
│         └────────────────┼────────────────────┘              │
│                          │                                   │
│  ┌───────────────────────┴───────────────────────────────┐  │
│  │              BioLing Cloud Agent                       │  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────────┐  │  │
│  │  │ LangGraph│ │   RAG   │ │   ML    │ │  千问API    │  │  │
│  │  │  Agent  │ │ 混合检索 │ │  推理   │ │ (DashScope) │  │  │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
         ▲                                    ▲
         │ MQTT                               │ HTTPS
         │                                    │
┌────────┴────────┐                  ┌────────┴────────┐
│     ESP32-S3    │                  │    Web前端      │
│   (生理数据采集) │                  │  (用户交互界面)  │
└─────────────────┘                  └─────────────────┘
```

---

## 快速部署（本地开发）

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

### 3. 启动Embedding服务

```bash
ollama serve
ollama pull nomic-embed-text
```

### 4. 启动服务

```bash
cd app
uvicorn main:app --reload --host 0.0.0.0 --port 8000
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
│   │   ├── database.py        # SQLite连接
│   │   ├── models.py          # 数据模型
│   │   ├── vector_store.py    # 向量库 (RAG)
│   │   ├── feature_store.py   # 特征库 (SQLite)
│   │   ├── timeseries.py      # 时序库 (SQLite)
│   │   └── checkpoint_store.py # 会话检查点 (内存)
│   │
│   └── interfaces/           # 外部接口
│       ├── api_routes.py     # HTTP API
│       └── mqtt_listener.py  # MQTT 监听
│
├── docs/                     # RAG知识库
├── tests/                    # 测试
└── data/                     # 数据存储
    └── db/
        ├── biolid.db         # SQLite数据库
        └── chroma_db/        # 向量数据库
```

---

## 数据库架构

### 存储策略

| 数据类型 | 存储方式 | 说明 |
|----------|----------|------|
| 生理数据 | SQLite | 长期持久化，支持时间范围查询 |
| 用户画像 | SQLite | 长期记忆，历史统计 |
| 特征历史 | SQLite | ML提取特征，趋势分析 |
| 对话历史 | SQLite | 用户交互记录 |
| 会话检查点 | 内存 | 短期上下文，重启丢失 |
| RAG知识库 | ChromaDB | 向量检索 |

### 数据表结构

```
┌─────────────────────────────────────────────────────────────┐
│                    SQLite (biolid.db)                       │
├─────────────────┬─────────────────┬─────────────────────────┤
│ physiological_  │  user_profiles  │   feature_history       │
│     data        │                 │                         │
│ ─────────────── │ ─────────────── │ ─────────────────────── │
│ user_id         │ user_id (PK)    │ user_id                 │
│ timestamp       │ avg_heart_rate  │ timestamp               │
│ heart_rate      │ avg_sdnn        │ stress_index            │
│ ibi_mean        │ avg_stress      │ emotion                 │
│ sdnn            │ total_sessions  │ risk_level              │
│ rmssd           │ high_stress_    │ heart_rate              │
│ stress_index    │   events        │ sdnn, rmssd             │
│ emotion         │ baseline_hr     │                         │
│ risk_level      │ baseline_sdnn   │                         │
├─────────────────┴─────────────────┴─────────────────────────┤
│              conversation_history                            │
│ ─────────────────────────────────────────────────────────── │
│ user_id, session_id, role, content, emotion_state           │
└─────────────────────────────────────────────────────────────┘
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

### 混合检索 + Rerank

系统支持**向量检索 + BM25关键词检索**混合检索，以及**Cross-Encoder Rerank**重排序：

```
Query → 向量检索 ─┬→ 分数融合 → Rerank → Top-K结果
                  │
       BM25检索 ──┘
```

### 配置参数

```bash
# 向量数据库
VECTOR_STORE_TYPE=chroma
CHROMA_PERSIST_PATH=./data/db/chroma_db
RAG_TOP_K=5
RAG_SIMILARITY_THRESHOLD=0.7

# 混合检索
RAG_ENABLE_HYBRID_SEARCH=true    # 启用混合检索
RAG_HYBRID_ALPHA=0.5             # 向量权重（0-1，BM25权重=1-alpha）

# Rerank重排序
RAG_ENABLE_RERANK=true           # 启用Rerank
RAG_RERANK_MODEL=BAAI/bge-reranker-base  # Rerank模型
RAG_RERANK_TOP_K=3               # Rerank后返回数量
```

### 检索策略对比

| 策略 | 说明 | 适用场景 |
|------|------|----------|
| 纯向量检索 | 语义相似度 | 概念匹配 |
| 纯BM25 | 关键词匹配 | 精确术语 |
| 混合检索 | 向量+BM25融合 | 通用场景（推荐） |
| 混合+Rerank | 混合检索后重排序 | 高精度需求 |

### 添加知识库

**方式一：文件导入（推荐）**

1. 准备 `.txt` 文件，每段知识用空行分隔：
```
深呼吸是最简单有效的减压方法。尝试4-7-8呼吸法...

渐进式肌肉放松训练（PMR）可有效缓解身体紧张...
```

2. 放入 `docs/` 目录：
```
biolid-cloud-agent/
├── docs/
│   ├── stress_management.txt    # 压力管理知识
│   ├── sleep_hygiene.txt        # 睡眠卫生知识
│   └── exercise_tips.txt        # 运动建议
```

3. 运行导入脚本：
```bash
python scripts/import_knowledge.py --import
```

**方式二：代码添加**

```python
from app.database.vector_store import VectorStore

vs = VectorStore()
vs.add_document({
    "id": "custom_001",
    "category": "stress_management",
    "content": "正念练习：每日冥想10分钟可降低皮质醇水平"
})
```

**管理命令**：
```bash
# 查看知识库统计
python scripts/import_knowledge.py --stats

# 测试检索效果
python scripts/import_knowledge.py --test "如何缓解压力"
```

---

## 更新日志

### v0.6.1 (2026-03-28)
- 新增RAG知识库导入脚本 scripts/import_knowledge.py
- 支持批量导入.txt文件到向量数据库
- 添加知识库统计和测试查询功能

### v0.6.0 (2026-03-28)
- 重构数据库层：SQLite持久化替代内存存储
- 新增数据表：physiological_data, user_profiles, feature_history, conversation_history
- 短期上下文保留内存存储（CheckpointStore）
- 长期数据全部持久化到SQLite

### v0.5.1 (2026-03-28)
- 更新部署指南：使用pyenv管理Python版本（推荐3.11.9）
- 修复requirements.txt依赖版本兼容性问题
- 限制numpy<2.0.0和chromadb版本范围

### v0.5.0 (2026-03-28)
- 新增阿里云服务器完整部署指南
- 添加Supervisor生产环境部署方案
- 添加部署架构图和常见问题解答

### v0.4.0 (2026-03-28)
- 新增BM25关键词检索模块
- 实现混合检索（向量+BM25分数融合）
- 实现Rerank重排序（Cross-Encoder）
- 新增RAG配置参数支持

### v0.3.0 (2026-03-24)
- 对话模型默认使用阿里云DashScope千问API
- Embedding保持本地Ollama部署

### v0.2.0 (2026-03-24)
- 默认配置改为千问 + 本地Ollama

### v0.1.0 (2026-03-24)
- 完成LangGraph健康智能体核心架构

---

MIT License
