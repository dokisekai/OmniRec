import logging
import os
import threading
from typing import Optional

from src.models.base import BaseModelWrapper

logger = logging.getLogger(__name__)

# Whisper model size tiers and their memory footprint
_WHISPER_SIZES = {
    "large-v3": 1.5,
    "large-v2": 1.5,
    "large":    1.5,
    "medium":   0.8,
    "small":    0.25,
    "base":     0.14,
    "tiny":     0.07,
}


class WhisperWrapper(BaseModelWrapper):
    """
    [Node 2.6.1] Whisper ASR — Automatic Speech Recognition.

    Loading strategy:
      1. openai-whisper (pip install openai-whisper) — most reliable on macOS.
      2. transformers WhisperForConditionalGeneration — HuggingFace pipeline.
      3. Stub transcript fallback when neither is available.

    Default model: large-v3 (best quality, ~1.5 GB).
    To use a smaller model set WHISPER_MODEL env var to e.g. "base".
    """

    def __init__(self, model_size: Optional[str] = None):
        size = model_size or os.getenv("WHISPER_MODEL", "large-v3")
        # Prefer local weights if found
        local_path = os.path.join("backend", "models", f"whisper-{size}")
        model_id = local_path if os.path.exists(local_path) else f"openai/whisper-{size}"
        mem_gb = _WHISPER_SIZES.get(size, 1.5)
        super().__init__(model_id, estimated_memory_gb=mem_gb)
        self._size = size
        self._pipe = None          # openai-whisper model OR HF pipeline
        self._backend: str = "none"  # "openai_whisper" | "transformers" | "stub"
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def load(self):
        if self._is_loaded:
            return
        logger.info(f"[WhisperWrapper] Loading Whisper-{self._size}...")
        self._try_openai_whisper()
        if self._backend == "none":
            self._try_transformers_pipeline()
        if self._backend == "none":
            logger.warning(
                "[WhisperWrapper] Neither openai-whisper nor transformers available. "
                "Install openai-whisper: pip install openai-whisper"
            )
            self._backend = "stub"
        self._is_loaded = True
        logger.info(f"[WhisperWrapper] Backend: {self._backend}")

    def _try_openai_whisper(self):
        try:
            import whisper  # type: ignore
            # Use local model dir if it exists, otherwise download
            download_root = os.path.join("backend", "models")
            self._pipe = whisper.load_model(self._size, download_root=download_root)
            self._backend = "openai_whisper"
            logger.info(f"[WhisperWrapper] ✅ openai-whisper {self._size} loaded.")
        except Exception as e:
            logger.debug(f"[WhisperWrapper] openai-whisper load failed: {e}")

    def _try_transformers_pipeline(self):
        try:
            from transformers import pipeline  # type: ignore
            if os.path.exists(self.model_id):
                model_id = self.model_id
            else:
                # If not locally present, don't block on network in offline mode
                return
            self._pipe = pipeline(
                "automatic-speech-recognition",
                model=model_id,
                chunk_length_s=30,
                stride_length_s=5,
                return_timestamps=True,
            )
            self._backend = "transformers"
            logger.info(f"[WhisperWrapper] ✅ HF Whisper pipeline loaded: {model_id}")
        except Exception as e:
            logger.debug(f"[WhisperWrapper] transformers pipeline load failed: {e}")

    def unload(self):
        self._pipe = None
        self._backend = "none"
        self._is_loaded = False

    # ------------------------------------------------------------------
    # Transcription
    # ------------------------------------------------------------------

    def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None,
        task: str = "transcribe",
    ) -> dict:
        """
        Transcribe speech from an audio file.

        Args:
            audio_path: Path to audio file.
            language:   ISO-639 language hint (e.g. "zh", "en"). None = auto-detect.
            task:       "transcribe" or "translate" (to English).

        Returns:
            Dict with keys:
                "text"     – full transcript string
                "language" – detected/used language code
                "segments" – list of {start, end, text} dicts (if available)
        """
        if not self._is_loaded:
            self.load()

        if not os.path.exists(audio_path):
            return self._stub_result(audio_path)

        with self._lock:
            if self._backend == "openai_whisper":
                return self._transcribe_openai(audio_path, language, task)
            elif self._backend == "transformers":
                return self._transcribe_hf(audio_path, language, task)
            else:
                return self._stub_result(audio_path)

    def predict(self, audio_path: str) -> str:
        """BaseModelWrapper-compatible entry point. Returns transcript text."""
        return self.transcribe(audio_path).get("text", "")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _transcribe_openai(self, audio_path: str, language: Optional[str], task: str) -> dict:
        try:
            opts = {"task": task}
            if language:
                opts["language"] = language
            result = self._pipe.transcribe(audio_path, **opts)
            segments = [
                {"start": s["start"], "end": s["end"], "text": s["text"]}
                for s in result.get("segments", [])
            ]
            logger.info(
                f"[WhisperWrapper] Transcribed {os.path.basename(audio_path)} "
                f"({result.get('language', '?')}) — {len(result['text'])} chars"
            )
            return {
                "text": result["text"].strip(),
                "language": result.get("language", language or "auto"),
                "segments": segments,
            }
        except Exception as e:
            logger.error(f"[WhisperWrapper] openai-whisper transcription error: {e}")
            return self._stub_result(audio_path)

    def _transcribe_hf(self, audio_path: str, language: Optional[str], task: str) -> dict:
        try:
            gen_kwargs = {"task": task}
            if language:
                from transformers.models.whisper.tokenization_whisper import TO_LANGUAGE_CODE  # type: ignore
                lang_code = TO_LANGUAGE_CODE.get(language, language)
                gen_kwargs["language"] = lang_code

            result = self._pipe(audio_path, generate_kwargs=gen_kwargs)
            text = result.get("text", "").strip()
            chunks = result.get("chunks", [])
            segments = [
                {"start": c["timestamp"][0], "end": c["timestamp"][1], "text": c["text"]}
                for c in chunks
            ]
            logger.info(f"[WhisperWrapper] HF transcribed: {len(text)} chars")
            return {
                "text": text,
                "language": language or "auto",
                "segments": segments,
            }
        except Exception as e:
            logger.error(f"[WhisperWrapper] HF transcription error: {e}")
            return self._stub_result(audio_path)

    @staticmethod
    def _stub_result(audio_path: str) -> dict:
        fname = os.path.basename(audio_path)
        return {
            "text": f"[ASR Stub — {fname}]: 暂无真实转写结果，请安装 openai-whisper。",
            "language": "zh",
            "segments": [],
        }


whisper_wrapper = WhisperWrapper()
