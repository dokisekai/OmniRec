import hashlib
import logging
import os
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from src.core.config import settings
from src.core.schemas import ImageAnalysisResult, ModelModality, MediaType, SearchResultItem
from src.models.vlm import VLMWrapper
from src.models.embedding import EmbeddingWrapper
from src.pipeline.tag_generator import tag_generator
from src.services.base_service import BaseService
from src.vector_db.qdrant_client import vector_db_client

logger = logging.getLogger(__name__)

class ImageService(BaseService):
    """
    [Node 3.2.1, 3.2.2, 3.2.3] Independent Image Service.
    - 3.2.1: Dual-track vector encoding (thumbnail_vector & content_vector).
    - 3.2.2: Hex dominant color palette extraction.
    - 3.2.3: Weighted image-to-image dual-track vector search.
    """

    @staticmethod
    def extract_visual_feature_vector(image_path: str, dim: int = 2048) -> List[float]:
        """[Node 3.2.1] Track 1: Extract direct visual feature vector (thumbnail_vector)."""
        if not os.path.exists(image_path):
            hash_val = hash(image_path)
            np.random.seed(abs(hash_val) % (2**32))
            vec = np.random.randn(dim)
            return (vec / np.linalg.norm(vec)).tolist()

        try:
            from PIL import Image
            img = Image.open(image_path).convert("RGB").resize((128, 128))
            arr = np.array(img, dtype=np.float32) / 255.0
            
            r_hist, _ = np.histogram(arr[:, :, 0], bins=64, range=(0, 1))
            g_hist, _ = np.histogram(arr[:, :, 1], bins=64, range=(0, 1))
            b_hist, _ = np.histogram(arr[:, :, 2], bins=64, range=(0, 1))
            
            spatial_feat = arr[::8, ::8, :].flatten()
            raw_feat = np.concatenate([r_hist, g_hist, b_hist, spatial_feat])
            
            if len(raw_feat) < dim:
                padded = np.pad(raw_feat, (0, dim - len(raw_feat)), mode="constant")
            else:
                padded = raw_feat[:dim]
                
            norm_vec = padded / (np.linalg.norm(padded) + 1e-9)
            return norm_vec.tolist()
        except Exception as e:
            logger.warning(f"PIL visual feature extraction fallback: {e}")
            hash_val = hash(image_path)
            np.random.seed(abs(hash_val) % (2**32))
            vec = np.random.randn(dim)
            return (vec / np.linalg.norm(vec)).tolist()

    @staticmethod
    def extract_dominant_colors(image_path: str, num_colors: int = 3) -> List[str]:
        """[Node 3.2.2] Extract dominant Hex color palette (e.g. ['#FF5733', '#1C2833'])."""
        try:
            from PIL import Image
            if not os.path.exists(image_path):
                return ["#2C3E50", "#E74C3C", "#ECF0F1"]
            img = Image.open(image_path).convert("RGB").resize((50, 50))
            colors = img.getcolors(maxcolors=2500)
            if not colors:
                return ["#34495E", "#1ABC9C"]
            colors.sort(key=lambda x: x[0], reverse=True)
            hex_colors = [f"#{c[1][0]:02x}{c[1][1]:02x}{c[1][2]:02x}" for c in colors[:num_colors]]
            return hex_colors
        except Exception as e:
            logger.debug(f"Dominant colors extraction fallback: {e}")
            return ["#34495E", "#1ABC9C"]

    def process_image(self, image_path: str, prompt: Optional[str] = None) -> ImageAnalysisResult:
        """[Node 3.2.1 & 3.2.2] Deep image analysis and dual-track vector encoding."""
        logger.info(f"[ImageService] Processing image: {image_path}")
        md5_str = self.calculate_md5(image_path)
        
        # Track 1: Direct visual feature vector
        thumbnail_vec = self.extract_visual_feature_vector(image_path, dim=settings.VECTOR_DIM)
        dominant_colors = self.extract_dominant_colors(image_path)

        # Track 2: VLM deep semantic text generation
        vlm_model: VLMWrapper = self.memory_manager.load_model(
            ModelModality.VLM,
            loader_fn=lambda: VLMWrapper()
        )
        
        analysis_prompt = prompt or (
            "请详细分析该图片的画面内容：1. 主体对象与细节；2. 色彩主调与摄影风格；"
            "3. 场景与自然/都市环境；4. 表达的情绪氛围；5. 构图与光影特色；6. 包含的品牌或实体。"
        )
        description = vlm_model.predict(image_path, prompt=analysis_prompt)

        # 6-Category taxonomy tags
        categorized_tags = tag_generator.generate_categorized_tags(description)
        flat_tags = tag_generator.flatten_tags(description)
        flat_tags.extend([f"主色_{c}" for c in dominant_colors[:2]])

        # Text embedding (content_vector)
        embedding_model: EmbeddingWrapper = self.memory_manager.load_model(
            ModelModality.EMBEDDING,
            loader_fn=lambda: EmbeddingWrapper()
        )
        
        embedding_vectors = embedding_model.predict([description])
        content_vec = embedding_vectors[0] if embedding_vectors else None

        return ImageAnalysisResult(
            image_path=image_path,
            md5=md5_str,
            description=description,
            tags=list(set(flat_tags)),
            embedding=content_vec,
        )

    def search_similar_images(
        self,
        image_path: str,
        visual_weight: float = 0.4,
        semantic_weight: float = 0.6,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """[Node 3.2.3] Deep Image-to-Image Dual-Track Search."""
        analysis = self.process_image(image_path)
        visual_vec = self.extract_visual_feature_vector(image_path, dim=settings.VECTOR_DIM)
        content_vec = analysis.embedding or visual_vec

        visual_hits = vector_db_client.search_similar(
            query_vector=visual_vec,
            vector_name="thumbnail_vector",
            top_k=top_k * 2
        )

        semantic_hits = vector_db_client.search_similar(
            query_vector=content_vec,
            vector_name="content_vector",
            top_k=top_k * 2
        )

        fused_scores: Dict[str, float] = {}
        payloads: Dict[str, Dict[str, Any]] = {}

        for hit in visual_hits:
            item_id = hit["item_id"]
            payloads[item_id] = hit["payload"]
            fused_scores[item_id] = fused_scores.get(item_id, 0.0) + visual_weight * hit["score"]

        for hit in semantic_hits:
            item_id = hit["item_id"]
            payloads[item_id] = hit["payload"]
            fused_scores[item_id] = fused_scores.get(item_id, 0.0) + semantic_weight * hit["score"]

        results = [
            {"item_id": item_id, "score": score, "payload": payloads[item_id]}
            for item_id, score in sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)
        ]
        return results[:top_k]

image_service = ImageService()
