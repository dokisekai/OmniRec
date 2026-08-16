import logging
import time
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

class DegradationManager:
    """
    Circuit Breaker & Graceful Degradation Manager (08-缓存容错与批量处理.md 第2节).
    Monitors model failure rates and memory pressure, triggering automatic fallbacks
    (e.g., VLM failure -> fallback to color histogram / basic text metadata).
    """

    def __init__(self, failure_threshold: int = 3, reset_timeout_sec: float = 60.0):
        self.failure_threshold = failure_threshold
        self.reset_timeout_sec = reset_timeout_sec
        # modality -> {"failure_count": int, "circuit_open": bool, "last_failure": float}
        self.breakers: Dict[str, Dict[str, Any]] = {}

    def execute_with_fallback(
        self,
        modality: str,
        primary_fn: Callable[[], Any],
        fallback_fn: Callable[[], Any]
    ) -> Any:
        now = time.time()
        info = self.breakers.setdefault(modality, {"failure_count": 0, "circuit_open": False, "last_failure": 0.0})

        # Check circuit breaker reset timeout
        if info["circuit_open"]:
            if now - info["last_failure"] > self.reset_timeout_sec:
                logger.info(f"[Degradation] Circuit breaker reset timeout passed for [{modality}]. Half-opening circuit.")
                info["circuit_open"] = False
                info["failure_count"] = 0
            else:
                logger.warning(f"[Degradation] Circuit OPEN for [{modality}]. Invoking Fallback strategy immediately.")
                return fallback_fn()

        try:
            result = primary_fn()
            # Success: reset failure count
            info["failure_count"] = 0
            return result
        except Exception as e:
            info["failure_count"] += 1
            info["last_failure"] = now
            logger.error(f"[Degradation] Primary execution failed for [{modality}] ({info['failure_count']}/{self.failure_threshold}): {e}")
            
            if info["failure_count"] >= self.failure_threshold:
                logger.critical(f"[Degradation] Failure threshold reached. Opening Circuit Breaker for [{modality}]!")
                info["circuit_open"] = True
                
            return fallback_fn()

degradation_manager = DegradationManager()
