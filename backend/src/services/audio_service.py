import logging
import os
from typing import List, Optional

import numpy as np

from src.core.schemas import AudioAnalysisResult, ModelModality
from src.models.clap import clap_wrapper, CLAPWrapper
from src.models.whisper import whisper_wrapper, WhisperWrapper
from src.models.embedding import EmbeddingWrapper
from src.pipeline.vad_detector import vad_detector
from src.services.base_service import BaseService

logger = logging.getLogger(__name__)


class AudioService(BaseService):
    """
    [Node 3.4.1] Audio Service — VAD + ASR (Whisper) + Audio Embedding (CLAP).

    Processing pipeline:
      1. VAD classifies audio as voice / music / ambient.
      2. voice   → Whisper ASR transcription
         music   → CLAP 512-d audio embedding
         ambient → CLAP 512-d audio embedding
      3. Text embedding of transcript / description via EmbeddingWrapper.
    """

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def process_audio(self, audio_path: str, mode: str = "auto") -> AudioAnalysisResult:
        logger.info(f"[AudioService] Processing: {audio_path}")
        md5_str = self.calculate_md5(audio_path)
        filename = os.path.basename(audio_path)

        # 1. VAD classification & Hotspot Locator
        audio_type = vad_detector.classify_audio_type(audio_path)
        hotspot_start, hotspot_end = vad_detector.find_best_audio_window(audio_path, target_duration=30.0)
        logger.info(f"[AudioService] VAD: {audio_type}, Hotspot window: [{hotspot_start:.1f}s - {hotspot_end:.1f}s]")

        transcript: Optional[str] = None
        clap_embedding: Optional[List[float]] = None
        segments: List[dict] = []

        if audio_type == "voice":
            # 2a. Whisper ASR (transcribes active speech)
            logger.info("[AudioService] Running Whisper ASR on voice track...")
            asr_result = whisper_wrapper.transcribe(audio_path)
            transcript = asr_result.get("text", "")
            segments = asr_result.get("segments", [])
            logger.info(f"[AudioService] ASR: {len(transcript)} chars, {len(segments)} segments")
        else:
            # 2b. CLAP audio embedding on the climax/hotspot window
            logger.info("[AudioService] Running CLAP audio embedding on energy hotspot...")
            duration = max(5.0, hotspot_end - hotspot_start)
            clap_embedding = clap_wrapper.encode_audio(audio_path, dim=512, offset=hotspot_start, duration=duration)

        # 3. Text embedding for cross-modal search
        text_to_embed = transcript or f"音频文件 {filename} ({audio_type})"
        embedding_model: EmbeddingWrapper = self.memory_manager.load_model(
            ModelModality.EMBEDDING,
            loader_fn=lambda: EmbeddingWrapper()
        )
        embeddings = embedding_model.predict([text_to_embed])
        text_embedding = embeddings[0] if embeddings else None

        # Build tags
        tags = ["音频", audio_type]
        if transcript:
            # Extract a few keyword tags from transcript
            tags += self._extract_transcript_tags(transcript)

        return AudioAnalysisResult(
            audio_path=audio_path,
            md5=md5_str,
            duration_sec=self._get_duration(audio_path),
            audio_type=audio_type,
            transcript=transcript,
            clap_embedding=clap_embedding,
            tags=tags,
            embedding=text_embedding
        )

    # ------------------------------------------------------------------
    # Direct vector extraction (called by server.py /embed and /upload)
    # ------------------------------------------------------------------

    def extract_audio_feature_vector(
        self,
        audio_path: str,
        dim: int = 512,
    ) -> List[float]:
        """
        Extract a dense feature vector from an audio file.

        Strategy:
          1. CLAP (laion/clap-htsat-unfused)  → semantic 512-d vector
          2. librosa mel-spectrogram features  → 512-d fallback
          3. Deterministic hash               → offline stub

        Args:
            audio_path: Path to audio file.
            dim:        Target dimensionality (default 512 for CLAP space).

        Returns:
            L2-normalised float list of length `dim`.
        """
        if not os.path.exists(audio_path):
            logger.warning(f"[AudioService] File not found: {audio_path}")
            return self._hash_fallback_vector(audio_path, dim)

        # 1. CLAP with hotspot window detection
        try:
            hotspot_start, hotspot_end = vad_detector.find_best_audio_window(audio_path, target_duration=30.0)
            duration = max(5.0, hotspot_end - hotspot_start)
            vec = clap_wrapper.encode_audio(audio_path, dim=dim, offset=hotspot_start, duration=duration)
            if vec:
                return vec
        except Exception as e:
            logger.debug(f"[AudioService] CLAP encoding failed: {e}")

        # 2. librosa mel spectrogram
        vec = self._try_librosa_vector(audio_path, dim)
        if vec is not None:
            return vec

        # 3. Hash fallback
        logger.warning(f"[AudioService] All encoders failed. Hash fallback for {audio_path}.")
        return self._hash_fallback_vector(audio_path, dim)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _try_librosa_vector(self, audio_path: str, dim: int) -> Optional[List[float]]:
        try:
            import librosa  # type: ignore
            y, sr = librosa.load(audio_path, sr=22050, mono=True, duration=30.0)
            mel = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=128)
            mel_db = librosa.power_to_db(mel, ref=np.max)
            feat = np.concatenate([mel_db.mean(axis=1), mel_db.std(axis=1)])  # 256-d
            return self._resize_to_dim(feat.astype(np.float32), dim)
        except Exception as e:
            logger.debug(f"[AudioService] librosa failed: {e}")
            return None

    @staticmethod
    def _hash_fallback_vector(path: str, dim: int) -> List[float]:
        seed = abs(hash(path)) % (2 ** 32)
        rng = np.random.default_rng(seed)
        vec = rng.standard_normal(dim).astype(np.float32)
        return (vec / (np.linalg.norm(vec) + 1e-9)).tolist()

    @staticmethod
    def _resize_to_dim(vec: np.ndarray, dim: int) -> List[float]:
        if len(vec) >= dim:
            v = vec[:dim]
        else:
            v = np.pad(vec, (0, dim - len(vec)))
        return (v / (np.linalg.norm(v) + 1e-9)).tolist()

    @staticmethod
    def _get_duration(audio_path: str) -> float:
        try:
            import librosa  # type: ignore
            return float(librosa.get_duration(path=audio_path))
        except Exception:
            return 0.0

    @staticmethod
    def _extract_transcript_tags(transcript: str, max_tags: int = 3) -> List[str]:
        """Extract simple keyword tags from ASR transcript."""
        keywords = [
            "音乐", "歌曲", "对话", "演讲", "采访", "新闻", "播客",
            "故事", "教学", "英语", "普通话", "粤语",
        ]
        found = [kw for kw in keywords if kw in transcript]
        return found[:max_tags]


audio_service = AudioService()
