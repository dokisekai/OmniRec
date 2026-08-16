import os
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
from fastapi.testclient import TestClient
from src.api.server import app
from src.core.schemas import IndexResult, MediaType

class TestAPIEndpoints(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.img_path = os.path.join(self.tmp_dir.name, "test_api_img.jpg")
        img = Image.new("RGB", (64, 64), color=(100, 150, 200))
        img.save(self.img_path, format="JPEG")

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_health_check(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "healthy")

    def test_root_dashboard(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Antigravity Multimodal", resp.text)

    def test_search_endpoint(self):
        payload = {
            "query_text": "自然风光高山湖泊",
            "top_k": 5
        }
        resp = self.client.post("/api/v1/search", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("results", data)

    @patch("src.pipeline.progressive_indexer.ProgressiveIndexer.index_file")
    def test_index_endpoint(self, mock_index):
        mock_index.return_value = IndexResult(
            item_id="item_test_123",
            media_type=MediaType.IMAGE,
            file_path=self.img_path,
            md5="hash_123",
            title="test.jpg"
        )
        resp = self.client.post("/api/v1/index", params={"file_path": self.img_path, "media_type": "image"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["item_id"], "item_test_123")

    def test_recommend_endpoint(self):
        payload = {
            "item_id": "seed_item_1",
            "top_k": 3
        }
        resp = self.client.post("/api/v1/recommend", json=payload)
        self.assertEqual(resp.status_code, 200)

if __name__ == "__main__":
    unittest.main()
