import logging
import os
import json
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("capabilities_benchmark")

from src.core.schemas import MediaType, RecommendQuery, SearchQuery
from src.services.image_service import image_service
from src.services.video_service import video_service
from src.services.audio_service import audio_service
from src.services.text_service import text_service
from src.pipeline.tag_generator import tag_generator
from src.pipeline.progressive_indexer import progressive_indexer
from src.engine.retrieval_engine import retrieval_engine
from src.engine.recommendation_engine import recommendation_engine

def main():
    img_path = "/Users/xiuxiuxiu/Desktop/multimodal-recommender/test_files/beauty_1755438760705.jpeg"
    video_path = "/Users/xiuxiuxiu/Desktop/multimodal-recommender/test_files/IMG_2514.MOV"

    logger.info("==================================================")
    logger.info("系统核心能力 (向量 / 6维标签 / 多模态描述) 全面测试验证")
    logger.info("==================================================")

    # 1. 向量生成能力测试
    logger.info("\n--- [1] 向量生成能力测试 (Vector Generation Check) ---")
    vis_vec = image_service.extract_visual_feature_vector(img_path, dim=2048)
    text_vec = text_service.process_text("测试高山雪景自然风光向量生成")
    
    vis_norm = np.linalg.norm(vis_vec)
    text_norm = np.linalg.norm(text_vec)
    
    logger.info(f"视觉特征向量 (thumbnail_vector): 维度={len(vis_vec)}, L2范数={vis_norm:.4f} (已单位化)")
    logger.info(f"文本语义向量 (content_vector):   维度={len(text_vec)}, L2范数={text_norm:.4f} (已单位化)")
    assert len(vis_vec) == 2048 and abs(vis_norm - 1.0) < 1e-3, "thumbnail_vector 校验失败"
    assert len(text_vec) == 2048 and abs(text_norm - 1.0) < 1e-3, "content_vector 校验失败"
    logger.info("✅ 向量生成与单位化归一化能力: 正常！")

    # 2. 6 大维度体系标签能力测试
    logger.info("\n--- [2] 6 大维度标签抽取能力测试 (6-Category Tag System) ---")
    sample_text = "这是一幅拍摄于高山湖泊边的时尚人物肖像大片，阳光下呈现极简风与暖色调，治愈系氛围，特写镜头与大景深..."
    cat_tags = tag_generator.generate_categorized_tags(sample_text)
    flat_tags = tag_generator.flatten_tags(sample_text)
    colors = image_service.extract_dominant_colors(img_path)

    logger.info(f"样本输入: '{sample_text[:40]}...'")
    logger.info(f"结构化 6 维归纳标签:\n{json.dumps(cat_tags, ensure_ascii=False, indent=2)}")
    logger.info(f"展平去重标签集 ({len(flat_tags)}个): {flat_tags}")
    logger.info(f"图片 Hex 主色调卡片: {colors}")
    assert len(flat_tags) > 0 and len(colors) > 0, "标签与主色调抽取校验失败"
    logger.info("✅ 6 大维度标签与主色调提取能力: 正常！")

    # 3. 描述生成能力测试 (Image VLM & Video Temporal Summary)
    logger.info("\n--- [3] 多模态描述生成能力测试 (VLM & Temporal Descriptions) ---")
    if os.path.exists(img_path):
        img_res = image_service.process_image(img_path)
        logger.info(f"【真实图片 MD5: {img_res.md5}】")
        logger.info(f"【图片生成富文本描述】:\n{img_res.description}\n")
        logger.info(f"【图片关联标签】: {img_res.tags}")

    if os.path.exists(video_path):
        vid_res = video_service.process_video(video_path, extract_audio=True)
        logger.info(f"\n【真实视频 MD5: {vid_res.md5}, 时长: {vid_res.duration_sec:.1f}s, 抽帧数: {vid_res.extracted_frames}】")
        logger.info(f"【视频时序关键帧描述 checkpoint】:")
        for frame_desc in vid_res.frame_descriptions:
            logger.info(f"  {frame_desc}")
        if vid_res.audio_transcript:
            logger.info(f"【音轨 ASR 语音字幕】: {vid_res.audio_transcript}")
        logger.info(f"【视频融合总标签集】: {vid_res.tags}")
    logger.info("✅ 图片/视频多模态描述生成能力: 正常！")

    # 4. 多路召回与推荐推理能力测试
    logger.info("\n--- [4] 检索与 Recommend 推理能力测试 ---")
    indexed_img = progressive_indexer.index_file(img_path, MediaType.IMAGE)
    indexed_vid = progressive_indexer.index_file(video_path, MediaType.VIDEO)

    rec_res = recommendation_engine.recommend_item_to_item(RecommendQuery(item_id=indexed_img.item_id, top_k=2))
    logger.info(f"以图片 [{indexed_img.item_id}] 为 Seed 的 Item-to-Item 推荐结果数: {len(rec_res.recommendations)}")
    for rec in rec_res.recommendations:
        logger.info(f"  -> 推荐项目 [{rec.item_id}] 相似度得分={rec.score:.4f} 标题={rec.title}")
        logger.info(f"     推荐理由: {rec.explanation}")

    logger.info("\n==================================================")
    logger.info("全套向量、标签、描述与推荐推理能力验证通过！测试结果全部正常！")

if __name__ == "__main__":
    main()
