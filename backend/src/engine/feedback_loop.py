import logging
import time
from typing import Dict, List

logger = logging.getLogger(__name__)

class FeedbackLoopManager:
    """
    Feedback Loop & Dynamic Re-weighting Manager (06-推荐引擎模块.md 第7节).
    Records user implicit feedback (clicks, dwell time, impressions)
    and dynamically adjusts vector weights and tag affinity scores.
    """

    def __init__(self):
        # item_id -> {"clicks": int, "impressions": int, "dwell_sum_sec": float}
        self.stats: Dict[str, Dict[str, float]] = {}

    def record_impression(self, item_id: str):
        if item_id not in self.stats:
            self.stats[item_id] = {"clicks": 0, "impressions": 0, "dwell_sum_sec": 0.0}
        self.stats[item_id]["impressions"] += 1
        logger.info(f"[FeedbackLoop] Recorded impression for item_id={item_id}")

    def record_click(self, item_id: str, dwell_time_sec: float = 5.0):
        if item_id not in self.stats:
            self.stats[item_id] = {"clicks": 0, "impressions": 0, "dwell_sum_sec": 0.0}
        self.stats[item_id]["clicks"] += 1
        self.stats[item_id]["dwell_sum_sec"] += dwell_time_sec
        logger.info(f"[FeedbackLoop] Recorded click & dwell_time={dwell_time_sec}s for item_id={item_id}")

    def get_ctr(self, item_id: str) -> float:
        if item_id in self.stats and self.stats[item_id]["impressions"] > 0:
            return self.stats[item_id]["clicks"] / self.stats[item_id]["impressions"]
        return 0.0

feedback_loop = FeedbackLoopManager()
