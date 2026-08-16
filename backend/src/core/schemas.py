import time
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class ModelModality(str, Enum):
    VLM = "vlm"
    EMBEDDING = "embedding"
    LLM = "llm"
    ASR = "asr"
    CLAP = "clap"
    RERANKER = "reranker"

class MemoryTier(str, Enum):
    L0 = "L0"  # Permanent
    L1 = "L1"  # Hot cache (5 min TTL)
    L2 = "L2"  # Cold load (unload immediately)

class MediaType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    TEXT = "text"

# --- [Node 1.2.1] Analysis Models ---

class ImageAnalysisResult(BaseModel):
    image_path: str = Field(description="Local path to image file")
    md5: str = Field(description="Content-addressed MD5 hash")
    description: str = Field(default="", description="VLM generated rich-text description")
    tags: List[str] = Field(default_factory=list, description="Categorized tags")
    embedding: Optional[List[float]] = Field(default=None, description="2048-dim text embedding vector")
    processed_at: float = Field(default_factory=time.time)

class VideoAnalysisResult(BaseModel):
    video_path: str = Field(description="Local path to video file")
    md5: str = Field(description="Content-addressed MD5 hash")
    duration_sec: float = Field(default=0.0, description="Video duration in seconds")
    extracted_frames: int = Field(default=0, description="Number of extracted keyframes")
    frame_descriptions: List[str] = Field(default_factory=list, description="Temporal frame descriptions")
    audio_transcript: Optional[str] = Field(default=None, description="ASR speech transcript")
    tags: List[str] = Field(default_factory=list, description="Categorized video tags")
    embedding: Optional[List[float]] = Field(default=None, description="Multi-track pooled embedding vector")
    processed_at: float = Field(default_factory=time.time)

class AudioAnalysisResult(BaseModel):
    audio_path: str = Field(description="Local path to audio file")
    md5: str = Field(description="Content-addressed MD5 hash")
    duration_sec: float = Field(default=0.0, description="Audio duration in seconds")
    audio_type: str = Field(default="voice", description="Audio type: voice, music, ambient")
    transcript: Optional[str] = Field(default=None, description="ASR transcript")
    clap_embedding: Optional[List[float]] = Field(default=None, description="512-dim CLAP audio vector")
    tags: List[str] = Field(default_factory=list, description="Audio tags")
    embedding: Optional[List[float]] = Field(default=None, description="Text embedding vector")
    processed_at: float = Field(default_factory=time.time)

class IndexResult(BaseModel):
    item_id: str = Field(description="Unique point ID")
    tenant_id: str = Field(default="default", description="Multi-tenant isolation identifier")
    media_type: MediaType = Field(description="Media modality type")
    file_path: str = Field(description="Path to target media file")
    md5: str = Field(description="File MD5 hash")
    title: str = Field(default="", description="Media title/filename")
    description: str = Field(default="", description="Unified multi-modal description")
    tags: List[str] = Field(default_factory=list, description="Associated tags")
    is_vectorized: bool = Field(default=True, description="True if valid dense vectors have been extracted")
    content_vector: Optional[List[float]] = Field(default=None, description="Primary semantic vector (2048-dim)")
    audio_vector: Optional[List[float]] = Field(default=None, description="Audio vector (512-dim)")
    thumbnail_vector: Optional[List[float]] = Field(default=None, description="Visual feature vector (2048-dim)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Payload metadata")
    indexed_at: float = Field(default_factory=time.time)

# --- Search & Recommendation Models ---

class SearchQuery(BaseModel):
    tenant_id: str = Field(default="default", description="Multi-tenant isolation identifier")
    query_text: Optional[str] = Field(default=None, description="Text query string")
    query_image_path: Optional[str] = Field(default=None, description="Image query file path")
    query_audio_path: Optional[str] = Field(default=None, description="Audio query file path")
    filter_tags: List[str] = Field(default_factory=list, description="Tags for payload filtering")
    filter_media_type: Optional[MediaType] = Field(default=None, description="Media type filter")
    only_vectorized: bool = Field(default=True, description="Only search items with valid generated vectors")
    top_k: int = Field(default=10, ge=1, le=100, description="Top-K results count")
    enable_rerank: bool = Field(default=True)
    enable_explanation: bool = Field(default=True)

class SearchResultItem(BaseModel):
    item_id: str
    tenant_id: str = "default"
    score: float
    media_type: MediaType
    file_path: str
    title: str = ""
    description: str = ""
    tags: List[str] = Field(default_factory=list)
    is_vectorized: bool = True
    explanation: Optional[str] = None

class SearchResult(BaseModel):
    query: SearchQuery
    results: List[SearchResultItem] = Field(default_factory=list)
    total: int = 0
    latency_ms: float = 0.0

class RecommendQuery(BaseModel):
    item_id: str = Field(description="Seed item ID for Item-to-Item recommendation")
    tenant_id: str = Field(default="default", description="Multi-tenant isolation identifier")
    candidate_item_ids: Optional[List[str]] = Field(default=None, description="Optional restricted candidate subset IDs")
    only_vectorized: bool = Field(default=True, description="Only recommend items with completed vector embeddings")
    top_k: int = Field(default=10, ge=1, le=100)
    enable_rerank: bool = Field(default=True)
    enable_explanation: bool = Field(default=True)

class RecommendResult(BaseModel):
    seed_item_id: str
    tenant_id: str = "default"
    recommendations: List[SearchResultItem] = Field(default_factory=list)
    latency_ms: float = 0.0
    message: Optional[str] = None
