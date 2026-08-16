import logging
import os
from typing import Dict, List, Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)


class VADDetector:
    """
    Intelligent Voice Activity Detection (VAD) & Audio Hotspot Locator.
    
    Features:
    1. Short-Time Energy & RMS Envelope Analysis (finds music climaxes / vocal hotspots).
    2. Silence & Noise Rejection (skips leading/trailing dead air, intro jingles).
    3. Optimal Window Extraction (picks the most informative 30s window for CLAP & Whisper).
    4. Accurate Audio Modality Classification (voice vs music vs ambient).
    """

    def detect_speech_segments(self, audio_path: str) -> List[Tuple[float, float]]:
        """
        Detect active speech intervals in an audio file using energy & spectral analysis.
        Returns list of (start_sec, end_sec) intervals.
        """
        if not os.path.exists(audio_path):
            return [(0.0, 5.0)]

        try:
            import librosa
            # Load up to 3 minutes for VAD scan
            y, sr = librosa.load(audio_path, sr=16000, mono=True, duration=180.0)
            if len(y) == 0:
                return [(0.0, 5.0)]

            # 1. Compute Short-Time RMS Energy (frame_length=2048, hop_length=512)
            hop_length = 512
            rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=hop_length)[0]
            
            # Dynamic energy threshold (mean + 0.25 * std)
            rms_threshold = np.mean(rms) * 0.65
            active_frames = np.where(rms > rms_threshold)[0]

            if len(active_frames) == 0:
                duration = float(len(y) / sr)
                return [(0.0, min(10.0, duration))]

            # 2. Group active frames into continuous speech segments (minimum 1.0s)
            frame_times = librosa.frames_to_time(active_frames, sr=sr, hop_length=hop_length)
            segments: List[Tuple[float, float]] = []
            
            if len(frame_times) > 0:
                seg_start = frame_times[0]
                prev_time = frame_times[0]

                for t in frame_times[1:]:
                    if t - prev_time > 1.5:  # Pause > 1.5s indicates segment boundary
                        if prev_time - seg_start >= 0.8:
                            segments.append((float(seg_start), float(prev_time)))
                        seg_start = t
                    prev_time = t

                if prev_time - seg_start >= 0.8:
                    segments.append((float(seg_start), float(prev_time)))

            if not segments:
                duration = float(len(y) / sr)
                return [(0.0, min(15.0, duration))]

            logger.info(f"[VAD] Detected {len(segments)} distinct voice activity segments in {os.path.basename(audio_path)}")
            return segments

        except Exception as e:
            logger.debug(f"[VAD] librosa detection error ({e}), using heuristic fallback.")
            return self._heuristic_fallback(audio_path)

    def find_best_audio_window(self, audio_path: str, target_duration: float = 30.0) -> Tuple[float, float]:
        """
        Locates the single highest-information/highest-energy time window in a long audio track.
        Avoids initial silence or trailing fade-out.
        
        Returns: (start_sec, end_sec)
        """
        if not os.path.exists(audio_path):
            return (0.0, target_duration)

        try:
            import librosa
            # Load full audio duration
            total_duration = float(librosa.get_duration(path=audio_path))
            if total_duration <= target_duration:
                return (0.0, total_duration)

            # Sample audio across timeline to find highest energy chunk
            y, sr = librosa.load(audio_path, sr=16000, mono=True)
            hop = 16000 * 5  # 5-second sliding step
            win_samples = int(target_duration * sr)

            best_energy = -1.0
            best_start = 0.0

            for start_sample in range(0, max(1, len(y) - win_samples), hop):
                chunk = y[start_sample : start_sample + win_samples]
                energy = float(np.sum(chunk ** 2))
                if energy > best_energy:
                    best_energy = energy
                    best_start = float(start_sample / sr)

            logger.info(
                f"[VAD Hotspot] Selected optimal audio window for {os.path.basename(audio_path)}: "
                f"[{best_start:.1f}s - {best_start + target_duration:.1f}s] (total {total_duration:.1f}s)"
            )
            return (best_start, min(total_duration, best_start + target_duration))

        except Exception as e:
            logger.debug(f"[VAD] Best window detection fallback: {e}")
            return (0.0, target_duration)

    def classify_audio_type(self, audio_path: str) -> str:
        """
        Classify audio type into 'voice', 'music', or 'ambient' using
        Spectral Centroid, Zero-Crossing Rate & Speech Ratio.
        """
        filename = os.path.basename(audio_path).lower()
        if any(kw in filename for kw in ["music", "bgm", "song", "track", "audio_bgm"]):
            return "music"

        try:
            import librosa
            y, sr = librosa.load(audio_path, sr=16000, mono=True, duration=30.0)
            if len(y) == 0:
                return "ambient"

            # Spectral Flatness (music is harmonic/peaked; ambient/noise is flat)
            flatness = float(np.mean(librosa.feature.spectral_flatness(y=y)))
            # Zero Crossing Rate (speech has higher variance than pure music/ambient)
            zcr = librosa.feature.zero_crossing_rate(y)[0]
            zcr_std = float(np.std(zcr))

            segments = self.detect_speech_segments(audio_path)
            speech_dur = sum(end - start for start, end in segments)

            if speech_dur >= 3.0 and zcr_std > 0.04:
                return "voice"
            elif flatness < 0.08:
                return "music"
            else:
                return "ambient"

        except Exception as e:
            logger.debug(f"[VAD] Classification fallback: {e}")
            return "voice"

    @staticmethod
    def _heuristic_fallback(audio_path: str) -> List[Tuple[float, float]]:
        file_size = os.path.getsize(audio_path) if os.path.exists(audio_path) else 100000
        dur = max(5.0, min(180.0, file_size / 32000.0))
        return [(0.0, min(10.0, dur))]


vad_detector = VADDetector()
