import math
from typing import Dict, List, Set

class EvaluationMetrics:
    """
    Offline Recommendation Evaluation Metrics (09-部署运维与评估.md 第3节).
    Calculates NDCG@K, Recall@K, Precision@K, and Intra-List Diversity (ILD).
    """

    @staticmethod
    def calculate_precision_at_k(recommended: List[str], ground_truth: Set[str], k: int) -> float:
        """Precision@K = |Recommended@K intersect GroundTruth| / K"""
        rec_k = recommended[:k]
        if not rec_k:
            return 0.0
        hits = sum(1 for item in rec_k if item in ground_truth)
        return hits / float(k)

    @staticmethod
    def calculate_recall_at_k(recommended: List[str], ground_truth: Set[str], k: int) -> float:
        """Recall@K = |Recommended@K intersect GroundTruth| / |GroundTruth|"""
        if not ground_truth:
            return 0.0
        rec_k = recommended[:k]
        hits = sum(1 for item in rec_k if item in ground_truth)
        return hits / float(len(ground_truth))

    @staticmethod
    def calculate_ndcg_at_k(recommended: List[str], ground_truth: Set[str], k: int) -> float:
        """Normalized Discounted Cumulative Gain at K (NDCG@K)."""
        rec_k = recommended[:k]
        dcg = 0.0
        for i, item in enumerate(rec_k, start=1):
            if item in ground_truth:
                dcg += 1.0 / math.log2(i + 1)
        
        # Ideal DCG (IDCG)
        idcg = sum(1.0 / math.log2(i + 1) for i in range(1, min(len(ground_truth), k) + 1))
        if idcg == 0.0:
            return 0.0
        return dcg / idcg

    @staticmethod
    def calculate_diversity_score(tags_per_item: List[List[str]]) -> float:
        """Calculate Intra-List Diversity (ILD) score based on tag Jaccard distance across item pairs."""
        if len(tags_per_item) <= 1:
            return 1.0

        distances = []
        for i in range(len(tags_per_item)):
            for j in range(i + 1, len(tags_per_item)):
                set_i = set(tags_per_item[i])
                set_j = set(tags_per_item[j])
                union_len = len(set_i.union(set_j))
                if union_len == 0:
                    dist = 1.0
                else:
                    jaccard_sim = len(set_i.intersection(set_j)) / float(union_len)
                    dist = 1.0 - jaccard_sim
                distances.append(dist)

        return sum(distances) / len(distances) if distances else 1.0

evaluation_metrics = EvaluationMetrics()
