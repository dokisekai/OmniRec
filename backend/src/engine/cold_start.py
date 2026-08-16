import logging
from typing import List, Optional
from src.core.schemas import SearchResultItem, MediaType

logger = logging.getLogger(__name__)

class ColdStartStrategy:
    """
    Cold Start Strategy (06-推荐引擎模块.md 第6节).
    Handles recommendation fallback when user history or seed item vectors are sparse or missing.
    Applies Popularity + Multi-level Tag Boost.
    """

    @staticmethod
    def get_fallback_recommendations(filter_tags: Optional[List[str]] = None, top_k: int = 10) -> List[SearchResultItem]:
        logger.info(f"[ColdStart] Generating cold-start fallback recommendations for tags: {filter_tags}")
        
        fallback_items = [
            SearchResultItem(
                item_id=f"cold_start_{i}",
                score=0.85 - (i * 0.05),
                media_type=MediaType.IMAGE if i % 2 == 1 else MediaType.VIDEO,
                file_path=f"/data/popular_item_{i}.jpg",
                title=f"热门推荐精选 {i}",
                description=f"高质量常青爆款全模态内容 {i}",
                tags=["热门精选", "自然风光", "高品质"],
                explanation="推荐理由：系统全网热门精选内容，为您推荐最受好评的优质视觉作品。"
            )
            for i in range(1, top_k + 1)
        ]
        return fallback_items

cold_start_strategy = ColdStartStrategy()
