import os
import tempfile
import unittest

from src.core.schemas import IndexResult, MediaType
from src.services.video_service import video_service
from src.vector_db.qdrant_client import vector_db_client

class TestVideoVectors(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.video_path = os.path.join(self.tmp_dir.name, "test_video.mp4")
        with open(self.video_path, "wb") as f:
            f.write(b"dummy mp4 video bytes for temporal analysis test")

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_deep_video_analysis(self):
        res = video_service.process_video(self.video_path, extract_audio=True)
        self.assertIsNotNone(res.md5)
        self.assertTrue(res.duration_sec > 0)
        self.assertTrue(res.extracted_frames > 0)
        self.assertTrue(len(res.frame_descriptions) > 0)
        self.assertTrue(len(res.tags) > 0)
        self.assertIsNotNone(res.embedding)

    def test_video_search(self):
        # Insert target video item into vector DB
        target_video = IndexResult(
            item_id="target_video_1",
            media_type=MediaType.VIDEO,
            file_path=self.video_path,
            md5="vid_hash_1",
            title="测试自然纪录片",
            description="【视频全片剧情/镜头总结】 [05s] 高山湖泊画面 [10s] 雄鹰翱翔",
            content_vector=[0.2] * 2048
        )
        vector_db_client.upsert_item(target_video)

        hits = video_service.search_similar_videos(self.video_path, top_k=5)
        self.assertTrue(len(hits) > 0)

if __name__ == "__main__":
    unittest.main()
