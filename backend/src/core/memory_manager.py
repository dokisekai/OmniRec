import gc
import logging
import threading
import time
from typing import Any, Callable, Dict, Optional

from src.core.config import settings
from src.core.schemas import MemoryTier, ModelModality

logger = logging.getLogger(__name__)

def force_free_memory():
    """
    [Node 1.3.2] PyTorch MPS Safe Memory Purge.
    Runs garbage collection and flushes PyTorch MPS cache if tensors were allocated on GPU.
    """
    gc.collect()
    try:
        import torch
        if hasattr(torch, "mps") and hasattr(torch.mps, "empty_cache"):
            if hasattr(torch, "backends") and hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                try:
                    if hasattr(torch.mps, "current_allocated_memory") and torch.mps.current_allocated_memory() > 0:
                        torch.mps.empty_cache()
                        logger.debug("PyTorch MPS memory cache flushed successfully.")
                except Exception:
                    pass
    except Exception as e:
        logger.debug(f"PyTorch MPS empty_cache skipped: {e}")

class MemoryManager:
    """
    [Node 1.3.1 & 1.3.2] Three-tier Memory Manager for Apple Silicon Unified Memory (24GB).
    - L0 Permanent (VLM + Embedding): Loaded on boot, never evicted.
    - L1 Hot Cache (LLM, ASR, CLAP, Reranker): TTL 5 min, LRU eviction.
    - L2 Cold Load (TTS): Unloaded immediately after use.
    - Hard limit: MEMORY_LIMIT_GB (default 20.0 GB).
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(MemoryManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._models: Dict[str, Dict[str, Any]] = {}
        self._memory_lock = threading.Lock()
        logger.info(f"MemoryManager initialized with MEMORY_LIMIT_GB={settings.MEMORY_LIMIT_GB}")

    def get_used_memory_gb(self) -> float:
        with self._memory_lock:
            return sum(info["memory_gb"] for info in self._models.values())

    def _evict_l1_if_needed(self, required_gb: float):
        """[Node 1.3.1] Evict oldest L1 models if total memory + required_gb exceeds 20GB limit."""
        current_used = sum(info["memory_gb"] for info in self._models.values())
        if current_used + required_gb <= settings.MEMORY_LIMIT_GB:
            return

        logger.info(f"Memory check: used={current_used:.1f}GB + req={required_gb:.1f}GB > cap={settings.MEMORY_LIMIT_GB}GB. Triggering LRU eviction.")
        
        l1_models = [
            (mod, info) for mod, info in self._models.items()
            if info["tier"] == MemoryTier.L1.value
        ]
        l1_models.sort(key=lambda x: x[1]["last_accessed"])

        for mod, info in l1_models:
            if current_used + required_gb <= settings.MEMORY_LIMIT_GB:
                break
            logger.info(f"Evicting L1 model: {mod} ({info['memory_gb']}GB)")
            self._unload_model_internal(mod)
            current_used = sum(i["memory_gb"] for i in self._models.values())

        force_free_memory()

    def evict_expired_l1_models(self):
        """[Node 1.3.1] Evict any L1 models whose idle time exceeds L1_TTL_SECONDS (300s)."""
        now = time.time()
        with self._memory_lock:
            expired = [
                mod for mod, info in self._models.items()
                if info["tier"] == MemoryTier.L1.value and (now - info["last_accessed"] > settings.L1_TTL_SECONDS)
            ]
            for mod in expired:
                logger.info(f"TTL expired for L1 model: {mod}. Evicting.")
                self._unload_model_internal(mod)
        if expired:
            force_free_memory()

    def _unload_model_internal(self, modality: str):
        if modality in self._models:
            model_info = self._models.pop(modality)
            instance = model_info.get("instance")
            del instance
            del model_info
            logger.info(f"Model [{modality}] unloaded.")

    def load_model(self, modality: str, loader_fn: Callable[[], Any]) -> Any:
        """Get or load model with memory budget enforcement."""
        mod_key = modality.value if isinstance(modality, ModelModality) else str(modality)
        model_meta = settings.MODELS.get(mod_key)
        
        if not model_meta:
            raise ValueError(f"Unknown modality: {mod_key}")

        with self._memory_lock:
            if mod_key in self._models:
                self._models[mod_key]["last_accessed"] = time.time()
                return self._models[mod_key]["instance"]

            self._evict_l1_if_needed(model_meta.memory_gb)

            logger.info(f"Loading [{mod_key}] ({model_meta.model_id}, {model_meta.memory_gb}GB, Tier {model_meta.tier})...")
            instance = loader_fn()
            
            self._models[mod_key] = {
                "instance": instance,
                "tier": model_meta.tier,
                "memory_gb": model_meta.memory_gb,
                "last_accessed": time.time(),
                "model_id": model_meta.model_id,
            }
            current_used_gb = sum(info["memory_gb"] for info in self._models.values())
            logger.info(f"[{mod_key}] loaded. Current memory usage: {current_used_gb:.1f}GB / {settings.MEMORY_LIMIT_GB}GB")
            return instance

    def release_model(self, modality: str):
        """[Node 1.3.1] Release L2 models immediately after use."""
        mod_key = modality.value if isinstance(modality, ModelModality) else str(modality)
        with self._memory_lock:
            if mod_key in self._models and self._models[mod_key]["tier"] == MemoryTier.L2.value:
                logger.info(f"Releasing L2 model [{mod_key}] immediately after use.")
                self._unload_model_internal(mod_key)
                force_free_memory()

    def get_status(self) -> Dict[str, Any]:
        with self._memory_lock:
            l0_used = sum(m["memory_gb"] for m in self._models.values() if m["tier"] == MemoryTier.L0.value)
            l1_used = sum(m["memory_gb"] for m in self._models.values() if m["tier"] == MemoryTier.L1.value)
            l2_used = sum(m["memory_gb"] for m in self._models.values() if m["tier"] == MemoryTier.L2.value)
            return {
                "total_memory_limit_gb": settings.MEMORY_LIMIT_GB,
                "current_used_gb": l0_used + l1_used + l2_used,
                "tier_breakdown_gb": {"L0": l0_used, "L1": l1_used, "L2": l2_used},
                "loaded_models": {
                    mod: {
                        "model_id": info["model_id"],
                        "tier": info["tier"],
                        "memory_gb": info["memory_gb"],
                        "last_accessed": info["last_accessed"],
                    } for mod, info in self._models.items()
                }
            }

memory_manager = MemoryManager()
