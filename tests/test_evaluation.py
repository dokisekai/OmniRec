import unittest
from src.evaluation.metrics import evaluation_metrics

class TestEvaluationMetrics(unittest.TestCase):

    def test_precision_and_recall(self):
        recommended = ["item_1", "item_2", "item_3", "item_4", "item_5"]
        ground_truth = {"item_1", "item_3", "item_7"}

        prec = evaluation_metrics.calculate_precision_at_k(recommended, ground_truth, k=5)
        self.assertEqual(prec, 2.0 / 5.0)

        rec = evaluation_metrics.calculate_recall_at_k(recommended, ground_truth, k=5)
        self.assertEqual(rec, 2.0 / 3.0)

    def test_ndcg(self):
        recommended = ["item_1", "item_2", "item_3"]
        ground_truth = {"item_1", "item_3"}

        ndcg = evaluation_metrics.calculate_ndcg_at_k(recommended, ground_truth, k=3)
        self.assertTrue(ndcg > 0.0 and ndcg <= 1.0)

    def test_diversity_score(self):
        tags_list = [
            ["自然风光", "高山湖泊"],
            ["城市夜景", "建筑"],
            ["二次元", "动漫插画"]
        ]
        div_score = evaluation_metrics.calculate_diversity_score(tags_list)
        self.assertEqual(div_score, 1.0)  # All disjoint sets = 1.0 diversity

if __name__ == "__main__":
    unittest.main()
