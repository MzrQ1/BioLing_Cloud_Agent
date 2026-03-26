"""向量库 - RAG知识库"""
from typing import List, Dict, Optional
import json
import os
from datetime import datetime
from pathlib import Path

class VectorStore:
    def __init__(
        self,
        persist_path: Optional[str] = None,
        collection_name: str = "health_knowledge",
        use_embeddings: bool = True
    ):
        self.persist_path = persist_path or self._get_default_path()
        self.collection_name = collection_name
        self.use_embeddings = use_embeddings
        self._knowledge_base: List[Dict] = []
        self._embeddings: List[List[float]] = []
        self._chroma_client = None
        self._chroma_collection = None

        self._init_vector_store()

    def _get_default_path(self) -> str:
        from app.config import config
        return config.RAG.CHROMA_PERSIST_PATH

    def _init_vector_store(self):
        if self.use_embeddings:
            self._init_chroma()
        else:
            self._init_memory_store()

    def _init_chroma(self):
        try:
            import chromadb
            from chromadb.config import Settings

            os.makedirs(self.persist_path, exist_ok=True)

            self._chroma_client = chromadb.Client(Settings(
                persist_directory=self.persist_path,
                anonymized_telemetry=False
            ))

            try:
                self._chroma_collection = self._chroma_client.get_collection(
                    name=self.collection_name
                )
            except Exception:
                self._chroma_collection = self._chroma_client.create_collection(
                    name=self.collection_name,
                    metadata={"description": "Health knowledge base for RAG"}
                )

            self._load_existing_docs()
        except ImportError:
            self.use_embeddings = False
            self._init_memory_store()

    def _init_memory_store(self):
        self._knowledge_base = self._load_knowledge_base()
        if not self._knowledge_base:
            self._init_default_knowledge()

    def _load_existing_docs(self):
        if self._chroma_collection is None:
            return

        try:
            results = self._chroma_collection.get(include=["documents", "metadatas"])
            for i, doc in enumerate(results.get("documents", [])):
                self._knowledge_base.append({
                    "id": results["metadatas"][i].get("id", f"doc_{i}"),
                    "category": results["metadatas"][i].get("category", "general"),
                    "content": doc,
                    "source": results["metadatas"][i].get("source", "unknown")
                })
        except Exception:
            pass

    def query(self, query_text: str, top_k: int = 5) -> List[Dict]:
        if self.use_embeddings and self._chroma_collection is not None:
            return self._query_with_chroma(query_text, top_k)
        else:
            return self._query_with_keywords(query_text, top_k)

    def _query_with_chroma(self, query_text: str, top_k: int) -> List[Dict]:
        try:
            from app.agent.tools import EmbeddingCaller

            query_embedding = EmbeddingCaller.embed([query_text])[0]

            results = self._chroma_collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                include=["documents", "metadatas", "distances"]
            )

            docs = []
            for i, doc in enumerate(results.get("documents", [[]])[0]):
                distance = results.get("distances", [[]])[0][i]
                similarity = 1 - distance if distance else 0.5

                docs.append({
                    "id": results["metadatas"][0][i].get("id", f"doc_{i}"),
                    "category": results["metadatas"][0][i].get("category", "general"),
                    "content": doc,
                    "source": results["metadatas"][0][i].get("source", "unknown"),
                    "similarity": similarity
                })

            return docs
        except Exception:
            return self._query_with_keywords(query_text, top_k)

    def _query_with_keywords(self, query_text: str, top_k: int) -> List[Dict]:
        query_lower = query_text.lower()

        stress_keywords = ["压力", "stress", "紧张", "焦虑", "anxiety"]
        sleep_keywords = ["睡眠", "sleep", "休息", "失眠"]
        exercise_keywords = ["运动", "exercise", "锻炼", "活动"]
        diet_keywords = ["饮食", "diet", "食物", "营养"]

        scored_results = []
        for item in self._knowledge_base:
            score = 0
            content_lower = item.get("content", "").lower()

            if any(kw in query_lower or kw in content_lower for kw in stress_keywords):
                score += 2
            if any(kw in query_lower or kw in content_lower for kw in sleep_keywords):
                score += 1
            if any(kw in query_lower or kw in content_lower for kw in exercise_keywords):
                score += 1
            if any(kw in query_lower or kw in content_lower for kw in diet_keywords):
                score += 1

            if item.get("category") == "stress_management":
                score += 1

            if score > 0:
                scored_results.append((score, item))

        scored_results.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored_results[:top_k]]

    def add_document(self, doc: Dict) -> bool:
        doc["added_at"] = datetime.now().isoformat()

        if self.use_embeddings and self._chroma_collection is not None:
            try:
                from app.agent.tools import EmbeddingCaller

                embedding = EmbeddingCaller.embed([doc["content"]])[0]
                doc_id = doc.get("id", f"doc_{len(self._knowledge_base)}")

                self._chroma_collection.add(
                    embeddings=[embedding],
                    documents=[doc["content"]],
                    metadatas=[{
                        "id": doc_id,
                        "category": doc.get("category", "general"),
                        "source": doc.get("source", "user_upload"),
                        "added_at": doc["added_at"]
                    }],
                    ids=[doc_id]
                )
            except Exception as e:
                pass

        self._knowledge_base.append(doc)
        return True

    def add_documents_from_folder(self, folder_path: str) -> int:
        docs_path = Path(folder_path)
        if not docs_path.exists():
            return 0

        count = 0
        for file_path in docs_path.glob("*.txt"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                doc = {
                    "id": f"doc_{count}",
                    "category": "user_knowledge",
                    "content": content,
                    "source": file_path.name
                }
                if self.add_document(doc):
                    count += 1
            except Exception:
                continue

        return count

    def _load_knowledge_base(self) -> List[Dict]:
        cache_file = Path(self.persist_path) / "knowledge_cache.json"
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def save_knowledge_base(self):
        cache_file = Path(self.persist_path) / "knowledge_cache.json"
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(self._knowledge_base, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _init_default_knowledge(self):
        self._knowledge_base = [
            {
                "id": "stress_001",
                "category": "stress_management",
                "content": "深呼吸是最简单有效的减压方法。尝试4-7-8呼吸法：吸气4秒，屏气7秒，呼气8秒，重复3-5次可显著降低焦虑水平。",
                "source": "医学健康知识库"
            },
            {
                "id": "stress_002",
                "category": "stress_management",
                "content": "渐进式肌肉放松训练（PMR）可有效缓解身体紧张。从脚趾开始，逐步收紧并放松各肌肉群，每次15-20分钟。",
                "source": "医学健康知识库"
            },
            {
                "id": "sleep_001",
                "category": "sleep_hygiene",
                "content": "睡眠卫生建议：保持规律作息，睡前1小时避免使用电子设备，室温控制在18-22摄氏度，有助于提升睡眠质量。",
                "source": "医学健康知识库"
            },
            {
                "id": "sleep_002",
                "category": "sleep_hygiene",
                "content": "午睡时间建议控制在20-30分钟，过长的午睡会影响夜间睡眠质量，并可能导致下午感到更加困倦。",
                "source": "医学健康知识库"
            },
            {
                "id": "hrv_001",
                "category": "hrv_analysis",
                "content": "心率变异性（HRV）是评估自主神经系统功能的重要指标。较高的HRV通常表示身体更能适应压力恢复。",
                "source": "医学健康知识库"
            },
            {
                "id": "exercise_001",
                "category": "exercise",
                "content": "每周进行150分钟中等强度有氧运动（如快走、游泳、骑行）可显著改善心肺功能，降低静息心率，提高HRV。",
                "source": "医学健康知识库"
            },
            {
                "id": "mindfulness_001",
                "category": "mindfulness",
                "content": "正念冥想每日练习10-15分钟，持续8周可明显改善压力感知能力和情绪调节能力。",
                "source": "医学健康知识库"
            }
        ]
