import logging
import os
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("test_user_media")

from src.core.schemas import MediaType, RecommendQuery, SearchQuery
from src.services.image_service import image_service
from src.services.video_service import video_service
from src.pipeline.progressive_indexer import progressive_indexer
from src.engine.retrieval_engine import retrieval_engine
from src.engine.recommendation_engine import recommendation_engine
from src.vector_db.qdrant_client import vector_db_client

def main():
    img_path = "/Users/xiuxiuxiu/Desktop/multimodal-recommender/beauty_1755438760705.jpeg"
    video_path = "/Users/xiuxiuxiu/Desktop/multimodal-recommender/IMG_2514.MOV"

    logger.info("==================================================")
    logger.info("Testing Real User Media Files: Image & Video Analysis")
    logger.info("==================================================")

    # 1. Image Analysis
    if os.path.exists(img_path):
        logger.info(f"\n--- [1] Processing Image: {os.path.basename(img_path)} ---")
        start_t = time.time()
        img_result = image_service.process_image(img_path)
        img_elapsed = time.time() - start_t
        
        logger.info(f"Image MD5: {img_result.md5}")
        logger.info(f"Image Tags ({len(img_result.tags)}): {img_result.tags[:8]}")
        logger.info(f"Image Description: {img_result.description[:120]}...")
        logger.info(f"Image Vector Dimensions: {len(img_result.embedding) if img_result.embedding else 0}")
        logger.info(f"Processing Time: {img_elapsed:.2f}s")
        
        # Index image into vector store
        indexed_img = progressive_indexer.index_file(img_path, MediaType.IMAGE)
        logger.info(f"Indexed Image ID: {indexed_img.item_id}")
    else:
        logger.warning(f"Image file not found: {img_path}")

    # 2. Video Analysis
    if os.path.exists(video_path):
        logger.info(f"\n--- [2] Processing Video & Audio: {os.path.basename(video_path)} ---")
        start_t = time.time()
        video_result = video_service.process_video(video_path, extract_audio=True)
        video_elapsed = time.time() - start_t

        logger.info(f"Video MD5: {video_result.md5}")
        logger.info(f"Video Duration: {video_result.duration_sec:.1f}s")
        logger.info(f"Extracted Keyframes: {video_result.extracted_frames}")
        logger.info(f"Video Tags ({len(video_result.tags)}): {video_result.tags[:8]}")
        logger.info(f"Temporal Timeline Summaries: {len(video_result.frame_descriptions)} frame checkpoints")
        if video_result.audio_transcript:
            logger.info(f"Audio Transcript: {video_result.audio_transcript}")
        logger.info(f"Video Vector Dimensions: {len(video_result.embedding) if video_result.embedding else 0}")
        logger.info(f"Processing Time: {video_elapsed:.2f}s")

        # Index video into vector store
        indexed_vid = progressive_indexer.index_file(video_path, MediaType.VIDEO)
        logger.info(f"Indexed Video ID: {indexed_vid.item_id}")
    else:
        logger.warning(f"Video file not found: {video_path}")

    # 3. Multimodal Search & Item-to-Item Recommendation Test
    if os.path.exists(img_path):
        logger.info(f"\n--- [3] Multimodal Image-driven Search Test ---")
        search_res = retrieval_engine.search(SearchQuery(query_image_path=img_path, top_k=5))
        logger.info(f"Search Retrieved Hits: {len(search_res.results)}")
        for hit in search_res.results:
            logger.info(f"  Hit [{hit.item_id}] score={hit.score:.4f} title={hit.title} tags={hit.tags[:3]}")

        logger.info(f"\n--- [4] Item-to-Item Recommendation Test ---")
        img_item_id = f"item_{image_service.calculate_md5(img_path)[:12]}"
        rec_res = recommendation_engine.recommend_item_to_item(RecommendQuery(item_id=img_item_id, top_k=3))
        logger.info(f"Recommended Items Count: {len(rec_res.recommendations)}")
        for rec in rec_res.recommendations:
            logger.info(f"  Rec [{rec.item_id}] score={rec.score:.4f} title={rec.title}")
            logger.info(f"  {rec.explanation}")

    logger.info("\n==================================================")
    logger.info("Real User Media Test Execution Finished.")

if __name__ == "__main__":
    main()
