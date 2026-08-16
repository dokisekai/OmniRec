import logging
import os
import json
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("test_real_user_files_fast")

from src.core.schemas import MediaType, RecommendQuery, SearchQuery
from src.pipeline.ffmpeg_utils import ffmpeg_utils
from src.services.image_service import image_service
from src.services.video_service import video_service
from src.services.audio_service import audio_service
from src.pipeline.progressive_indexer import progressive_indexer
from src.engine.recommendation_engine import recommendation_engine

def main():
    img_path = "/Users/xiuxiuxiu/Desktop/multimodal-recommender/test_files/beauty_1755438760705.jpeg"
    video_path = "/Users/xiuxiuxiu/Desktop/multimodal-recommender/test_files/IMG_2514.MOV"
    extracted_audio_path = "/Users/xiuxiuxiu/Desktop/multimodal-recommender/test_files/extracted_audio.wav"

    logger.info("==================================================")
    logger.info("真实文件实测: 图片 + 视频 + 分离独立音频")
    logger.info("==================================================")

    # 1. 视频音轨分离
    if os.path.exists(video_path):
        audio_file = ffmpeg_utils.extract_audio_track(video_path, extracted_audio_path)
        logger.info(f"► 成功从 [{os.path.basename(video_path)}] 中剥离提取出独立音频文件:")
        logger.info(f"  音频保存路径: {audio_file}")
        logger.info(f"  音频文件 MD5: {image_service.calculate_md5(audio_file)}")

    # 2. 真实图片实测
    if os.path.exists(img_path):
        img_md5 = image_service.calculate_md5(img_path)
        colors = image_service.extract_dominant_colors(img_path)
        vis_vec = image_service.extract_visual_feature_vector(img_path)
        img_res = image_service.process_image(img_path)

        logger.info(f"\n► 真实图片测试 [{os.path.basename(img_path)}]:")
        logger.info(f"  图片大小: {os.path.getsize(img_path) / 1024 / 1024:.2f} MB")
        logger.info(f"  MD5: {img_md5}")
        logger.info(f"  提取 Hex 主色调: {colors}")
        logger.info(f"  视觉向量 Dim: {len(vis_vec)}, L2范数={np.linalg.norm(vis_vec):.4f}")
        logger.info(f"  VLM 描述: {img_res.description}")
        logger.info(f"  提取 6 维结构化标签: {img_res.tags}")

    # 3. 真实视频实测
    if os.path.exists(video_path):
        vid_res = video_service.process_video(video_path, extract_audio=True)
        logger.info(f"\n► 真实视频测试 [{os.path.basename(video_path)}]:")
        logger.info(f"  视频大小: {os.path.getsize(video_path) / 1024 / 1024:.2f} MB")
        logger.info(f"  MD5: {vid_res.md5}")
        logger.info(f"  视频时长: {vid_res.duration_sec:.1f}s, 关键帧抽帧数: {vid_res.extracted_frames}")
        logger.info(f"  时序剧情 Checkpoints: {vid_res.frame_descriptions}")
        logger.info(f"  融合提取标签: {vid_res.tags}")

    # 4. 独立分离音频文件实测
    if os.path.exists(extracted_audio_path):
        audio_res = audio_service.process_audio(extracted_audio_path)
        logger.info(f"\n► 分离出的独立音频测试 [{os.path.basename(extracted_audio_path)}]:")
        logger.info(f"  MD5: {audio_res.md5}")
        logger.info(f"  VAD 语音/环境音分类判定: {audio_res.audio_type}")
        if audio_res.transcript:
            logger.info(f"  Whisper ASR 转写字幕: {audio_res.transcript}")
        if audio_res.clap_embedding:
            logger.info(f"  CLAP 嵌入向量 Dim: {len(audio_res.clap_embedding)}")
        logger.info(f"  音频独立标签集: {audio_res.tags}")

    # 5. 三通道 (图片/视频/独立音频) 向量库索引与 Cross-Item 推荐
    logger.info(f"\n► 跨通道 (图片/视频/音频) 索引与 Item-to-Item 推荐测试:")
    idx_img = progressive_indexer.index_file(img_path, MediaType.IMAGE)
    idx_vid = progressive_indexer.index_file(video_path, MediaType.VIDEO)
    idx_aud = progressive_indexer.index_file(extracted_audio_path, MediaType.AUDIO)

    rec_res = recommendation_engine.recommend_item_to_item(RecommendQuery(item_id=idx_img.item_id, top_k=3))
    logger.info(f"  以图片 [{idx_img.item_id}] 为 Seed 推荐项目数: {len(rec_res.recommendations)}")
    for rec in rec_res.recommendations:
        logger.info(f"    - 推荐项目 [{rec.item_id}] 得分={rec.score:.4f} 类型={rec.media_type.value} 理由: {rec.explanation}")

    logger.info("\n==================================================")
    logger.info("真实文件 (图片 + 视频 + 分离独立音频) 实测全部成功完成！")

if __name__ == "__main__":
    main()
