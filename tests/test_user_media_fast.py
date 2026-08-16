import logging
import os
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("test_user_media_fast")

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

    # 1. Processing Image
    if os.path.exists(img_path):
        logger.info(f"\n--- [1] Analyzing Image File: {os.path.basename(img_path)} ---")
        img_md5 = image_service.calculate_md5(img_path)
        colors = image_service.extract_dominant_colors(img_path)
        vis_vec = image_service.extract_visual_feature_vector(img_path)
        
        logger.info(f"Image Path: {img_path}")
        logger.info(f"Image File Size: {os.path.getsize(img_path) / 1024 / 1024:.2f} MB")
        logger.info(f"Image Content MD5: {img_md5}")
        logger.info(f"Extracted Hex Dominant Colors: {colors}")
        logger.info(f"Visual Feature Vector (thumbnail_vector) Dim: {len(vis_vec)}")
        
        idx_img = progressive_indexer.index_file(img_path, MediaType.IMAGE)
        logger.info(f"Progressive L1/L2 Indexed ID: {idx_img.item_id}")
        logger.info(f"Indexed Tags ({len(idx_img.tags)}): {idx_img.tags[:6]}")
        logger.info(f"Indexed Description: {idx_img.description[:120]}...")

    # 2. Processing Video
    if os.path.exists(video_path):
        logger.info(f"\n--- [2] Analyzing Video File: {os.path.basename(video_path)} ---")
        vid_md5 = image_service.calculate_md5(video_path)
        vid_size_mb = os.path.getsize(video_path) / 1024 / 1024
        
        logger.info(f"Video Path: {video_path}")
        logger.info(f"Video File Size: {vid_size_mb:.2f} MB")
        logger.info(f"Video Content MD5: {vid_md5}")
        
        idx_vid = progressive_indexer.index_file(video_path, MediaType.VIDEO)
        logger.info(f"Progressive L1/L2 Indexed ID: {idx_vid.item_id}")
        logger.info(f"Indexed Tags ({len(idx_vid.tags)}): {idx_vid.tags[:6]}")
        logger.info(f"Indexed Description: {idx_vid.description[:120]}...")

    # 3. Multimodal Search & Item-to-Item Recommendation between the two items
    logger.info(f"\n--- [3] Multimodal Cross-Item Vector Search ---")
    search_res = retrieval_engine.search(SearchQuery(query_image_path=img_path, top_k=5))
    logger.info(f"Search Retrieved {len(search_res.results)} Hits")
    for hit in search_res.results:
        logger.info(f"  Hit [{hit.item_id}] Score={hit.score:.4f} Title={hit.title} Media={hit.media_type.value}")

    logger.info(f"\n--- [4] Item-to-Item Recommendation ---")
    img_item_id = f"item_{image_service.calculate_md5(img_path)[:12]}"
    rec_res = recommendation_engine.recommend_item_to_item(RecommendQuery(item_id=img_item_id, top_k=3))
    for rec in rec_res.recommendations:
        logger.info(f"  Rec [{rec.item_id}] Score={rec.score:.4f} Title={rec.title}")
        logger.info(f"  {rec.explanation}")

    logger.info("==================================================")
    logger.info("Real User Media Processing Completed Successfully.")

if __name__ == "__main__":
    main()
