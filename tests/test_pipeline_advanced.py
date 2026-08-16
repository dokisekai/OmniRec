import os
import tempfile
import unittest

from src.pipeline.ffmpeg_utils import ffmpeg_utils
from src.pipeline.vad_detector import vad_detector
from src.pipeline.tag_generator import tag_generator
from src.pipeline.batch_processor import batch_processor
from src.engine.cold_start import cold_start_strategy
from src.engine.feedback_loop import feedback_loop
from src.cache.degradation_manager import degradation_manager

class TestPipelineAdvanced(unittest.TestCase):

    def setUp(self):
        self.tmp_file = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        self.tmp_file.write(b"dummy mp4 data for ffmpeg test")
        self.tmp_file.close()

    def tearDown(self):
        if os.path.exists(self.tmp_file.name):
            os.unlink(self.tmp_file.name)

    def test_ffmpeg_utils(self):
        duration = ffmpeg_utils.get_video_duration(self.tmp_file.name)
        self.assertTrue(duration > 0)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            frames = ffmpeg_utils.extract_keyframes(self.tmp_file.name, tmpdir)
            self.assertTrue(len(frames) > 0)

    def test_vad_detector(self):
        segments = vad_detector.detect_speech_segments(self.tmp_file.name)
        self.assertTrue(len(segments) > 0)
        atype = vad_detector.classify_audio_type(self.tmp_file.name)
        self.assertIn(atype, ["voice", "music", "ambient"])

    def test_tag_generator(self):
        text = "这是一幅拍摄于高山湖泊边的人物肖像，具备极简风与治愈系色彩风格"
        cats = tag_generator.generate_categorized_tags(text)
        self.assertIn("Subject", cats)
        flat = tag_generator.flatten_tags(text)
        self.assertTrue(len(flat) > 0)

    def test_batch_processor(self):
        res = batch_processor.submit_online_task("task_001", lambda: "online_result")
        self.assertEqual(res, "online_result")

    def test_cold_start_and_feedback(self):
        recs = cold_start_strategy.get_fallback_recommendations(top_k=5)
        self.assertEqual(len(recs), 5)
        
        feedback_loop.record_impression("cold_start_1")
        feedback_loop.record_click("cold_start_1")
        ctr = feedback_loop.get_ctr("cold_start_1")
        self.assertEqual(ctr, 1.0)

    def test_degradation_manager(self):
        # Test primary execution
        res = degradation_manager.execute_with_fallback(
            "vlm",
            primary_fn=lambda: "vlm_ok",
            fallback_fn=lambda: "fallback_ok"
        )
        self.assertEqual(res, "vlm_ok")

if __name__ == "__main__":
    unittest.main()
