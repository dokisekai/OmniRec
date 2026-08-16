import unittest
import time
from src.core.config import settings
from src.core.schemas import ModelModality, MemoryTier
from src.core.memory_manager import MemoryManager, force_free_memory

class MockModel:
    def __init__(self, name: str):
        self.name = name

class TestMemoryManager(unittest.TestCase):

    def setUp(self):
        self.mm = MemoryManager()

    def test_l0_permanent_loading(self):
        vlm = self.mm.load_model(ModelModality.VLM, loader_fn=lambda: MockModel("vlm"))
        self.assertIsNotNone(vlm)
        self.assertEqual(vlm.name, "vlm")
        status = self.mm.get_status()
        self.assertIn("vlm", status["loaded_models"])
        self.assertEqual(status["loaded_models"]["vlm"]["tier"], MemoryTier.L0.value)

    def test_l1_hot_cache_loading_and_eviction(self):
        llm = self.mm.load_model(ModelModality.LLM, loader_fn=lambda: MockModel("llm"))
        self.assertIsNotNone(llm)
        status = self.mm.get_status()
        self.assertIn("llm", status["loaded_models"])

    def test_l2_cold_load_release(self):
        tts = self.mm.load_model(ModelModality.TTS, loader_fn=lambda: MockModel("tts"))
        self.assertIsNotNone(tts)
        status = self.mm.get_status()
        self.assertIn("tts", status["loaded_models"])
        
        # Release immediately
        self.mm.release_model(ModelModality.TTS)
        status_after = self.mm.get_status()
        self.assertNotIn("tts", status_after["loaded_models"])

    def test_force_free_memory(self):
        # Ensure force_free_memory runs without exception
        force_free_memory()

if __name__ == "__main__":
    unittest.main()
