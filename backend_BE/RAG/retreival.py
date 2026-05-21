"""
RAG Retrieval Module with incremental ingest support and hybrid query mode.
"""

import logging
import os
import pickle
import threading
from typing import Any, Dict, List, Optional

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


logger = logging.getLogger("rag_retrieval")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STORE_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "rag_store")
INDEX_PATH = os.path.join(STORE_DIR, "faiss.index")
DOC_MAPPING_PATH = os.path.join(STORE_DIR, "doc_mapping.pkl")
LEGACY_DOC_PATH = os.path.join(STORE_DIR, "documents.pkl")
MODEL_NAME = "all-MiniLM-L6-v2"


class RAGRetriever:
    _instance = None
    _instance_lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    logger.info("Initializing RAG Retriever...")
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        self._rw_lock = threading.RLock()
        self.index = self._load_faiss_index()
        self.documents = self._load_documents()
        self.model = self._load_embedding_model()

        if self.index.ntotal != len(self.documents):
            raise RuntimeError(
                f"FAISS index size ({self.index.ntotal}) != documents ({len(self.documents)}). "
                "Rebuild index or regenerate doc_mapping.pkl."
            )

        self._report_ids, self._report_doc_indices = self._build_report_registry_and_indices()
        logger.info("RAG Retriever ready | Vectors=%d", self.index.ntotal)

    def _load_faiss_index(self):
        if not os.path.exists(INDEX_PATH):
            raise FileNotFoundError(f"FAISS index missing: {INDEX_PATH}")
        return faiss.read_index(INDEX_PATH)

    def _load_documents(self):
        candidate_paths = []
        if os.path.exists(DOC_MAPPING_PATH):
            candidate_paths.append(DOC_MAPPING_PATH)
        if os.path.exists(LEGACY_DOC_PATH):
            candidate_paths.append(LEGACY_DOC_PATH)

        if not candidate_paths:
            raise FileNotFoundError("Document mapping file missing")

        last_error = None
        for path in candidate_paths:
            try:
                with open(path, "rb") as f:
                    docs = pickle.load(f)
                if not isinstance(docs, list):
                    raise RuntimeError("Document mapping must be a list.")
                if path != DOC_MAPPING_PATH:
                    logger.warning("Loaded documents from fallback mapping: %s", path)
                return docs
            except Exception as e:
                logger.warning("Failed to load mapping from %s: %s", path, e)
                last_error = e
                continue

        raise RuntimeError(f"Could not load document mapping from any source: {last_error}")

    def _load_embedding_model(self):
        return SentenceTransformer(MODEL_NAME)

    def _build_report_registry_and_indices(self) -> tuple[set[str], Dict[str, List[int]]]:
        report_ids: set[str] = set()
        report_doc_indices: Dict[str, List[int]] = {}
        for idx, doc in enumerate(self.documents):
            report_id = self._doc_report_id(doc)
            if not report_id:
                continue
            report_ids.add(report_id)
            report_doc_indices.setdefault(report_id, []).append(idx)
        return report_ids, report_doc_indices

    @staticmethod
    def _doc_report_id(doc: Any) -> Optional[str]:
        if not isinstance(doc, dict):
            return None
        metadata = doc.get("metadata")
        if isinstance(metadata, dict):
            value = metadata.get("report_id")
            if value:
                return str(value)
        return None

    @staticmethod
    def _doc_matches_report(doc: Any, report_id: str) -> bool:
        return RAGRetriever._doc_report_id(doc) == report_id

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        vectors = self.model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return vectors.astype("float32")

    def embed_query(self, query: str) -> np.ndarray:
        if not query or not isinstance(query, str):
            raise ValueError("Query must be a non-empty string")
        return self.embed_texts([query])

    def _format_results(self, indices: np.ndarray, distances: np.ndarray) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for idx, dist in zip(indices[0], distances[0]):
            if idx == -1:
                continue
            raw_doc = self.documents[idx]
            doc = raw_doc.copy() if isinstance(raw_doc, dict) else {"text": str(raw_doc)}
            doc["score"] = float(dist)
            results.append(doc)
        return results

    def _search_global(self, query_vec: np.ndarray, k: int) -> List[Dict[str, Any]]:
        if k <= 0 or self.index.ntotal == 0:
            return []
        search_k = min(k, self.index.ntotal)
        distances, indices = self.index.search(query_vec, search_k)
        return self._format_results(indices, distances)

    def _retrieve_report_only(self, query_vec: np.ndarray, report_id: str, k: int) -> List[Dict[str, Any]]:
        if k <= 0:
            return []

        doc_indices = self._report_doc_indices.get(report_id, [])
        if not doc_indices:
            return []

        q = query_vec[0]
        scored: List[tuple[float, Dict[str, Any]]] = []

        for idx in doc_indices:
            raw_doc = self.documents[idx]
            if not isinstance(raw_doc, dict):
                continue
            try:
                vec = self.index.reconstruct(int(idx)).astype("float32")
                score = float(np.sum((vec - q) ** 2))
            except Exception:
                score = 1e9
            doc = raw_doc.copy()
            doc["score"] = score
            scored.append((score, doc))

        scored.sort(key=lambda x: x[0])
        return [doc for _, doc in scored[:k]]

    def retrieve(
        self,
        query: str,
        k: int = 5,
        report_id: Optional[str] = None,
        strict_report: bool = False,
        retrieve_mode: str = "global",
        candidate_multiplier: int = 12,
    ) -> List[Dict[str, Any]]:
        try:
            if k <= 0:
                return []

            with self._rw_lock:
                if self.index.ntotal == 0:
                    return []

                query_vec = self.embed_query(query)

                mode = (retrieve_mode or "global").strip().lower()
                if strict_report:
                    mode = "report_only"
                if mode not in {"global", "report_only", "hybrid"}:
                    mode = "global"
                if not report_id:
                    mode = "global"

                if mode == "global":
                    return self._search_global(query_vec, k)

                if mode == "report_only":
                    return self._retrieve_report_only(query_vec, report_id=report_id, k=k)

                # hybrid: guaranteed report coverage + global coverage.
                report_k = max(1, int(round(k * 0.6)))
                global_k = max(0, k - report_k)

                report_results = self._retrieve_report_only(query_vec, report_id=report_id, k=report_k)
                candidate_k = min(max(max(global_k, 1) * candidate_multiplier, k), self.index.ntotal)
                global_candidates = self._search_global(query_vec, candidate_k)

                merged: List[Dict[str, Any]] = []
                seen = set()

                def _uid(doc: Dict[str, Any]) -> str:
                    meta = doc.get("metadata")
                    if isinstance(meta, dict) and "report_id" in meta and "chunk_id" in meta:
                        return f"{meta.get('report_id')}::{meta.get('chunk_id')}"
                    return str(doc.get("text", ""))[:256]

                for doc in report_results:
                    uid = _uid(doc)
                    if uid in seen:
                        continue
                    doc["retrieval_scope"] = "report"
                    merged.append(doc)
                    seen.add(uid)
                    if len(merged) >= k:
                        return merged

                for doc in global_candidates:
                    if self._doc_matches_report(doc, report_id):
                        continue
                    uid = _uid(doc)
                    if uid in seen:
                        continue
                    doc["retrieval_scope"] = "global"
                    merged.append(doc)
                    seen.add(uid)
                    if len(merged) >= k:
                        return merged

                if len(merged) < k:
                    top_up = self._retrieve_report_only(query_vec, report_id=report_id, k=k)
                    for doc in top_up:
                        uid = _uid(doc)
                        if uid in seen:
                            continue
                        doc["retrieval_scope"] = "report"
                        merged.append(doc)
                        seen.add(uid)
                        if len(merged) >= k:
                            break

                return merged

        except Exception as e:
            logger.exception("Retrieval failed")
            raise RuntimeError(f"Retrieval error: {e}")

    def _persist_locked(self):
        os.makedirs(STORE_DIR, exist_ok=True)
        tmp_index_path = f"{INDEX_PATH}.tmp"
        tmp_doc_path = f"{DOC_MAPPING_PATH}.tmp"

        faiss.write_index(self.index, tmp_index_path)
        with open(tmp_doc_path, "wb") as f:
            pickle.dump(self.documents, f)

        os.replace(tmp_index_path, INDEX_PATH)
        os.replace(tmp_doc_path, DOC_MAPPING_PATH)

    def add_documents(self, documents: List[Dict[str, Any]]) -> int:
        if not documents:
            return 0

        prepared_docs: List[Dict[str, Any]] = []
        for doc in documents:
            if not isinstance(doc, dict):
                continue
            text = str(doc.get("text", "")).strip()
            if not text:
                continue
            normalized = dict(doc)
            normalized["text"] = text
            prepared_docs.append(normalized)

        if not prepared_docs:
            return 0

        with self._rw_lock:
            embeddings = self.embed_texts([d["text"] for d in prepared_docs])
            if embeddings.shape[0] != len(prepared_docs):
                raise RuntimeError("Embedding count mismatch while adding documents.")

            if embeddings.shape[1] != self.index.d:
                raise RuntimeError(
                    f"Embedding dimension mismatch: vectors={embeddings.shape[1]}, index={self.index.d}"
                )

            start_idx = len(self.documents)
            self.index.add(embeddings)
            self.documents.extend(prepared_docs)

            if self.index.ntotal != len(self.documents):
                raise RuntimeError(
                    f"Post-update mismatch: index={self.index.ntotal}, docs={len(self.documents)}"
                )

            for offset, doc in enumerate(prepared_docs):
                report_id = self._doc_report_id(doc)
                if report_id:
                    self._report_ids.add(report_id)
                    self._report_doc_indices.setdefault(report_id, []).append(start_idx + offset)

            self._persist_locked()
            return len(prepared_docs)

    def has_report(self, report_id: str) -> bool:
        if not report_id:
            return False
        with self._rw_lock:
            return report_id in self._report_ids

    def report_chunk_count(self, report_id: str) -> int:
        if not report_id:
            return 0
        with self._rw_lock:
            return len(self._report_doc_indices.get(report_id, []))


_retriever: Optional[RAGRetriever] = None
_retriever_lock = threading.Lock()


def _get_retriever() -> RAGRetriever:
    global _retriever
    if _retriever is None:
        with _retriever_lock:
            if _retriever is None:
                _retriever = RAGRetriever()
    return _retriever


def retrieve_context(
    query: str,
    k: int = 5,
    report_id: Optional[str] = None,
    strict_report: bool = False,
    retrieve_mode: str = "global",
):
    return _get_retriever().retrieve(
        query,
        k=k,
        report_id=report_id,
        strict_report=strict_report,
        retrieve_mode=retrieve_mode,
    )


def add_documents_to_index(documents: List[Dict[str, Any]]) -> int:
    return _get_retriever().add_documents(documents)


def report_exists(report_id: str) -> bool:
    return _get_retriever().has_report(report_id)


def report_chunk_count(report_id: str) -> int:
    return _get_retriever().report_chunk_count(report_id)


