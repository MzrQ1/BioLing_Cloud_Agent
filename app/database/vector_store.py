"""
向量库模块 - RAG知识库（支持混合检索和Rerank）

本模块实现了完整的RAG（Retrieval-Augmented Generation）检索系统，包含：
1. BM25关键词检索 - 基于词频和逆文档频率的经典信息检索算法
2. 向量检索 - 基于Embedding的语义相似度检索
3. 混合检索 - 融合向量检索和BM25检索结果
4. Rerank重排序 - 使用Cross-Encoder对检索结果进行精细重排序

检索流程：
    Query → 向量检索 ─┬→ 分数融合 → Rerank → Top-K结果
                      │
           BM25检索 ──┘

使用示例：
    from app.database.vector_store import VectorStore

    vs = VectorStore()
    results = vs.query("如何缓解压力", top_k=3)
"""
from typing import List, Dict, Optional, Tuple
import json
import os
import math
import re
from datetime import datetime
from pathlib import Path
from collections import Counter


class BM25:
    """
    BM25关键词检索实现

    BM25（Best Matching 25）是一种基于概率检索模型的排序函数，
    是信息检索领域最经典的算法之一。它通过计算查询词与文档的
    相关性得分来排序文档。

    核心公式：
        score(D, Q) = Σ IDF(qi) * (f(qi, D) * (k1 + 1)) / (f(qi, D) + k1 * (1 - b + b * |D| / avgdl))

    其中：
        - f(qi, D): 词qi在文档D中的词频
        - |D|: 文档D的长度
        - avgdl: 平均文档长度
        - k1: 词频饱和参数，控制词频增长的边际递减效应
        - b: 文档长度归一化参数

    Attributes:
        k1 (float): 词频饱和参数，默认1.5，值越大词频影响越大
        b (float): 文档长度归一化参数，默认0.75，值越大长度惩罚越强
        doc_freqs (Dict): 记录每个词在多少文档中出现
        doc_lens (List): 每个文档的长度
        avgdl (float): 平均文档长度
        doc_term_freqs (List): 每个文档的词频统计
        n_docs (int): 文档总数
        idf (Dict): 每个词的逆文档频率值
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        """
        初始化BM25检索器

        Args:
            k1: 词频饱和参数，通常取值1.2-2.0，默认1.5
            b: 文档长度归一化参数，通常取值0.75，范围0-1
        """
        self.k1 = k1
        self.b = b
        self.doc_freqs: Dict[str, int] = {}
        self.doc_lens: List[int] = []
        self.avgdl: float = 0
        self.doc_term_freqs: List[Dict[str, int]] = []
        self.n_docs: int = 0
        self.idf: Dict[str, float] = {}

    def _tokenize(self, text: str) -> List[str]:
        """
        文本分词

        支持中英文混合文本，将文本拆分为token列表。
        英文按单词分割，中文按字符分割。

        Args:
            text: 待分词的文本

        Returns:
            分词后的token列表

        Example:
            >>> bm25._tokenize("Hello世界")
            ['hello', '世', '界']
        """
        text = text.lower()
        tokens = re.findall(r'\w+|[\u4e00-\u9fff]+', text)
        return tokens

    def fit(self, documents: List[str]):
        """
        训练BM25模型

        对文档集合进行预处理，计算IDF值和文档长度统计。
        必须在search之前调用。

        Args:
            documents: 文档列表，每个元素是一个文档字符串

        Note:
            - 计算每个文档的词频统计
            - 计算每个词的文档频率（出现在多少文档中）
            - 计算平均文档长度
            - 计算每个词的IDF值
        """
        self.n_docs = len(documents)
        self.doc_term_freqs = []
        self.doc_lens = []

        for doc in documents:
            tokens = self._tokenize(doc)
            self.doc_lens.append(len(tokens))
            term_freqs = Counter(tokens)
            self.doc_term_freqs.append(dict(term_freqs))

            for term in term_freqs:
                if term not in self.doc_freqs:
                    self.doc_freqs[term] = 0
                self.doc_freqs[term] += 1

        self.avgdl = sum(self.doc_lens) / self.n_docs if self.n_docs > 0 else 0

        for term, freq in self.doc_freqs.items():
            self.idf[term] = math.log((self.n_docs - freq + 0.5) / (freq + 0.5) + 1)

    def search(self, query: str, top_k: int = 10) -> List[Tuple[int, float]]:
        """
        执行BM25检索

        计算查询与所有文档的相关性得分，返回top_k个最相关文档。

        Args:
            query: 查询文本
            top_k: 返回的最大文档数

        Returns:
            List[Tuple[int, float]]: (文档索引, BM25得分)的列表，按得分降序排列

        Example:
            >>> bm25.fit(["压力管理很重要", "睡眠质量影响健康"])
            >>> bm25.search("压力", top_k=1)
            [(0, 0.693)]
        """
        query_tokens = self._tokenize(query)
        scores = []

        for doc_idx, term_freqs in enumerate(self.doc_term_freqs):
            score = 0
            doc_len = self.doc_lens[doc_idx]

            for term in query_tokens:
                if term not in term_freqs:
                    continue

                tf = term_freqs[term]
                idf = self.idf.get(term, 0)

                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / self.avgdl)
                score += idf * numerator / denominator

            scores.append((doc_idx, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]


class Reranker:
    """
    Rerank重排序器

    使用Cross-Encoder模型对检索结果进行精细重排序。
    Cross-Encoder将query和document同时输入模型，能够捕捉
    query-document之间的深层语义交互，比Bi-Encoder更精确。

    工作原理：
        1. 将(query, document)对输入Cross-Encoder
        2. 模型输出一个相关性得分
        3. 根据得分重新排序文档

    推荐模型：
        - BAAI/bge-reranker-base: 轻量级，适合中文
        - BAAI/bge-reranker-large: 更大更精确
        - cross-encoder/ms-marco-MiniLM-L-6-v2: 英文通用

    Attributes:
        model_name (str): HuggingFace模型名称
        _model: 延迟加载的CrossEncoder模型实例
    """

    def __init__(self, model_name: str = "BAAI/bge-reranker-base"):
        """
        初始化Reranker

        Args:
            model_name: HuggingFace上的模型名称，默认使用bge-reranker-base
        """
        self.model_name = model_name
        self._model = None
        self._tokenizer = None

    def _load_model(self):
        """
        延迟加载模型

        模型在第一次使用时才加载，避免不必要的内存占用。
        如果sentence-transformers未安装，则跳过rerank。
        """
        if self._model is not None:
            return

        try:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(self.model_name, max_length=512)
        except ImportError:
            self._model = None

    def rerank(
        self,
        query: str,
        documents: List[Dict],
        top_k: int = 3
    ) -> List[Dict]:
        """
        对文档列表进行重排序

        Args:
            query: 查询文本
            documents: 待重排序的文档列表，每个文档是包含content字段的字典
            top_k: 返回的最大文档数

        Returns:
            重排序后的文档列表，每个文档增加rerank_score字段

        Example:
            >>> reranker = Reranker()
            >>> docs = [{"content": "深呼吸可以缓解压力"}, {"content": "运动有益健康"}]
            >>> reranked = reranker.rerank("如何减压", docs, top_k=2)
            >>> print(reranked[0]["rerank_score"])
            0.85
        """
        if not documents:
            return documents

        self._load_model()

        if self._model is None:
            return documents[:top_k]

        try:
            pairs = [(query, doc.get("content", "")) for doc in documents]
            scores = self._model.predict(pairs)

            scored_docs = list(zip(documents, scores))
            scored_docs.sort(key=lambda x: x[1], reverse=True)

            reranked = []
            for doc, score in scored_docs[:top_k]:
                doc_copy = doc.copy()
                doc_copy["rerank_score"] = float(score)
                reranked.append(doc_copy)

            return reranked
        except Exception:
            return documents[:top_k]


class VectorStore:
    """
    向量库主类 - 支持混合检索和Rerank

    这是RAG系统的核心组件，提供完整的知识库管理功能：
    - 文档存储（内存 + Chroma向量数据库）
    - 多种检索策略（向量检索、BM25检索、混合检索）
    - Rerank重排序
    - 知识库持久化

    检索策略选择：
        1. enable_hybrid=True: 混合检索（向量+BM25融合）
        2. enable_hybrid=False + use_embeddings=True: 纯向量检索
        3. enable_hybrid=False + use_embeddings=False: 纯BM25检索

    检索流程：
        query() → 选择检索策略 → 执行检索 → Rerank(可选) → 阈值过滤 → 返回结果

    Attributes:
        persist_path (str): 数据持久化路径
        collection_name (str): Chroma集合名称
        use_embeddings (bool): 是否使用向量检索
        enable_hybrid (bool): 是否启用混合检索
        enable_rerank (bool): 是否启用Rerank
        _knowledge_base (List): 内存中的知识库
        _chroma_collection: Chroma向量数据库集合
        _bm25: BM25检索器实例
        _reranker: Reranker实例
    """

    def __init__(
        self,
        persist_path: Optional[str] = None,
        collection_name: str = "health_knowledge",
        use_embeddings: bool = True,
        enable_hybrid: bool = True,
        enable_rerank: bool = True
    ):
        """
        初始化向量库

        Args:
            persist_path: 数据持久化目录，默认从配置读取
            collection_name: Chroma集合名称
            use_embeddings: 是否使用向量检索，False则仅用BM25
            enable_hybrid: 是否启用混合检索（向量+BM25融合）
            enable_rerank: 是否启用Rerank重排序
        """
        self.persist_path = persist_path or self._get_default_path()
        self.collection_name = collection_name
        self.use_embeddings = use_embeddings
        self.enable_hybrid = enable_hybrid
        self.enable_rerank = enable_rerank

        self._knowledge_base: List[Dict] = []
        self._embeddings: List[List[float]] = []
        self._chroma_client = None
        self._chroma_collection = None

        self._bm25: Optional[BM25] = None
        self._reranker: Optional[Reranker] = None

        self._init_vector_store()

    def _get_default_path(self) -> str:
        """获取默认持久化路径"""
        from app.config import config
        return config.RAG.CHROMA_PERSIST_PATH

    def _get_rag_config(self):
        """获取RAG配置"""
        from app.config import config
        return config.RAG

    def _init_vector_store(self):
        """
        初始化向量库

        按顺序初始化各个组件：
        1. Chroma向量数据库（如果启用）
        2. 内存存储（如果未启用向量数据库）
        3. BM25检索器
        4. Reranker（如果启用）
        """
        if self.use_embeddings:
            self._init_chroma()
        else:
            self._init_memory_store()

        self._init_bm25()

        if self.enable_rerank:
            rag_config = self._get_rag_config()
            self._reranker = Reranker(rag_config.RERANK_MODEL)

    def _init_chroma(self):
        """
        初始化Chroma向量数据库

        Chroma是一个轻量级的向量数据库，支持：
        - 向量相似度检索
        - 元数据过滤
        - 数据持久化

        如果Chroma未安装，自动降级为内存存储。
        """
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
        """
        初始化内存存储

        当Chroma不可用时的降级方案，使用内存+JSON文件存储。
        """
        self._knowledge_base = self._load_knowledge_base()
        if not self._knowledge_base:
            self._init_default_knowledge()

    def _init_bm25(self):
        """
        初始化BM25检索器

        基于当前知识库训练BM25模型。
        每次添加新文档后需要重新调用以更新索引。
        """
        self._bm25 = BM25()
        documents = [doc.get("content", "") for doc in self._knowledge_base]
        if documents:
            self._bm25.fit(documents)

    def _load_existing_docs(self):
        """
        从Chroma加载已有文档到内存

        将向量数据库中的文档同步到内存知识库，
        便于BM25检索和文档管理。
        """
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
        """
        执行知识库检索

        根据配置选择检索策略，执行检索并返回结果。

        检索策略优先级：
            1. 混合检索（enable_hybrid=True + use_embeddings=True）
            2. 纯向量检索（enable_hybrid=False + use_embeddings=True）
            3. 纯BM25检索（use_embeddings=False）

        Args:
            query_text: 查询文本
            top_k: 返回的最大文档数

        Returns:
            List[Dict]: 检索结果列表，每个元素包含：
                - id: 文档ID
                - category: 文档类别
                - content: 文档内容
                - source: 文档来源
                - similarity/bm25_score/hybrid_score: 相关性得分
                - rerank_score: Rerank得分（如果启用）

        Example:
            >>> vs = VectorStore()
            >>> results = vs.query("如何缓解压力", top_k=3)
            >>> for r in results:
            ...     print(r["content"], r.get("rerank_score", r.get("similarity")))
        """
        rag_config = self._get_rag_config()

        enable_hybrid = self.enable_hybrid and rag_config.ENABLE_HYBRID_SEARCH
        enable_rerank = self.enable_rerank and rag_config.ENABLE_RERANK

        if enable_hybrid and self.use_embeddings and self._chroma_collection is not None:
            results = self._hybrid_search(query_text, top_k, rag_config.HYBRID_ALPHA)
        elif self.use_embeddings and self._chroma_collection is not None:
            results = self._query_with_chroma(query_text, top_k)
        else:
            results = self._query_with_bm25(query_text, top_k)

        if enable_rerank and self._reranker is not None and results:
            rerank_top_k = rag_config.RERANK_TOP_K
            results = self._reranker.rerank(query_text, results, rerank_top_k)

        threshold = rag_config.SIMILARITY_THRESHOLD
        if threshold > 0:
            results = [
                r for r in results
                if r.get("similarity", 1) >= threshold or r.get("rerank_score", 1) > 0
            ]

        return results

    def _hybrid_search(self, query_text: str, top_k: int, alpha: float) -> List[Dict]:
        """
        混合检索实现

        融合向量检索和BM25检索的结果，通过加权求和得到最终得分。

        融合公式：
            final_score = alpha * normalized_bm25_score + (1 - alpha) * vector_similarity

        Args:
            query_text: 查询文本
            top_k: 返回的最大文档数
            alpha: BM25权重，向量权重为(1-alpha)

        Returns:
            List[Dict]: 融合后的检索结果，包含：
                - hybrid_score: 融合得分
                - vector_component: 向量检索贡献
                - bm25_component: BM25检索贡献

        Note:
            - 两种检索各取top_k*2个结果，扩大召回范围
            - BM25得分需要归一化到[0,1]区间
            - 相同ID的文档合并得分
        """
        vector_results = self._query_with_chroma(query_text, top_k * 2)
        bm25_results = self._query_with_bm25(query_text, top_k * 2)

        vector_scores = {}
        for i, doc in enumerate(vector_results):
            doc_id = doc.get("id", f"vec_{i}")
            vector_scores[doc_id] = {
                "score": doc.get("similarity", 0) * (1 - alpha),
                "doc": doc
            }

        bm25_scores = {}
        max_bm25 = max((d.get("bm25_score", 1) for d in bm25_results), default=1)
        for i, doc in enumerate(bm25_results):
            doc_id = doc.get("id", f"bm25_{i}")
            normalized_score = doc.get("bm25_score", 0) / max_bm25 if max_bm25 > 0 else 0
            bm25_scores[doc_id] = {
                "score": normalized_score * alpha,
                "doc": doc
            }

        combined = {}
        for doc_id, data in vector_scores.items():
            if doc_id not in combined:
                combined[doc_id] = {"vector_score": 0, "bm25_score": 0, "doc": data["doc"]}
            combined[doc_id]["vector_score"] = data["score"]

        for doc_id, data in bm25_scores.items():
            if doc_id not in combined:
                combined[doc_id] = {"vector_score": 0, "bm25_score": 0, "doc": data["doc"]}
            combined[doc_id]["bm25_score"] = data["score"]

        for doc_id in combined:
            combined[doc_id]["final_score"] = (
                combined[doc_id]["vector_score"] + combined[doc_id]["bm25_score"]
            )

        sorted_results = sorted(
            combined.values(),
            key=lambda x: x["final_score"],
            reverse=True
        )

        results = []
        for item in sorted_results[:top_k]:
            doc = item["doc"].copy()
            doc["hybrid_score"] = item["final_score"]
            doc["vector_component"] = item["vector_score"]
            doc["bm25_component"] = item["bm25_score"]
            results.append(doc)

        return results

    def _query_with_chroma(self, query_text: str, top_k: int) -> List[Dict]:
        """
        向量检索实现

        使用Embedding模型将查询转换为向量，在Chroma中执行相似度检索。

        Args:
            query_text: 查询文本
            top_k: 返回的最大文档数

        Returns:
            List[Dict]: 检索结果，包含similarity字段

        Note:
            - 使用余弦距离，distance越小越相似
            - similarity = 1 - distance
            - 如果向量检索失败，自动降级为BM25检索
        """
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
            return self._query_with_bm25(query_text, top_k)

    def _query_with_bm25(self, query_text: str, top_k: int) -> List[Dict]:
        """
        BM25检索实现

        使用BM25算法进行关键词检索。

        Args:
            query_text: 查询文本
            top_k: 返回的最大文档数

        Returns:
            List[Dict]: 检索结果，包含bm25_score字段

        Note:
            - BM25得分归一化为similarity: min(score/10, 1.0)
            - 适合精确关键词匹配场景
        """
        if self._bm25 is None or not self._knowledge_base:
            return []

        scores = self._bm25.search(query_text, top_k)

        results = []
        for doc_idx, score in scores:
            if doc_idx < len(self._knowledge_base):
                doc = self._knowledge_base[doc_idx].copy()
                doc["bm25_score"] = score
                doc["similarity"] = min(score / 10, 1.0)
                results.append(doc)

        return results

    def add_document(self, doc: Dict) -> bool:
        """
        添加单个文档到知识库

        将文档同时添加到内存和向量数据库（如果启用）。

        Args:
            doc: 文档字典，应包含：
                - id: 文档唯一标识（可选，自动生成）
                - category: 文档类别（可选，默认"general"）
                - content: 文档内容（必需）
                - source: 文档来源（可选）

        Returns:
            bool: 是否添加成功

        Example:
            >>> vs = VectorStore()
            >>> vs.add_document({
            ...     "id": "custom_001",
            ...     "category": "stress_management",
            ...     "content": "正念练习可以降低压力水平"
            ... })
            True
        """
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
            except Exception:
                pass

        self._knowledge_base.append(doc)

        self._init_bm25()

        return True

    def add_documents_from_folder(self, folder_path: str) -> int:
        """
        从文件夹批量导入文档

        扫描指定目录下的所有.txt文件并导入知识库。

        Args:
            folder_path: 文档目录路径

        Returns:
            int: 成功导入的文档数量

        Note:
            - 仅支持.txt文件
            - 文件名作为source字段
            - category默认为"user_knowledge"
        """
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
        """
        从缓存文件加载知识库

        读取持久化的knowledge_cache.json文件。

        Returns:
            List[Dict]: 知识库文档列表
        """
        cache_file = Path(self.persist_path) / "knowledge_cache.json"
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def save_knowledge_base(self):
        """
        保存知识库到缓存文件

        将内存中的知识库持久化为JSON文件。
        """
        cache_file = Path(self.persist_path) / "knowledge_cache.json"
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(self._knowledge_base, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _init_default_knowledge(self):
        """
        初始化默认知识库

        当知识库为空时，加载预设的健康管理知识。
        包含压力管理、睡眠卫生、HRV分析、运动建议等类别。
        """
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
