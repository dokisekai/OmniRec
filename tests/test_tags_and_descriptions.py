import logging
import os
import json

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("test_tags_and_desc")

from src.pipeline.tag_generator import tag_generator
from src.services.image_service import image_service
from src.services.video_service import video_service
from src.services.text_service import text_service

def main():
    img_path = "/Users/xiuxiuxiu/Desktop/multimodal-recommender/beauty_1755438760705.jpeg"
    video_path = "/Users/xiuxiuxiu/Desktop/multimodal-recommender/IMG_2514.MOV"

    logger.info("==================================================")
    logger.info("测试标签提取功能与描述生成功能 (6大分类标签体系)")
    logger.info("==================================================")

    # 1. Test Tag Generator Taxonomy Extraction on rich sample texts
    sample_texts = [
        "这是一幅拍摄于高山湖泊边的时尚人物肖像，阳光照耀下呈现极简风与暖色调，画面洋溢着治愈系氛围，采用了大景深的特写镜头拍摄数码单反大片。",
        "视频记录了赛博朋克风格的都市夜景与跑车飞驰的画面，热血激情的音效配合对称构图的航拍视角。",
        "二次元动漫插画风的森林星空插画，浪漫唯美的冷色调烘托神秘深沉的情绪。"
    ]

    logger.info("\n--- [1] 测试 6 大维度体系标签提取器 (Subject/ColorStyle/Scene/Emotion/Composition/Entity) ---")
    for i, sample in enumerate(sample_texts, start=1):
        categorized = tag_generator.generate_categorized_tags(sample)
        flat = tag_generator.flatten_tags(sample)
        logger.info(f"\n[文本样本 {i}]: {sample[:45]}...")
        logger.info(f"  结构化 6 维标签: {json.dumps(categorized, ensure_ascii=False)}")
        logger.info(f"  展平去重标签集 ({len(flat)}个): {flat}")

    # 2. Test Image Tags & VLM Description on real user image (beauty_1755438760705.jpeg)
    if os.path.exists(img_path):
        logger.info(f"\n--- [2] 测试真实图片描述与标签生成: {os.path.basename(img_path)} ---")
        img_res = image_service.process_image(img_path)
        logger.info(f"图片生成的描述:\n{img_res.description}\n")
        logger.info(f"图片提取的标签: {img_res.tags}")

    # 3. Test Video Temporal Descriptions & Tags on real user video (IMG_2514.MOV)
    if os.path.exists(video_path):
        logger.info(f"\n--- [3] 测试真实视频时序剧情描述与标签生成: {os.path.basename(video_path)} ---")
        vid_res = video_service.process_video(video_path, extract_audio=True)
        logger.info(f"视频抽帧与时序总结:")
        for frame_desc in vid_res.frame_descriptions:
            logger.info(f"  {frame_desc}")
        if vid_res.audio_transcript:
            logger.info(f"  原声语音字幕: {vid_res.audio_transcript}")
        logger.info(f"视频融合提取的总标签集: {vid_res.tags}")

    logger.info("==================================================")
    logger.info("标签功能与描述生成功能测试完成！")

if __name__ == "__main__":
    main()
