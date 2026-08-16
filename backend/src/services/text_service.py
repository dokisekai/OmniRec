import logging
from typing import List

from src.core.schemas import ModelModality
from src.models.embedding import EmbeddingWrapper
from src.pipeline.tag_generator import tag_generator
from src.services.base_service import BaseService

logger = logging.getLogger(__name__)

class TextService(BaseService):
    """
    [Node 3.5.1] Independent Text Service.
    Handles text cleaning, tokenization, 6-category taxonomy tag extraction, and dense text embedding generation.
    """

    def process_text(self, text: str) -> List[float]:
        cleaned_text = text.strip()
        logger.info(f"[TextService] Vectorizing text: '{cleaned_text[:30]}...'")
        embedding_model: EmbeddingWrapper = self.memory_manager.load_model(
            ModelModality.EMBEDDING,
            loader_fn=lambda: EmbeddingWrapper()
        )
        embeddings = embedding_model.predict([cleaned_text])
        return embeddings[0] if embeddings else []

    def extract_tags(self, text: str) -> List[str]:
        """Extract structured tags via TagGenerator."""
        return tag_generator.flatten_tags(text)

text_service = TextService()
