import logging
import os
from typing import List, Optional
import numpy as np

from src.models.base import BaseModelWrapper
from src.core.config import find_embedding_model_path

logger = logging.getLogger(__name__)


class EmbeddingWrapper(BaseModelWrapper):
    """
    [Node 2.3.1] Qwen3-VL-Embedding Multimodal Dense Vector Adapter.
    Generates normalized 2048-dimensional MRL embeddings.
    
    Loading strategy:
      1. Try sentence-transformers (HuggingFace) with the local model path
      2. Try transformers AutoModel + mean pooling
      3. Fall back to deterministic hash-seeded vectors (offline mode only)
    """

    def __init__(self, model_id: Optional[str] = None, dim: int = 2048):
        resolved = model_id or find_embedding_model_path()
        super().__init__(resolved, estimated_memory_gb=2.0)
        self.tokenizer = None
        self.dim = dim
        self._backend: str = "none"  # "sentence_transformers" | "transformers" | "hash_fallback"

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def load(self):
        logger.info(f"[EmbeddingWrapper] Loading model from: {self.model_id}")
        self._try_load_sentence_transformers()
        if self._backend == "none":
            self._try_load_transformers()
        if self._backend == "none":
            logger.warning(
                "[EmbeddingWrapper] No real embedding backend available. "
                "Using hash-seeded fallback (semantics invalid). "
                "Install sentence-transformers or ensure model weights exist."
            )
            self._backend = "hash_fallback"
        self._is_loaded = True
        logger.info(f"[EmbeddingWrapper] Backend selected: {self._backend}")

    def _try_load_sentence_transformers(self):
        """Attempt to load via sentence-transformers (preferred)."""
        try:
            from sentence_transformers import SentenceTransformer
            model_path = self.model_id if os.path.exists(self.model_id) else "Qwen/Qwen3-Embedding-2B"
            self._model = SentenceTransformer(model_path, trust_remote_code=True)
            self._backend = "sentence_transformers"
            logger.info(f"[EmbeddingWrapper] ✅ Loaded via sentence-transformers: {model_path}")
        except Exception as e:
            logger.debug(f"[EmbeddingWrapper] sentence-transformers load failed: {e}")

    def _try_load_transformers(self):
        """Attempt to load via HuggingFace transformers with manual mean pooling."""
        try:
            from transformers import AutoTokenizer, AutoModel
            model_path = self.model_id if os.path.exists(self.model_id) else "Qwen/Qwen3-Embedding-2B"
            self.tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
            self._model = AutoModel.from_pretrained(model_path, trust_remote_code=True)
            self._model.eval()
            self._backend = "transformers"
            logger.info(f"[EmbeddingWrapper] ✅ Loaded via transformers: {model_path}")
        except Exception as e:
            logger.debug(f"[EmbeddingWrapper] transformers load failed: {e}")

    def unload(self):
        logger.info(f"[EmbeddingWrapper] Unloading embedding model.")
        self._model = None
        self.tokenizer = None
        self._backend = "none"
        self._is_loaded = False

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def predict(self, texts: List[str]) -> List[List[float]]:
        if not self._is_loaded:
            self.load()

        if self._backend == "sentence_transformers":
            return self._predict_sentence_transformers(texts)
        elif self._backend == "transformers":
            return self._predict_transformers(texts)
        else:
            return self._predict_hash_fallback(texts)

    def _predict_sentence_transformers(self, texts: List[str]) -> List[List[float]]:
        try:
            embeddings = self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
            # Truncate or pad to target dim
            results = []
            for emb in embeddings:
                vec = np.array(emb, dtype=np.float32)
                vec = self._resize_to_dim(vec)
                results.append(vec.tolist())
            return results
        except Exception as e:
            logger.error(f"[EmbeddingWrapper] sentence-transformers inference error: {e}")
            return self._predict_hash_fallback(texts)

    def _predict_transformers(self, texts: List[str]) -> List[List[float]]:
        try:
            import torch
            encoded = self.tokenizer(
                texts,
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="pt"
            )
            with torch.no_grad():
                output = self._model(**encoded)
            # Mean pooling over token dimension
            attention_mask = encoded["attention_mask"]
            token_embeddings = output.last_hidden_state
            input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
            pooled = torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(input_mask_expanded.sum(1), min=1e-9)
            # L2 normalize
            pooled = torch.nn.functional.normalize(pooled, p=2, dim=1)
            results = []
            for vec in pooled.cpu().numpy():
                results.append(self._resize_to_dim(vec).tolist())
            return results
        except Exception as e:
            logger.error(f"[EmbeddingWrapper] transformers inference error: {e}")
            return self._predict_hash_fallback(texts)

    def _predict_hash_fallback(self, texts: List[str]) -> List[List[float]]:
        """Deterministic hash-seeded Gaussian fallback (offline/stub mode only)."""
        results = []
        for text in texts:
            seed = abs(hash(text)) % (2 ** 32)
            rng = np.random.default_rng(seed)
            vec = rng.standard_normal(self.dim).astype(np.float32)
            norm = np.linalg.norm(vec)
            vec = vec / (norm + 1e-9)
            results.append(vec.tolist())
        return results

    def _resize_to_dim(self, vec: np.ndarray) -> np.ndarray:
        """Resize vector to target dim via truncation or zero-padding."""
        if len(vec) >= self.dim:
            return vec[:self.dim]
        return np.pad(vec, (0, self.dim - len(vec)))


embedding_wrapper = EmbeddingWrapper()
