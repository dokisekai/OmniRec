import logging
import queue
import threading
import time
from typing import Any, Callable

logger = logging.getLogger(__name__)


class PriorityTask:
    def __init__(self, priority: int, task_id: str, fn: Callable[[], Any]):
        self.priority = priority   # Lower number = Higher priority
        self.task_id = task_id
        self.fn = fn
        self.created_at = time.time()

    def __lt__(self, other: "PriorityTask"):
        return self.priority < other.priority


class BatchProcessor:
    """
    Concurrency & Priority Queue Manager.
    - Online search requests (Priority 0) execute immediately.
    - Background indexing tasks (Priority 10) are queued and consumed by a
      daemon worker thread, ensuring they don't block the event loop.
    """

    def __init__(self, max_workers: int = 2):
        self.max_workers = max_workers
        self.task_queue: queue.PriorityQueue = queue.PriorityQueue()
        self.semaphore = threading.Semaphore(max_workers)
        self.online_search_active = False
        self._lock = threading.Lock()
        self._shutdown = threading.Event()

        # Start background consumer daemon threads
        for i in range(max_workers):
            t = threading.Thread(
                target=self._worker_loop,
                name=f"batch-worker-{i}",
                daemon=True
            )
            t.start()

        logger.info(f"[BatchProcessor] Initialized with {max_workers} worker threads.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def submit_online_task(self, task_id: str, fn: Callable[[], Any]) -> Any:
        """Execute high-priority online search request immediately (blocks caller)."""
        with self._lock:
            self.online_search_active = True
        logger.info(f"[BatchProcessor] Priority-0 online task [{task_id}] starting.")
        try:
            return fn()
        finally:
            with self._lock:
                self.online_search_active = False

    def submit_background_task(self, task_id: str, fn: Callable[[], Any]) -> None:
        """Queue low-priority background indexing task for async execution."""
        task = PriorityTask(priority=10, task_id=task_id, fn=fn)
        self.task_queue.put(task)
        logger.info(f"[BatchProcessor] Enqueued background task [{task_id}], "
                    f"queue depth={self.task_queue.qsize()}.")

    def is_busy(self) -> bool:
        with self._lock:
            return self.online_search_active or not self.task_queue.empty()

    def shutdown(self, wait: bool = True) -> None:
        """Signal worker threads to stop; optionally wait for queue drain."""
        logger.info("[BatchProcessor] Shutdown requested.")
        self._shutdown.set()

    # ------------------------------------------------------------------
    # Internal worker loop
    # ------------------------------------------------------------------

    def _worker_loop(self) -> None:
        """
        Daemon thread main loop.
        Blocks on PriorityQueue.get() until a task arrives, then runs it.
        Backs off briefly when an online search is active to avoid GPU contention.
        """
        thread_name = threading.current_thread().name
        logger.debug(f"[BatchProcessor] Worker thread {thread_name} started.")
        while not self._shutdown.is_set():
            try:
                task: PriorityTask = self.task_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            # Yield to online tasks
            while self.online_search_active and not self._shutdown.is_set():
                time.sleep(0.05)

            start = time.time()
            logger.info(f"[BatchProcessor] [{thread_name}] Running background task [{task.task_id}] "
                        f"(waited {start - task.created_at:.1f}s in queue).")
            try:
                task.fn()
                elapsed = (time.time() - start) * 1000
                logger.info(f"[BatchProcessor] [{thread_name}] Task [{task.task_id}] done in {elapsed:.0f}ms.")
            except Exception as exc:
                logger.error(f"[BatchProcessor] Task [{task.task_id}] raised: {exc}", exc_info=True)
            finally:
                self.task_queue.task_done()

        logger.debug(f"[BatchProcessor] Worker thread {thread_name} exiting.")


batch_processor = BatchProcessor()
