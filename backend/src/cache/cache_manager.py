import json
import logging
import os
import time
from typing import Any, Dict, Optional

from src.core.config import settings

logger = logging.getLogger(__name__)

class CacheManager:
    """
    Two-tier Caching Architecture (08-缓存容错与批量处理.md).
    - L1 In-Memory LRU Cache: Query vectors & top-k search results.
    - L2 DiskCache: Content-addressed (MD5) persistent cache for VLM descriptions & ASR transcripts.
    """

    def __init__(self, max_l1_items: int = 1000):
        self.max_l1_items = max_l1_items
        self._l1_cache: Dict[str, Dict[str, Any]] = {}
        self.disk_cache_dir = os.path.join(settings.CACHE_DIR, "l2_disk_cache")
        os.makedirs(self.disk_cache_dir, exist_ok=True)
        logger.info(f"CacheManager initialized. DiskCache dir: {self.disk_cache_dir}")

    # --- L1 Memory Cache Methods ---

    def get_l1(self, key: str) -> Optional[Any]:
        if key in self._l1_cache:
            entry = self._l1_cache[key]
            entry["last_accessed"] = time.time()
            return entry["value"]
        return None

    def set_l1(self, key: str, value: Any):
        if len(self._l1_cache) >= self.max_l1_items:
            # Evict oldest entry
            oldest_key = min(self._l1_cache.keys(), key=lambda k: self._l1_cache[k]["last_accessed"])
            del self._l1_cache[oldest_key]
        
        self._l1_cache[key] = {
            "value": value,
            "last_accessed": time.time()
        }

    # --- L2 DiskCache Methods ---

    def get_l2_by_md5(self, md5_str: str) -> Optional[Dict[str, Any]]:
        cache_file = os.path.join(self.disk_cache_dir, f"{md5_str}.json")
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    logger.info(f"[L2 Cache Hit] Loaded persistent cache for MD5: {md5_str}")
                    return data
            except Exception as e:
                logger.error(f"Error reading L2 cache file {cache_file}: {e}")
        return None

    def set_l2_by_md5(self, md5_str: str, data: Dict[str, Any]):
        cache_file = os.path.join(self.disk_cache_dir, f"{md5_str}.json")
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"[L2 Cache Saved] Persisted cache for MD5: {md5_str}")
        except Exception as e:
            logger.error(f"Error writing L2 cache file {cache_file}: {e}")

cache_manager = CacheManager()
