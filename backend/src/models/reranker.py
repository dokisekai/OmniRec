import logging
import os
import sys
import threading
from typing import List, Optional, Tuple

import numpy as np

from src.models.base import BaseModelWrapper
from src.core.config import find_reranker_model_path

logger = logging.getLogger(__name__)


class RerankerWrapper(BaseModelWrapper):
    """
    [Node 2.4.1] Qwen3-VL-Reranker-2B — Multimodal Cross-Encoder Reranker.

    Scores (query, document) pairs using the official binary linear head
    from the model's own scripts/qwen3_vl_reranker.py.  Falls back to
    cosine-score pass-through when the model cannot be loaded.

    Memory: ~2.0 GB (bfloat16 on CPU/MPS).
    """

    _DEFAULT_INSTRUCTION = (
        "Given a search query, determine whether the document is relevant "
        "to the query. Answer 'yes' if relevant, 'no' if not."
    )

    def __init__(self, model_id: Optional[str] = None):
        resolved = model_id or find_reranker_model_path()
        super().__init__(resolved, estimated_memory_gb=2.0)
        self._reranker = None          # Qwen3VLReranker instance from scripts/
        self._backend: str = "none"    # "qwen3vl" | "cosine_fallback"
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def load(self):
        if self._is_loaded:
            return
        logger.info(f"[RerankerWrapper] Loading model from: {self.model_id}")
        self._try_load_qwen3vl_reranker()
        if self._backend == "none":
            logger.warning(
                "[RerankerWrapper] Real reranker unavailable. "
                "Using cosine-score pass-through fallback."
            )
            self._backend = "cosine_fallback"
        self._is_loaded = True
        logger.info(f"[RerankerWrapper] Backend: {self._backend}")

    def _try_load_qwen3vl_reranker(self):
        """Load Qwen3VLReranker from the bundled scripts/ directory."""
        scripts_dir = os.path.join(self.model_id, "scripts")
        script_file = os.path.join(scripts_dir, "qwen3_vl_reranker.py")
        if not os.path.exists(script_file):
            logger.debug(f"[RerankerWrapper] Script not found at {script_file}")
            return
        try:
            # Add scripts dir to path so the script can import its deps
            if scripts_dir not in sys.path:
                sys.path.insert(0, scripts_dir)

            import importlib.util
            spec = importlib.util.spec_from_file_location("qwen3_vl_reranker", script_file)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

            Qwen3VLReranker = mod.Qwen3VLReranker
            self._reranker = Qwen3VLReranker(
                model_name_or_path=self.model_id,
                max_length=2048,
            )
            self._backend = "qwen3vl"
            logger.info("[RerankerWrapper] ✅ Qwen3-VL-Reranker loaded successfully.")
        except Exception as e:
            logger.warning(f"[RerankerWrapper] Qwen3-VL-Reranker load failed: {e}")

    def unload(self):
        self._reranker = None
        self._backend = "none"
        self._is_loaded = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def rerank(
        self,
        query_text: str,
        candidates: List[dict],
        top_k: int = 10,
        query_image: Optional[str] = None,
    ) -> List[dict]:
        """
        Rerank candidate documents against a query.

        Args:
            query_text:   Natural language query string.
            candidates:   List of dicts with at least {"item_id", "score",
                          "description", "file_path", "tags", ...}.
            top_k:        Number of results to return.
            query_image:  Optional path to a query image for multimodal reranking.

        Returns:
            Reranked list (up to top_k), each dict augmented with
            "rerank_score" and "original_score".
        """
        if not self._is_loaded:
            self.load()
        if not candidates:
            return []

        with self._lock:
            if self._backend == "qwen3vl":
                return self._rerank_qwen3vl(query_text, candidates, top_k, query_image)
            else:
                return self._rerank_cosine_fallback(query_text, candidates, top_k)

    def compute_score(
        self,
        query_text: str,
        doc_text: str,
        query_image: Optional[str] = None,
        doc_image: Optional[str] = None,
    ) -> float:
        """Score a single (query, document) pair. Returns 0–1 relevance score."""
        if not self._is_loaded:
            self.load()
        with self._lock:
            if self._backend == "qwen3vl" and self._reranker is not None:
                try:
                    scores = self._reranker.process({
                        "instruction": self._DEFAULT_INSTRUCTION,
                        "query": {"text": query_text, "image": query_image},
                        "documents": [{"text": doc_text, "image": doc_image}],
                    })
                    return float(scores[0]) if scores else 0.5
                except Exception as e:
                    logger.error(f"[RerankerWrapper] compute_score error: {e}")
                    return 0.5
            return self._cosine_text_sim(query_text, doc_text)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _rerank_qwen3vl(
        self,
        query_text: str,
        candidates: List[dict],
        top_k: int,
        query_image: Optional[str],
    ) -> List[dict]:
        try:
            documents = [
                {
                    "text": c.get("description", "") or " ".join(c.get("tags", [])),
                    "image": c.get("file_path") if c.get("media_type") == "image" else None,
                }
                for c in candidates
            ]
            scores = self._reranker.process({
                "instruction": self._DEFAULT_INSTRUCTION,
                "query": {"text": query_text, "image": query_image},
                "documents": documents,
            })
            annotated = []
            for cand, score in zip(candidates, scores):
                item = dict(cand)
                item["original_score"] = item.get("score", 0.0)
                item["rerank_score"] = float(score)
                item["score"] = float(score)
                annotated.append(item)

            annotated.sort(key=lambda x: x["rerank_score"], reverse=True)
            logger.info(f"[RerankerWrapper] Reranked {len(annotated)} → top-{top_k} via Qwen3-VL.")
            return annotated[:top_k]
        except Exception as e:
            logger.error(f"[RerankerWrapper] Qwen3-VL rerank error: {e}. Falling back.")
            return self._rerank_cosine_fallback(query_text, candidates, top_k)

    def _rerank_cosine_fallback(
        self,
        query_text: str,
        candidates: List[dict],
        top_k: int,
    ) -> List[dict]:
        """Re-score using simple TF-IDF-style character n-gram overlap."""
        annotated = []
        q_chars = set(query_text.lower())
        for cand in candidates:
            doc = (cand.get("description", "") + " " + " ".join(cand.get("tags", []))).lower()
            doc_chars = set(doc)
            overlap = len(q_chars & doc_chars) / (len(q_chars | doc_chars) + 1e-9)
            item = dict(cand)
            item["original_score"] = item.get("score", 0.0)
            item["rerank_score"] = float(overlap)
            # Blend: 70% original score + 30% text overlap
            item["score"] = 0.7 * item["original_score"] + 0.3 * item["rerank_score"]
            annotated.append(item)

        annotated.sort(key=lambda x: x["score"], reverse=True)
        return annotated[:top_k]

    @staticmethod
    def _cosine_text_sim(a: str, b: str) -> float:
        """Character-level jaccard similarity as cosine proxy."""
        sa, sb = set(a.lower()), set(b.lower())
        return len(sa & sb) / (len(sa | sb) + 1e-9)

    def predict(self, *args, **kwargs):
        """Alias for BaseModelWrapper compatibility."""
        return self.rerank(*args, **kwargs)


reranker_wrapper = RerankerWrapper()
