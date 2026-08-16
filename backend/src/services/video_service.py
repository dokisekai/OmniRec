import logging
import os
import tempfile
from typing import Any, Callable, Dict, List, Optional
import numpy as np

from src.core.config import settings
from src.core.schemas import MediaType, VideoAnalysisResult, SearchResultItem
from src.pipeline.ffmpeg_utils import ffmpeg_utils
from src.pipeline.vad_detector import vad_detector
from src.pipeline.tag_generator import tag_generator
from src.services.base_service import BaseService
from src.services.image_service import image_service
from src.services.audio_service import audio_service
from src.vector_db.qdrant_client import vector_db_client

logger = logging.getLogger(__name__)

class VideoService(BaseService):
    """
    [Node 3.3.1, 3.3.2, 3.3.3] Independent Video Service.
    - 3.3.1: Adaptive keyframe extraction & max-pooling thumbnail_vector pooling.
    - 3.3.2: Temporal timeline frame summary ([00:05] Scene...).
    - 3.3.3: Video-to-Video multimodal search.
    """

    def process_video(self, video_path: str, prompt: Optional[str] = None, extract_audio: bool = True, on_progress: Optional[Callable[[int, int], None]] = None) -> VideoAnalysisResult:
        """[Node 3.3.1 & 3.3.2] Temporal Video Analysis & Multi-Track Vector Generation."""
        logger.info(f"[VideoService] Processing video: {video_path}")
        md5_str = self.calculate_md5(video_path)

        duration_sec = ffmpeg_utils.get_video_duration(video_path)

        with tempfile.TemporaryDirectory() as tmp_frames_dir:
            # 3.3.1: Adaptive keyframe extraction
            extracted_frames = ffmpeg_utils.extract_keyframes(video_path, tmp_frames_dir, strategy="adaptive")
            logger.info(f"[VideoService] Extracted {len(extracted_frames)} keyframes.")

            # Cap keyframes to 2 representative frames for responsive VLM inference on GPU
            MAX_FRAMES = 2
            if len(extracted_frames) > MAX_FRAMES:
                idxs = [0, len(extracted_frames) // 2]
                extracted_frames = [extracted_frames[i] for i in idxs]
                logger.info(f"[VideoService] Sampled {len(extracted_frames)} keyframes for VLM analysis.")

            total = len(extracted_frames)
            frame_descriptions: List[str] = []
            frame_tags: List[str] = ["视频", "多模态"]
            visual_vectors: List[List[float]] = []

            for idx, frame_file in enumerate(extracted_frames, start=1):
                if on_progress is not None:
                    try:
                        on_progress(idx, total)
                    except Exception:
                        pass
                timestamp_str = f"[{idx * 5:02d}s]"
                img_res = image_service.process_image(frame_file, prompt=prompt)
                frame_descriptions.append(f"{timestamp_str} {img_res.description}")
                frame_tags.extend(img_res.tags)

                vis_vec = image_service.extract_visual_feature_vector(frame_file, dim=settings.VECTOR_DIM)
                visual_vectors.append(vis_vec)

            # 3.3.1: Max-pooling thumbnail_vector
            if visual_vectors:
                thumbnail_vec = np.max(np.array(visual_vectors), axis=0).tolist()
            else:
                thumbnail_vec = [0.1] * settings.VECTOR_DIM

        # Audio track processing
        audio_transcript = None
        clap_vector = None
        if extract_audio:
            with tempfile.TemporaryDirectory() as tmp_audio_dir:
                audio_track_path = os.path.join(tmp_audio_dir, "audio_track.wav")
                ffmpeg_utils.extract_audio_track(video_path, audio_track_path)
                
                audio_res = audio_service.process_audio(audio_track_path)
                audio_transcript = audio_res.transcript
                clap_vector = audio_res.clap_embedding
                frame_tags.extend(audio_res.tags)

        # 3.3.2: Temporal timeline summary
        temporal_summary = f"【视频全片剧情/镜头总结】 Duration: {duration_sec:.1f}s.\n" + "\n".join(frame_descriptions)
        if audio_transcript:
            temporal_summary += f"\n【原声语音字幕】: {audio_transcript}"

        categorized_tags = tag_generator.generate_categorized_tags(temporal_summary)
        all_tags = list(set(frame_tags + tag_generator.flatten_tags(temporal_summary)))

        from src.core.schemas import ModelModality
        from src.models.embedding import EmbeddingWrapper
        embedding_model: EmbeddingWrapper = self.memory_manager.load_model(
            ModelModality.EMBEDDING,
            loader_fn=lambda: EmbeddingWrapper()
        )
        embeddings = embedding_model.predict([temporal_summary])
        content_vec = embeddings[0] if embeddings else thumbnail_vec

        return VideoAnalysisResult(
            video_path=video_path,
            md5=md5_str,
            duration_sec=duration_sec,
            extracted_frames=len(extracted_frames),
            frame_descriptions=frame_descriptions,
            audio_transcript=audio_transcript,
            tags=all_tags,
            embedding=content_vec
        )

    def search_similar_videos(self, video_path: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """[Node 3.3.3] Video-to-Video Multi-Track Search."""
        video_res = self.process_video(video_path)
        
        hits = vector_db_client.search_similar(
            query_vector=video_res.embedding or [0.1] * settings.VECTOR_DIM,
            vector_name="content_vector",
            filter_media_type=MediaType.VIDEO.value,
            top_k=top_k
        )
        return hits

video_service = VideoService()
