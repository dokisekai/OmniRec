import os
import tempfile
import unittest

from src.services.image_service import image_service
from src.services.video_service import video_service
from src.services.audio_service import audio_service
from src.services.text_service import text_service

class TestServices(unittest.TestCase):

    def setUp(self):
        # Create temporary dummy file for testing
        self.tmp_file = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        self.tmp_file.write(b"dummy image data for md5 hash testing")
        self.tmp_file.close()

    def tearDown(self):
        if os.path.exists(self.tmp_file.name):
            os.unlink(self.tmp_file.name)

    def test_image_service(self):
        res = image_service.process_image(self.tmp_file.name)
        self.assertIsNotNone(res.md5)
        self.assertEqual(res.image_path, self.tmp_file.name)
        self.assertTrue(len(res.tags) > 0)
        self.assertIsNotNone(res.embedding)

    def test_audio_service(self):
        res = audio_service.process_audio(self.tmp_file.name)
        self.assertIsNotNone(res.md5)
        self.assertEqual(res.audio_path, self.tmp_file.name)
        self.assertIsNotNone(res.embedding)

    def test_video_service(self):
        res = video_service.process_video(self.tmp_file.name)
        self.assertIsNotNone(res.md5)
        self.assertEqual(res.video_path, self.tmp_file.name)
        self.assertIsNotNone(res.embedding)

    def test_text_service(self):
        vec = text_service.process_text("测试多模态向量推荐服务")
        self.assertTrue(len(vec) > 0)
        tags = text_service.extract_tags("这是一个包含视频和图片信息的推荐请求")
        self.assertIn("视频", tags)
        self.assertIn("视觉", tags)

if __name__ == "__main__":
    unittest.main()
