import logging
import time
from typing import Any, Dict, List, Optional

from src.core.schemas import MediaType, SearchQuery, SearchResult, SearchResultItem
from src.services.image_service import image_service
from src.services.audio_service import audio_service
from src.services.text_service import text_service
from src.vector_db.qdrant_client import vector_db_client

logger = logging.getLogger(__name__)


class RetrievalEngine:
    """
    Multi-channel Retrieval Engine with:
    - Reciprocal Rank Fusion (RRF) across text / image / audio channels
    - Optional Qwen3-VL-Reranker 2-stage precision reranking
    """

    def __init__(self, k_rrf: int = 60):
        self.k_rrf = k_rrf
        self.vector_db = vector_db_client
        self._reranker = None   # Lazy-loaded to avoid circular imports

    def _get_reranker(self):
        if self._reranker is None:
            try:
                from src.models.reranker import reranker_wrapper
                self._reranker = reranker_wrapper
            except Exception as e:
                logger.warning(f"[RetrievalEngine] Reranker unavailable: {e}")
                self._reranker = None
        return self._reranker

    # ------------------------------------------------------------------
    # RRF fusion
    # ------------------------------------------------------------------

    @staticmethod
    def calculate_rrf(
        rank_lists: List[List[Dict[str, Any]]],
        k: int = 60,
    ) -> List[Dict[str, Any]]:
        """
        Reciprocal Rank Fusion:  RRF(d) = Σ 1 / (k + rank_m(d))
        """
        scores: Dict[str, float] = {}
        payloads: Dict[str, Dict[str, Any]] = {}

        for rank_list in rank_lists:
            for rank_idx, hit in enumerate(rank_list, start=1):
                iid = hit["item_id"]
                payloads[iid] = hit["payload"]
                scores[iid] = scores.get(iid, 0.0) + 1.0 / (k + rank_idx)

        return [
            {"item_id": iid, "score": score, "payload": payloads[iid]}
            for iid, score in sorted(scores.items(), key=lambda x: x[1], reverse=True)
        ]

    # ------------------------------------------------------------------
    # Main search
    # ------------------------------------------------------------------

    def search(self, query: SearchQuery) -> SearchResult:
        start_time = time.time()
        logger.info("[RetrievalEngine] Search started...")

        rank_lists: List[List[Dict[str, Any]]] = []
        fetch_k = query.top_k * 5   # Over-fetch for reranker

        # --- Channel 1: Text query → content_vector ---
        if query.query_text:
            text_vec = text_service.process_text(query.query_text)
            if text_vec:
                hits = self.vector_db.search_similar(
                    query_vector=text_vec,
                    vector_name="content_vector",
                    tenant_id=query.tenant_id,
                    only_vectorized=query.only_vectorized,
                    filter_tags=query.filter_tags,
                    filter_media_type=(
                        query.filter_media_type.value if query.filter_media_type else None
                    ),
                    top_k=fetch_k,
                )
                rank_lists.append(hits)

        # --- Channel 2: Image query → thumbnail_vector ---
        if query.query_image_path:
            img_res = image_service.process_image(query.query_image_path)
            if img_res.embedding:
                hits = self.vector_db.search_similar(
                    query_vector=img_res.embedding,
                    vector_name="thumbnail_vector",
                    tenant_id=query.tenant_id,
                    only_vectorized=query.only_vectorized,
                    filter_tags=query.filter_tags,
                    filter_media_type=(
                        query.filter_media_type.value if query.filter_media_type else None
                    ),
                    top_k=fetch_k,
                )
                rank_lists.append(hits)

        # --- Channel 3: Audio query → audio_vector ---
        if query.query_audio_path:
            audio_res = audio_service.process_audio(query.query_audio_path)
            audio_vec = audio_res.clap_embedding or audio_res.embedding
            if audio_vec:
                hits = self.vector_db.search_similar(
                    query_vector=audio_vec,
                    vector_name="audio_vector",
                    tenant_id=query.tenant_id,
                    only_vectorized=query.only_vectorized,
                    filter_tags=query.filter_tags,
                    filter_media_type=(
                        query.filter_media_type.value if query.filter_media_type else None
                    ),
                    top_k=fetch_k,
                )
                rank_lists.append(hits)

        # --- Fallback: browse all with dummy vector ---
        if not rank_lists:
            dummy_vec = [0.01] * 2048
            hits = self.vector_db.search_similar(
                query_vector=dummy_vec,
                tenant_id=query.tenant_id,
                only_vectorized=query.only_vectorized,
                filter_tags=query.filter_tags,
                filter_media_type=(
                    query.filter_media_type.value if query.filter_media_type else None
                ),
                top_k=fetch_k,
            )
            rank_lists.append(hits)

        # --- RRF Fusion ---
        fused = self.calculate_rrf(rank_lists, k=self.k_rrf)

        # --- Stage 2: Reranker (optional) ---
        if query.enable_rerank and query.query_text and len(fused) > 0:
            fused = self._apply_reranker(query.query_text, fused, query.top_k)
        else:
            fused = fused[: query.top_k]

        # --- Build response items ---
        search_items = [
            SearchResultItem(
                item_id=h["item_id"],
                tenant_id=h.get("tenant_id", query.tenant_id),
                score=h["score"],
                media_type=MediaType(h["payload"].get("media_type", "image")),
                file_path=h["payload"].get("file_path", ""),
                title=h["payload"].get("title", ""),
                description=h["payload"].get("description", ""),
                tags=h["payload"].get("tags", []),
                is_vectorized=h.get("is_vectorized", True),
                explanation=h.get("explanation"),
            )
            for h in fused
        ]

        elapsed_ms = (time.time() - start_time) * 1000.0
        logger.info(
            f"[RetrievalEngine] Done: {len(search_items)} results in {elapsed_ms:.1f}ms"
        )
        return SearchResult(
            query=query,
            results=search_items,
            total=len(search_items),
            latency_ms=elapsed_ms,
        )

    # ------------------------------------------------------------------
    # Reranker integration
    # ------------------------------------------------------------------

    def _apply_reranker(
        self,
        query_text: str,
        fused: List[Dict[str, Any]],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        reranker = self._get_reranker()
        if reranker is None:
            return fused[:top_k]

        # Prepare flat candidate list for reranker
        candidates = [
            {
                "item_id": h["item_id"],
                "score": h["score"],
                "description": h["payload"].get("description", ""),
                "tags": h["payload"].get("tags", []),
                "file_path": h["payload"].get("file_path", ""),
                "media_type": h["payload"].get("media_type", ""),
                **h,          # keep payload for later
            }
            for h in fused
        ]

        reranked = reranker.rerank(
            query_text=query_text,
            candidates=candidates,
            top_k=top_k,
        )

        # Merge rerank_score back into hit dicts
        result = []
        for r in reranked:
            # Restore payload structure
            hit = {
                "item_id": r["item_id"],
                "score": r["score"],
                "rerank_score": r.get("rerank_score", r["score"]),
                "original_score": r.get("original_score", r["score"]),
                "payload": r.get("payload", {
                    "media_type": r.get("media_type", "image"),
                    "file_path": r.get("file_path", ""),
                    "title": r.get("title", ""),
                    "description": r.get("description", ""),
                    "tags": r.get("tags", []),
                }),
            }
            result.append(hit)

        logger.info(
            f"[RetrievalEngine] Reranker: {len(fused)} → {len(result)} results "
            f"(backend: {getattr(reranker, '_backend', 'unknown')})"
        )
        return result


retrieval_engine = RetrievalEngine()
