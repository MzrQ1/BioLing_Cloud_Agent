"""全局配置"""
import os
from pathlib import Path
from typing import Optional, Dict, Any

BASE_DIR = Path(__file__).resolve().parent.parent

class LLMConfig:
    """大模型配置"""
    PROVIDER: str = os.getenv("LLM_PROVIDER", "dashscope")

    DIALOG_MODEL: str = os.getenv("LLM_DIALOG_MODEL", "qwen2.5-7b-instruct")
    DIALOG_API_BASE: str = os.getenv("LLM_DIALOG_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    DIALOG_API_KEY: str = os.getenv("DASHSCOPE_API_KEY", "")

    EMBEDDING_PROVIDER: str = os.getenv("EMBEDDING_PROVIDER", "ollama")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
    EMBEDDING_API_BASE: str = os.getenv("EMBEDDING_API_BASE", "http://localhost:11434")
    EMBEDDING_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.7"))
    MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "1000"))

    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        return {
            "provider": cls.PROVIDER,
            "dialog_model": cls.DIALOG_MODEL,
            "dialog_api_base": cls.DIALOG_API_BASE,
            "embedding_provider": cls.EMBEDDING_PROVIDER,
            "embedding_model": cls.EMBEDDING_MODEL,
            "embedding_api_base": cls.EMBEDDING_API_BASE,
            "temperature": cls.TEMPERATURE,
            "max_tokens": cls.MAX_TOKENS,
        }

class RAGConfig:
    """RAG配置"""
    VECTOR_STORE_TYPE: str = os.getenv("VECTOR_STORE_TYPE", "chroma")

    CHROMA_PERSIST_PATH: str = str(BASE_DIR / "data" / "db" / "chroma_db")
    CHROMA_COLLECTION_NAME: str = os.getenv("CHROMA_COLLECTION_NAME", "health_knowledge")

    TOP_K: int = int(os.getenv("RAG_TOP_K", "5"))
    SIMILARITY_THRESHOLD: float = float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.7"))

    KNOWLEDGE_BASE_PATH: str = str(BASE_DIR / "docs")

    ENABLE_HYBRID_SEARCH: bool = os.getenv("RAG_ENABLE_HYBRID_SEARCH", "true").lower() == "true"
    HYBRID_ALPHA: float = float(os.getenv("RAG_HYBRID_ALPHA", "0.5"))

    ENABLE_RERANK: bool = os.getenv("RAG_ENABLE_RERANK", "true").lower() == "true"
    RERANK_MODEL: str = os.getenv("RAG_RERANK_MODEL", "BAAI/bge-reranker-base")
    RERANK_TOP_K: int = int(os.getenv("RAG_RERANK_TOP_K", "3"))

    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        return {
            "vector_store_type": cls.VECTOR_STORE_TYPE,
            "chroma_persist_path": cls.CHROMA_PERSIST_PATH,
            "chroma_collection_name": cls.CHROMA_COLLECTION_NAME,
            "top_k": cls.TOP_K,
            "similarity_threshold": cls.SIMILARITY_THRESHOLD,
            "knowledge_base_path": cls.KNOWLEDGE_BASE_PATH,
            "enable_hybrid_search": cls.ENABLE_HYBRID_SEARCH,
            "hybrid_alpha": cls.HYBRID_ALPHA,
            "enable_rerank": cls.ENABLE_RERANK,
            "rerank_model": cls.RERANK_MODEL,
            "rerank_top_k": cls.RERANK_TOP_K
        }

class Config:
    MODEL_CACHE_DIR = BASE_DIR / "data" / "models_cache"
    DB_PATH = BASE_DIR / "data" / "db"
    LOG_PATH = BASE_DIR / "data" / "logs"

    MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
    MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
    MQTT_TOPIC = os.getenv("MQTT_TOPIC", "biolid/esp32/sensor_data")

    INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://localhost:8086")
    INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN", "")
    INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "biolid")
    INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "sensor_data")

    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    STRESS_MODEL_PATH = BASE_DIR / "app" / "ml_services" / "models" / "stress_detector.onnx"
    ANOMALY_MODEL_PATH = BASE_DIR / "app" / "ml_services" / "models" / "anomaly_classifier.onnx"

    LLM = LLMConfig()
    RAG = RAGConfig()

config = Config()
