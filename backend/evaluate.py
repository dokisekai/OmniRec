import logging
import time
from typing import Dict, List, Set

from src.core.schemas import MediaType, RecommendQuery, SearchQuery
from src.engine.recommendation_engine import recommendation_engine
from src.engine.retrieval_engine import retrieval_engine
from src.evaluation.metrics import evaluation_metrics
from src.pipeline.progressive_indexer import progressive_indexer
from src.vector_db.qdrant_client import vector_db_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("evaluate")

def run_offline_evaluation():
    logger.info("==================================================")
    logger.info("Running Offline Recommendation & Retrieval Evaluation (09 篇规约)")
    logger.info("==================================================")

    # 1. Prepare benchmark items
    benchmark_items = [
        {"file_path": "./cache/eval_item_1.jpg", "type": MediaType.IMAGE, "tags": ["自然", "风景", "高山湖泊"]},
        {"file_path": "./cache/eval_item_2.mp4", "type": MediaType.VIDEO, "tags": ["城市", "建筑", "夜景"]},
        {"file_path": "./cache/eval_item_3.wav", "type": MediaType.AUDIO, "tags": ["语音", "访谈", "治愈系"]},
        {"file_path": "./cache/eval_item_4.jpg", "type": MediaType.IMAGE, "tags": ["自然", "森林", "极简风"]},
        {"file_path": "./cache/eval_item_5.mp4", "type": MediaType.VIDEO, "tags": ["二次元", "动漫", "插画"]},
    ]

    indexed_ids = []
    for item in benchmark_items:
        # Create dummy file if needed for indexing
        import os
        os.makedirs(os.path.dirname(item["file_path"]), exist_ok=True)
        if not os.path.exists(item["file_path"]):
            with open(item["file_path"], "wb") as f:
                f.write(b"dummy benchmark file data")
        
        idx_res = progressive_indexer.index_file(item["file_path"], item["type"])
        indexed_ids.append(idx_res.item_id)

    logger.info(f"Indexed {len(indexed_ids)} benchmark items into vector store.")

    # 2. Evaluate Search Retrieval (NDCG@K, Recall@K, Precision@K)
    ground_truth_set = set(indexed_ids[:3])
    search_query = SearchQuery(query_text="自然与风景", top_k=5)
    search_res = retrieval_engine.search(search_query)
    retrieved_ids = [r.item_id for r in search_res.results]

    p5 = evaluation_metrics.calculate_precision_at_k(retrieved_ids, ground_truth_set, k=5)
    r5 = evaluation_metrics.calculate_recall_at_k(retrieved_ids, ground_truth_set, k=5)
    ndcg5 = evaluation_metrics.calculate_ndcg_at_k(retrieved_ids, ground_truth_set, k=5)

    # 3. Evaluate Item-to-Item Recommendation & Diversity (ILD Score)
    rec_query = RecommendQuery(item_id=indexed_ids[0], top_k=5, enable_explanation=True)
    rec_res = recommendation_engine.recommend_item_to_item(rec_query)
    recommended_tags = [r.tags for r in rec_res.recommendations]
    diversity_score = evaluation_metrics.calculate_diversity_score(recommended_tags)

    # 4. Generate Report
    logger.info("\n--- Offline Evaluation Metrics Benchmark ---")
    logger.info(f"Precision@5:     {p5 * 100:.2f}%")
    logger.info(f"Recall@5:        {r5 * 100:.2f}%")
    logger.info(f"NDCG@5:          {ndcg5:.4f}")
    logger.info(f"Diversity (ILD): {diversity_score:.4f} (1.0 = Max Diversity)")
    logger.info("==================================================")
    logger.info("Offline Evaluation Completed Successfully.")

if __name__ == "__main__":
    run_offline_evaluation()
