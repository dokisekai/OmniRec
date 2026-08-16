"""
Evaluation package: Offline recommendation metrics (NDCG@K, Recall@K, Precision@K, Diversity Score).
"""
from src.evaluation.metrics import EvaluationMetrics, evaluation_metrics

__all__ = ["EvaluationMetrics", "evaluation_metrics"]
