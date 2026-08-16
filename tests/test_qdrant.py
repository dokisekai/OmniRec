import unittest
from src.core.schemas import IndexResult, MediaType
from src.vector_db.qdrant_client import VectorDBClient

class TestQdrantClient(unittest.TestCase):

    def setUp(self):
        self.vdb = VectorDBClient()
        self.test_item = IndexResult(
            item_id="test_item_001",
            media_type=MediaType.IMAGE,
            file_path="/path/to/test.jpg",
            md5="d41d8cd98f00b204e9800998ecf8427e",
            title="测试自然风光",
            description="一片风景优美的原野与高山湖泊",
            tags=["自然", "风景", "湖泊"],
            content_vector=[0.1] * 2048,
            audio_vector=[0.05] * 512,
            thumbnail_vector=[0.1] * 2048
        )

    def test_upsert_and_retrieve(self):
        success = self.vdb.upsert_item(self.test_item)
        self.assertTrue(success)
        
        retrieved = self.vdb.get_item_by_id("test_item_001")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.title, "测试自然风光")

    def test_search_similar(self):
        self.vdb.upsert_item(self.test_item)
        query_vec = [0.1] * 2048
        hits = self.vdb.search_similar(query_vec, top_k=5)
        self.assertTrue(len(hits) > 0)
        self.assertEqual(hits[0]["item_id"], "test_item_001")

if __name__ == "__main__":
    unittest.main()
