import os
import sys
import logging
from dataclasses import dataclass, field
from typing import Dict, Tuple

logger = logging.getLogger(__name__)

def find_model_path(subfolder: str, default_name: str) -> str:
    candidates = [
        f"backend/models/{subfolder}",
        f"models/{subfolder}",
        subfolder,
        f"../models/{subfolder}",
        f"../../models/{subfolder}"
    ]
    for cand in candidates:
        if os.path.exists(cand):
            return cand
    return default_name

def find_mlx_model_path() -> str:
    return find_model_path("mlx_model", "Qwen3-VL-8B-Instruct")

def find_embedding_model_path() -> str:
    return find_model_path("qwen3_vl_embedding_8b", "Qwen3-VL-Embedding-8B")

def find_reranker_model_path() -> str:
    return find_model_path("reranker_model", "Qwen3-VL-Reranker-2B")

def find_clap_model_path() -> str:
    return find_model_path("clap_model", "laion/clap-htsat-unfused")

@dataclass
class ModelInfo:
    model_id: str
    framework: str  # mlx-vlm, mlx-lm, transformers, llama.cpp
    memory_gb: float
    tier: str  # L0, L1, L2

@dataclass
class Settings:
    """
    [Node 1.1.1] Hardware Budget Constraints & Settings.
    Apple Silicon M5 (24GB Unified Memory) 精细化分配规范.
    """
    # Hardware & Memory Limits
    TOTAL_MEMORY_GB: float = 24.0
    SYSTEM_RESERVED_GB: float = 4.0
    MEMORY_LIMIT_GB: float = 20.0  # 24.0 - 4.0 GB hard budget
    L1_TTL_SECONDS: int = 300      # 5 minutes TTL for L1 hot cache

    # Model Registry & Defaults (All 6 Models Upgraded to L0 Permanent Resident Mode)
    MODELS: Dict[str, ModelInfo] = field(default_factory=lambda: {
        "vlm": ModelInfo(
            model_id=os.getenv("VLM_MODEL_ID", find_mlx_model_path()),
            framework="mlx-vlm",
            memory_gb=5.4,
            tier="L0"
        ),
        "embedding": ModelInfo(
            model_id=os.getenv("EMBEDDING_MODEL_ID", find_embedding_model_path()),
            framework="transformers",
            memory_gb=2.0,
            tier="L0"
        ),
        "llm": ModelInfo(
            model_id=os.getenv("LLM_MODEL_ID", "bonsai-8b-mlx"),
            framework="mlx-lm",
            memory_gb=1.3,
            tier="L0"
        ),
        "asr": ModelInfo(
            model_id=os.getenv("ASR_MODEL_ID", "Whisper-large-v3"),
            framework="transformers",
            memory_gb=0.7,
            tier="L0"
        ),
        "clap": ModelInfo(
            model_id=os.getenv("CLAP_MODEL_ID", find_clap_model_path()),
            framework="transformers",
            memory_gb=0.6,
            tier="L0"
        ),
        "reranker": ModelInfo(
            model_id=os.getenv("RERANKER_MODEL_ID", find_reranker_model_path()),
            framework="transformers",
            memory_gb=2.0,
            tier="L0"
        )
    })

    # Qdrant Vector DB Settings
    QDRANT_HOST: str = os.getenv("QDRANT_HOST", "localhost")
    QDRANT_PORT: int = int(os.getenv("QDRANT_PORT", "6333"))
    QDRANT_GRPC_PORT: int = int(os.getenv("QDRANT_GRPC_PORT", "6334"))
    QDRANT_COLLECTION: str = os.getenv("QDRANT_COLLECTION", "media_items")
    VECTOR_DIM: int = 2048
    MRL_TRUNCATED_DIMS: Tuple[int, ...] = (512, 128)

    # Storage & Cache Directories (Encapsulated inside backend/cache & backend/data)
    CACHE_DIR: str = os.getenv("CACHE_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "cache")))
    STORAGE_DIR: str = os.getenv("STORAGE_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data")))

    def validate_hardware_limits(self) -> bool:
        """Validate if system configuration adheres to safety limits."""
        l0_total = sum(m.memory_gb for m in self.MODELS.values() if m.tier == "L0")
        l1_max = max((m.memory_gb for m in self.MODELS.values() if m.tier == "L1"), default=0.0)
        if l0_total + l1_max > self.MEMORY_LIMIT_GB:
            logger.warning(f"Memory configuration exceeds limit: L0 ({l0_total}G) + max L1 ({l1_max}G) > {self.MEMORY_LIMIT_GB}G")
            return False
        logger.info(f"[Node 1.1.1 Validated] L0 Permanent={l0_total}GB, Memory Budget Cap={self.MEMORY_LIMIT_GB}GB OK.")
        return True

settings = Settings()
settings.validate_hardware_limits()
