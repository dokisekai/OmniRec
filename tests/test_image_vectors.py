import os
import tempfile
import unittest
from PIL import Image

from src.core.schemas import IndexResult, MediaType
from src.services.image_service import image_service
from src.vector_db.qdrant_client import vector_db_client

class TestImageVectors(unittest.TestCase):

    def setUp(self):
        # Create a real 100x100 JPEG image for PIL testing
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.img_path = os.path.join(self.tmp_dir.name, "test_landscape.jpg")
        img = Image.new("RGB", (100, 100), color=(44, 62, 80))
        img.save(self.img_path, format="JPEG")

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_visual_feature_vector(self):
        vec = image_service.extract_visual_feature_vector(self.img_path, dim=2048)
        self.assertEqual(len(vec), 2048)

    def test_dominant_colors(self):
        colors = image_service.extract_dominant_colors(self.img_path, num_colors=3)
        self.assertTrue(len(colors) > 0)
        self.assertTrue(colors[0].startswith("#"))

    def test_deep_image_analysis(self):
        result = image_service.process_image(self.img_path)
        self.assertIsNotNone(result.md5)
        self.assertTrue(len(result.description) > 0)
        self.assertTrue(len(result.tags) > 0)

    def test_dual_track_image_search(self):
        # Insert target item into vector DB
        target_item = IndexResult(
            item_id="target_image_1",
            media_type=MediaType.IMAGE,
            file_path=self.img_path,
            md5="img_hash_1",
            title="高山湖泊风景",
            description="一片被雪山围绕的深蓝色湖泊，天空晴朗",
            content_vector=[0.15] * 2048,
            thumbnail_vector=[0.12] * 2048
        )
        vector_db_client.upsert_item(target_item)

        search_hits = image_service.search_similar_images(
            image_path=self.img_path,
            visual_weight=0.4,
            semantic_weight=0.6,
            top_k=5
        )
        self.assertTrue(len(search_hits) > 0)

if __name__ == "__main__":
    unittest.main()
