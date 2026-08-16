"""
Vector DB package: Qdrant client wrapper and schema management.
"""
from src.vector_db.qdrant_client import VectorDBClient, vector_db_client

__all__ = ["VectorDBClient", "vector_db_client"]
