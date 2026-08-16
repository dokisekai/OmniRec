import hashlib
import os
from abc import ABC
from typing import Any

from src.core.memory_manager import memory_manager

class BaseService(ABC):
    """
    [Node 3.1.1] Abstract Base Class for Independent Multimodal Services.
    Provides fast chunked MD5 content hashing & MemoryManager dependency injection.
    """

    def __init__(self):
        self.memory_manager = memory_manager

    @staticmethod
    def calculate_md5(file_path: str, chunk_size: int = 65536) -> str:
        """Calculate MD5 hash of a file for content-addressed deduplication."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found for MD5 calculation: {file_path}")
        
        md5_hash = hashlib.md5()
        with open(file_path, "rb") as f:
            while chunk := f.read(chunk_size):
                md5_hash.update(chunk)
        return md5_hash.hexdigest()
