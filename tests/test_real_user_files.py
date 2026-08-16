import logging
import os
import json
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("test_real_user_files")

from src.core.schemas import MediaType, RecommendQuery, SearchQuery
from src.pipeline.ffmpeg_utils import ffmpeg_utils
from src.services.image_service import image_service
from src.services.video_service import video_service
from src.services.audio_service import audio_service
from src.services.text_service import text_service
from src.pipeline.progressive_indexer import progressive_indexer
from src.engine.recommendation_engine import recommendation_engine
from src.engine.retrieval_engine import retrieval_engine

def main():
    img_path = "/Users/xiuxiuxiu/Desktop/multimodal-recommender/test_files/beauty_1755438760705.jpeg"
    video_path = "/Users/xiuxiuxiu/Desktop/multimodal-recommender/test_files/IMG_2514.MOV"
    extracted_audio_path = "/Users/xiuxiuxiu/Desktop/multimodal-recommender/test_files/extracted_audio.wav"

    logger.info("==================================================")
    logger.info("真实媒体文件 (图片、视频、分离独立音频) 实测验证")
    logger.info("==================================================")

    # 1. 音频分离测试 (Extract Audio Track from Video)
    logger.info("\n--- [1] 视频音轨分离与独立音频文件生成 ---")
    if os.path.exists(video_path):
        audio_file = ffmpeg_utils.extract_audio_track(video_path, extracted_audio_path)
        logger.info(f"成功分离出独立音频文件: {audio_file}")
        logger.info(f"分离音频文件大小: {os.path.getsize(audio_file) / 1024:.2f} KB")

    # 2. 真实图片分析测试
    if os.path.exists(img_path):
        logger.info(f"\n--- [2] 真实图片分析测试: {os.path.basename(img_path)} ---")
        img_res = image_service.process_image(img_path)
        vis_vec = image_service.extract_visual_feature_vector(img_path)
        colors = image_service.extract_dominant_colors(img_path)
        
        logger.info(f"图片 MD5: {img_res.md5}")
        logger.info(f"图片 Hex 主色调卡片: {colors}")
        logger.info(f"图片视觉特征向量 (thumbnail_vector) 维度: {len(vis_vec)}, L2范数: {np.linalg.norm(vis_vec):.4f}")
        logger.info(f"图片 VLM 分析描述:\n{img_res.description}\n")
        logger.info(f"图片抽取 6 维结构化标签集 ({len(img_res.tags)}个): {img_res.tags}")

    # 3. 真实视频分析测试
    if os.path.exists(video_path):
        logger.info(f"\n--- [3] 真实视频分析测试: {os.path.basename(video_path)} ---")
        vid_res = video_service.process_video(video_path, extract_audio=True)
        
        logger.info(f"视频 MD5: {vid_res.md5}")
        logger.info(f"视频时长: {vid_res.duration_sec:.1f} 秒, 关键帧抽帧数: {vid_res.extracted_frames}")
        logger.info(f"视频时序剧情 checkpoint:")
        for frame_desc in vid_res.frame_descriptions:
            logger.info(f"  {frame_desc}")
        logger.info(f"视频融合总标签集 ({len(vid_res.tags)}个): {vid_res.tags}")

    # 4. 独立分离音频分析测试
    if os.path.exists(extracted_audio_path):
        logger.info(f"\n--- [4] 独立分离音频文件分析测试: {os.path.basename(extracted_audio_path)} ---")
        audio_res = audio_service.process_audio(extracted_audio_path)
        
        logger.info(f"分离音频 MD5: {audio_res.md5}")
        logger.info(f"音频分类判定 (VAD Detector): {audio_res.audio_type}")
        if audio_res.transcript:
            logger.info(f"音频 Whisper ASR 字幕: {audio_res.transcript}")
        if audio_res.clap_embedding:
            logger.info(f"音频 CLAP 向量维度: {len(audio_res.clap_embedding)}")
        logger.info(f"音频独立标签集: {audio_res.tags}")

    # 5. 跨媒体向量索引与推荐测试
    logger.info(f"\n--- [5] 跨媒体 (图/视/音) 渐进式索引与 Item-to-Item 推荐 ---")
    idx_img = progressive_indexer.index_file(img_path, MediaType.IMAGE)
    idx_vid = progressive_indexer.index_file(video_path, MediaType.VIDEO)
    idx_aud = progressive_indexer.index_file(extracted_audio_path, MediaType.AUDIO)

    logger.info(f"Indexed Image Point ID: {idx_img.item_id}")
    logger.info(f"Indexed Video Point ID: {idx_vid.item_id}")
    logger.info(f"Indexed Audio Point ID: {idx_aud.item_id}")

    rec_res = recommendation_engine.recommend_item_to_item(RecommendQuery(item_id=idx_img.item_id, top_k=3))
    logger.info(f"\n以图片 [{idx_img.item_id}] 为 Seed 的推荐结果:")
    for rec in rec_res.recommendations:
        logger.info(f"  -> 推荐项目 [{rec.item_id}] 得分={rec.score:.4f} 标题={rec.title} 类型={rec.media_type.value}")
        logger.info(f"     推荐理由: {rec.explanation}")

    logger.info("\n==================================================")
    logger.info("真实媒体 (图片、视频、独立音频) 实测全部成功完成！")

if __name__ == "__main__":
    main()
