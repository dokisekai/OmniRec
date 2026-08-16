from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

class BaseModelWrapper(ABC):
    """
    [Node 2.1.1] Abstract Base Class for AI Model Wrappers.
    Enforces unified lifecycle: load(), unload(), is_loaded, predict().
    """

    def __init__(self, model_id: str, estimated_memory_gb: float = 2.0):
        self.model_id = model_id
        self.estimated_memory_gb = estimated_memory_gb
        self._model = None
        self._is_loaded = False

    @abstractmethod
    def load(self):
        """Load model weights into GPU/RAM."""
        pass

    @abstractmethod
    def unload(self):
        """Unload model and free GPU/RAM."""
        pass

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded

    @abstractmethod
    def predict(self, inputs: Any, **kwargs) -> Any:
        """Run model inference."""
        pass
