import logging
import os
import threading
from typing import List, Optional

import numpy as np

from src.models.base import BaseModelWrapper
from src.core.config import find_clap_model_path

logger = logging.getLogger(__name__)


class CLAPWrapper(BaseModelWrapper):
    """
    [Node 2.5.1] LAION CLAP — Contrastive Language-Audio Pretraining.

    Generates 512-dimensional audio embeddings and supports audio-text
    similarity scoring. Loads from local weights at backend/models/clap_model.

    Memory: ~0.6 GB.
    """

    def __init__(self, model_id: Optional[str] = None):
        resolved = model_id or find_clap_model_path()
        super().__init__(resolved, estimated_memory_gb=0.6)
        self._processor = None
        self._model = None
        self._backend: str = "none"   # "transformers" | "hash_fallback"
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def load(self):
        if self._is_loaded:
            return
        logger.info(f"[CLAPWrapper] Loading CLAP model from: {self.model_id}")
        self._try_load_transformers()
        if self._backend == "none":
            logger.warning(
                "[CLAPWrapper] CLAP unavailable — using hash-fallback 512d vectors."
            )
            self._backend = "hash_fallback"
        self._is_loaded = True
        logger.info(f"[CLAPWrapper] Backend: {self._backend}")

    def _try_load_transformers(self):
        if not os.path.exists(self.model_id):
            logger.debug(f"[CLAPWrapper] Model path not found: {self.model_id}")
            return
        try:
            from transformers import ClapModel, ClapProcessor  # type: ignore
            self._processor = ClapProcessor.from_pretrained(self.model_id)
            self._model = ClapModel.from_pretrained(self.model_id)
            self._model.eval()
            self._backend = "transformers"
            logger.info("[CLAPWrapper] ✅ LAION CLAP loaded via transformers.")
        except Exception as e:
            logger.warning(f"[CLAPWrapper] transformers load failed: {e}")

    def unload(self):
        self._model = None
        self._processor = None
        self._backend = "none"
        self._is_loaded = False

    # ------------------------------------------------------------------
    # Audio embedding
    # ------------------------------------------------------------------

    def encode_audio(self, audio_path: str, dim: int = 512, offset: float = 0.0, duration: float = 30.0) -> List[float]:
        """
        Encode an audio file into a CLAP 512-d vector.

        Args:
            audio_path: Path to audio file (.wav/.mp3/.m4a).
            dim:        Target dimensionality (CLAP native = 512).
            offset:     Start time in seconds (for hotspot window extraction).
            duration:   Window duration in seconds.

        Returns:
            L2-normalised float list of length `dim`.
        """
        if not self._is_loaded:
            self.load()
        with self._lock:
            if self._backend == "transformers":
                return self._encode_transformers(audio_path, dim, offset=offset, duration=duration)
            return self._hash_fallback(audio_path, dim)

    def encode_text(self, text: str) -> List[float]:
        """Encode a text description into the shared CLAP 512-d space."""
        if not self._is_loaded:
            self.load()
        with self._lock:
            if self._backend == "transformers":
                return self._encode_text_transformers(text)
            return self._hash_fallback(text, 512)

    def audio_text_similarity(self, audio_path: str, text: str) -> float:
        """Return cosine similarity between audio and text in the CLAP space."""
        av = np.array(self.encode_audio(audio_path))
        tv = np.array(self.encode_text(text))
        return float(np.dot(av, tv) / (np.linalg.norm(av) * np.linalg.norm(tv) + 1e-9))

    # BaseModelWrapper compat
    def predict(self, audio_path: str) -> List[float]:
        return self.encode_audio(audio_path)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _encode_transformers(self, audio_path: str, dim: int, offset: float = 0.0, duration: float = 30.0) -> List[float]:
        try:
            import torch

            audio = None
            sr = 48000
            try:
                import soundfile as sf
                info = sf.info(audio_path)
                start_frame = int(offset * info.samplerate)
                frames = int(duration * info.samplerate)
                data, orig_sr = sf.read(audio_path, start=start_frame, frames=frames, dtype="float32")
                if len(data.shape) > 1:
                    data = data.mean(axis=1)  # mono
                if orig_sr != 48000:
                    # Simple linear resample to 48kHz
                    num_samples = int(len(data) * 48000 / orig_sr)
                    audio = np.interp(np.linspace(0, len(data), num_samples), np.arange(len(data)), data)
                else:
                    audio = data
                sr = 48000
            except Exception as e_sf:
                try:
                    import librosa
                    audio, sr = librosa.load(audio_path, sr=48_000, mono=True, offset=offset, duration=duration)
                except Exception as e_lib:
                    from scipy.io import wavfile
                    orig_sr, data = wavfile.read(audio_path)
                    data = data.astype(np.float32) / 32768.0
                    if len(data.shape) > 1:
                        data = data.mean(axis=1)
                    audio = data
                    sr = orig_sr

            try:
                inputs = self._processor(audio=audio, sampling_rate=sr, return_tensors="pt")
            except TypeError:
                inputs = self._processor(audios=audio, sampling_rate=sr, return_tensors="pt")

            with torch.no_grad():
                emb = self._model.get_audio_features(**inputs)
            
            if hasattr(emb, "audio_embeds"):
                emb_tensor = emb.audio_embeds
            elif hasattr(emb, "pooler_output") and emb.pooler_output is not None:
                emb_tensor = emb.pooler_output
            elif hasattr(emb, "last_hidden_state"):
                emb_tensor = emb.last_hidden_state.mean(dim=1)
            else:
                emb_tensor = emb

            vec = torch.nn.functional.normalize(emb_tensor, p=2, dim=-1)
            vec = vec.squeeze().cpu().numpy().astype(np.float32)
            return self._resize(vec, dim)
        except Exception as e:
            logger.error(f"[CLAPWrapper] encode_audio error: {e}")
            return self._hash_fallback(audio_path, dim)

    def _encode_text_transformers(self, text: str) -> List[float]:
        try:
            import torch
            inputs = self._processor(
                text=[text], return_tensors="pt", padding=True, truncation=True
            )
            with torch.no_grad():
                emb = self._model.get_text_features(**inputs)

            if hasattr(emb, "text_embeds"):
                emb_tensor = emb.text_embeds
            elif hasattr(emb, "pooler_output") and emb.pooler_output is not None:
                emb_tensor = emb.pooler_output
            elif hasattr(emb, "last_hidden_state"):
                emb_tensor = emb.last_hidden_state.mean(dim=1)
            else:
                emb_tensor = emb

            vec = torch.nn.functional.normalize(emb_tensor, p=2, dim=-1)
            vec = vec.squeeze().cpu().numpy().astype(np.float32)
            return self._resize(vec, 512)
        except Exception as e:
            logger.error(f"[CLAPWrapper] encode_text error: {e}")
            return self._hash_fallback(text, 512)

    @staticmethod
    def _hash_fallback(key: str, dim: int) -> List[float]:
        seed = abs(hash(key)) % (2 ** 32)
        rng = np.random.default_rng(seed)
        vec = rng.standard_normal(dim).astype(np.float32)
        return (vec / (np.linalg.norm(vec) + 1e-9)).tolist()

    @staticmethod
    def _resize(vec: np.ndarray, dim: int) -> List[float]:
        if len(vec) >= dim:
            v = vec[:dim]
        else:
            v = np.pad(vec, (0, dim - len(vec)))
        return (v / (np.linalg.norm(v) + 1e-9)).tolist()


clap_wrapper = CLAPWrapper()
