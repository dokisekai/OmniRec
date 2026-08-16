import unittest
from src.core.schemas import IndexResult, MediaType, RecommendQuery, SearchQuery
from src.engine.retrieval_engine import RetrievalEngine, retrieval_engine
from src.engine.recommendation_engine import RecommendationEngine, recommendation_engine
from src.vector_db.qdrant_client import vector_db_client

class TestEngines(unittest.TestCase):

    def setUp(self):
        # Insert 3 test items into vector database
        for i in range(1, 4):
            item = IndexResult(
                item_id=f"test_rec_{i}",
                media_type=MediaType.IMAGE if i % 2 == 1 else MediaType.VIDEO,
                file_path=f"/path/to/media_{i}.jpg",
                md5=f"hash_{i}",
                title=f"测试媒体内容 {i}",
                description=f"关于自然与城市的描述 {i}",
                tags=["风景", "城市"] if i == 1 else ["动漫", "人物"],
                content_vector=[0.1 * i] * 2048
            )
            vector_db_client.upsert_item(item)

    def test_rrf_fusion(self):
        rank_list1 = [
            {"item_id": "test_rec_1", "score": 0.9, "payload": {"media_type": "image", "title": "A"}},
            {"item_id": "test_rec_2", "score": 0.8, "payload": {"media_type": "video", "title": "B"}},
        ]
        rank_list2 = [
            {"item_id": "test_rec_2", "score": 0.95, "payload": {"media_type": "video", "title": "B"}},
            {"item_id": "test_rec_1", "score": 0.85, "payload": {"media_type": "image", "title": "A"}},
        ]
        fused = RetrievalEngine.calculate_rrf([rank_list1, rank_list2], k=60)
        self.assertEqual(len(fused), 2)
        # Check that score is computed properly
        self.assertTrue(fused[0]["score"] > 0)

    def test_search_retrieval(self):
        query = SearchQuery(query_text="城市风景", top_k=5)
        res = retrieval_engine.search(query)
        self.assertIsNotNone(res)
        self.assertTrue(len(res.results) > 0)

    def test_recommendation_item_to_item(self):
        query = RecommendQuery(item_id="test_rec_1", top_k=2, enable_explanation=True)
        res = recommendation_engine.recommend_item_to_item(query)
        self.assertEqual(res.seed_item_id, "test_rec_1")
        self.assertTrue(len(res.recommendations) > 0)
        self.assertIsNotNone(res.recommendations[0].explanation)

if __name__ == "__main__":
    unittest.main()
