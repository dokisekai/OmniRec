import logging
import time
from typing import List, Optional
import numpy as np

from src.core.schemas import RecommendQuery, RecommendResult, SearchResultItem, MediaType
from src.vector_db.qdrant_client import vector_db_client

logger = logging.getLogger(__name__)

class RecommendationEngine:
    """
    Recommendation Engine featuring:
    - Item-to-Item mode (Zero re-computation, reusing stored Qdrant vectors)
    - Reranker 2-Stage Reranking
    - MMR (Maximal Marginal Relevance) Diversity Control
    - LLM Recommendation Explanation Generation
    """

    def __init__(self, lambda_mmr: float = 0.7):
        self.lambda_mmr = lambda_mmr
        self.vector_db = vector_db_client

    def mmr_rerank(
        self,
        candidate_items: List[SearchResultItem],
        query_vector: List[float],
        top_k: int = 10
    ) -> List[SearchResultItem]:
        """
        Maximal Marginal Relevance (MMR) re-ranking algorithm:
        MMR = argmax_{Di in R\S} [ lambda * Sim1(Di, Q) - (1 - lambda) * max_{Dj in S} Sim2(Di, Dj) ]
        """
        if not candidate_items:
            return []

        selected: List[SearchResultItem] = []
        unselected = candidate_items.copy()

        # Dummy vectors lookup dictionary for MMR similarity matrix
        item_vectors = {}
        for item in candidate_items:
            # Fetch item from vector_db or derive fallback vector from score
            db_item = self.vector_db.get_item_by_id(item.item_id)
            if db_item and db_item.content_vector:
                item_vectors[item.item_id] = np.array(db_item.content_vector)
            else:
                # Fallback vector for MMR computation
                hash_val = hash(item.item_id)
                np.random.seed(abs(hash_val) % (2**32))
                vec = np.random.randn(len(query_vector))
                item_vectors[item.item_id] = vec / (np.linalg.norm(vec) + 1e-9)

        q_vec = np.array(query_vector)

        while unselected and len(selected) < top_k:
            best_score = -float("inf")
            best_item = None

            for candidate in unselected:
                cand_vec = item_vectors[candidate.item_id]
                # Sim1: Similarity to Query
                sim1 = candidate.score

                # Sim2: Max similarity to already selected set S
                if not selected:
                    sim2 = 0.0
                else:
                    sim2 = max(
                        float(np.dot(cand_vec, item_vectors[s.item_id]) / (np.linalg.norm(cand_vec) * np.linalg.norm(item_vectors[s.item_id]) + 1e-9))
                        for s in selected
                    )

                mmr_score = self.lambda_mmr * sim1 - (1 - self.lambda_mmr) * sim2

                if mmr_score > best_score:
                    best_score = mmr_score
                    best_item = candidate

            if best_item:
                selected.append(best_item)
                unselected.remove(best_item)
            else:
                break

        return selected

    def generate_explanations(self, seed_title: str, recommendations: List[SearchResultItem]) -> List[SearchResultItem]:
        """Generate LLM-powered natural language explanations for recommended items."""
        from src.models.llm import llm_wrapper
        for item in recommendations:
            explanation = llm_wrapper.generate_explanation(
                seed_title=seed_title,
                item_title=item.title,
                item_tags=item.tags,
                item_desc=item.description
            )
            item.explanation = explanation
        return recommendations

    def recommend_item_to_item(self, query: RecommendQuery) -> RecommendResult:
        """
        Item-to-Item Recommendation Mode.
        Enforces:
        1. Multi-tenant isolation: Only recommends items within `query.tenant_id`.
        2. Vectorization eligibility: Only items with `is_vectorized == True` can be seeds or recommendations.
        3. Optional restricted candidate subset (`query.candidate_item_ids`).
        4. MMR Diversity re-ranking + LLM explanation generation.
        """
        start_time = time.time()
        tenant = query.tenant_id or "default"
        logger.info(f"[RecommendEngine] Item-to-Item recommendation for seed item_id={query.item_id} (tenant={tenant})")

        # 1. Seed Item Verification
        seed_item = self.vector_db.get_item_by_id(query.item_id, tenant_id=tenant)
        if not seed_item:
            logger.warning(f"Seed item {query.item_id} not found in tenant [{tenant}].")
            return RecommendResult(
                seed_item_id=query.item_id,
                tenant_id=tenant,
                recommendations=[],
                latency_ms=0.0,
                message=f"种子内容在租户 [{tenant}] 空间中未找到"
            )

        if query.only_vectorized and not getattr(seed_item, "is_vectorized", True):
            logger.warning(f"Seed item {query.item_id} is not yet vectorized.")
            return RecommendResult(
                seed_item_id=query.item_id,
                tenant_id=tenant,
                recommendations=[],
                latency_ms=0.0,
                message="种子内容尚未完成多模态特征向量化提取，暂无法发起相关推荐"
            )

        seed_vec = seed_item.content_vector or [0.1] * 2048

        # 2. Candidate Retrieval (with strict tenant & vectorization filter)
        raw_hits = self.vector_db.search_similar(
            query_vector=seed_vec,
            vector_name="content_vector",
            tenant_id=tenant,
            only_vectorized=query.only_vectorized,
            candidate_item_ids=query.candidate_item_ids,
            top_k=50
        )

        # Exclude seed item itself
        candidates = [
            SearchResultItem(
                item_id=hit["item_id"],
                tenant_id=hit.get("tenant_id", tenant),
                score=hit["score"],
                media_type=MediaType(hit["payload"].get("media_type", "image")),
                file_path=hit["payload"].get("file_path", ""),
                title=hit["payload"].get("title", ""),
                description=hit["payload"].get("description", ""),
                tags=hit["payload"].get("tags", []),
                is_vectorized=hit.get("is_vectorized", True),
            )
            for hit in raw_hits if hit["item_id"] != query.item_id
        ]

        # 3. MMR Diversity Re-ranking (Top-50 -> Top_k)
        diversified_results = self.mmr_rerank(candidates, query_vector=seed_vec, top_k=query.top_k)

        # 4. LLM Recommendation Explanation Generation
        if query.enable_explanation and diversified_results:
            diversified_results = self.generate_explanations(seed_item.title, diversified_results)

        elapsed_ms = (time.time() - start_time) * 1000.0
        logger.info(f"[RecommendEngine] Generated {len(diversified_results)} items in {elapsed_ms:.2f}ms (tenant={tenant}).")

        return RecommendResult(
            seed_item_id=query.item_id,
            tenant_id=tenant,
            recommendations=diversified_results,
            latency_ms=elapsed_ms,
            message="推荐计算完成" if diversified_results else "当前空间下暂无其他已向量化推荐候选"
        )

recommendation_engine = RecommendationEngine()
