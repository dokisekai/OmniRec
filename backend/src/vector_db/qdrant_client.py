import logging
import os
from typing import Any, Dict, List, Optional
import numpy as np

from src.core.config import settings
from src.core.schemas import IndexResult, MediaType

logger = logging.getLogger(__name__)


class VectorDBClient:
    """
    [Node 3.5.1] Production-grade Vector Database Client with Qdrant & Resilient Fallback.
    Supports:
    - Multi-tenancy isolation via indexed `tenant_id` payload filters.
    - Strict `is_vectorized` eligibility validation for recommendations and search.
    - Dynamic candidate subset filtering (`candidate_item_ids`).
    - 2048d Dense Semantic Vectors (content_vector, thumbnail_vector) & 512d Audio Vectors.
    - HNSW + INT8 Scalar Quantization for sub-millisecond retrieval.
    """

    def __init__(self, collection_name: str = "media_items"):
        self.collection_name = collection_name
        self.client = None
        self._is_qdrant_live = False
        self._local_store: Dict[str, IndexResult] = {}
        self.connect()

    def connect(self):
        try:
            from qdrant_client import QdrantClient
            self.client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT, timeout=2.5)
            self.client.get_collections()
            self._is_qdrant_live = True
            logger.info(f"Connected to live Qdrant server at {settings.QDRANT_HOST}:{settings.QDRANT_PORT}")
            self.init_collection()
        except Exception as e:
            logger.warning(f"Could not connect to Qdrant server ({e}). Operating in resilient In-Memory Vector Store mode.")
            self._is_qdrant_live = False

    def init_collection(self):
        if not self._is_qdrant_live or self.client is None:
            return
        try:
            from qdrant_client.models import (
                VectorParams, Distance, HnswConfigDiff,
                ScalarQuantization, ScalarQuantizationConfig, ScalarType,
                PayloadSchemaType
            )
            collections = [c.name for c in self.client.get_collections().collections]
            if self.collection_name not in collections:
                logger.info(f"Creating Qdrant collection [{self.collection_name}] with named vectors & HNSW INT8...")
                vectors_config = {
                    "content_vector": VectorParams(size=settings.VECTOR_DIM, distance=Distance.COSINE),
                    "audio_vector": VectorParams(size=512, distance=Distance.COSINE),
                    "thumbnail_vector": VectorParams(size=settings.VECTOR_DIM, distance=Distance.COSINE),
                }
                hnsw_config = HnswConfigDiff(m=16, ef_construct=64)
                quantization_config = ScalarQuantization(
                    scalar=ScalarQuantizationConfig(
                        type=ScalarType.INT8, quantile=0.99, always_ram=True
                    )
                )
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=vectors_config,
                    hnsw_config=hnsw_config,
                    quantization_config=quantization_config
                )
                logger.info(f"Collection [{self.collection_name}] created successfully.")

            # Create payload indices for fast multi-tenant isolation & vectorization filtering
            try:
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="tenant_id",
                    field_schema=PayloadSchemaType.KEYWORD
                )
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="is_vectorized",
                    field_schema=PayloadSchemaType.BOOL
                )
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="media_type",
                    field_schema=PayloadSchemaType.KEYWORD
                )
            except Exception as e:
                logger.debug(f"Payload index creation note: {e}")

        except Exception as e:
            logger.error(f"Failed to initialize Qdrant collection: {e}")

    def upsert_item(self, item: IndexResult) -> bool:
        """Upsert a multi-modal index result into vector store with tenant isolation."""
        tenant_id = getattr(item, "tenant_id", "default") or "default"
        is_vec = bool(
            getattr(item, "is_vectorized", True) and
            (item.content_vector is not None or item.thumbnail_vector is not None or item.audio_vector is not None)
        )
        item.is_vectorized = is_vec
        item.tenant_id = tenant_id

        # Always update local store
        self._local_store[item.item_id] = item
        logger.info(f"[VectorDB] Upserted item_id={item.item_id} (tenant={tenant_id}, is_vectorized={is_vec})")

        if self._is_qdrant_live and self.client:
            try:
                from qdrant_client.models import PointStruct
                vectors = {}
                if item.content_vector:
                    vectors["content_vector"] = item.content_vector
                if item.audio_vector:
                    vectors["audio_vector"] = item.audio_vector
                if item.thumbnail_vector:
                    vectors["thumbnail_vector"] = item.thumbnail_vector

                payload = {
                    "item_id": item.item_id,
                    "tenant_id": tenant_id,
                    "media_type": item.media_type.value if hasattr(item.media_type, "value") else str(item.media_type),
                    "file_path": item.file_path,
                    "md5": item.md5,
                    "title": item.title,
                    "description": item.description,
                    "tags": item.tags,
                    "is_vectorized": is_vec,
                    "indexed_at": item.indexed_at,
                }
                
                point_id = abs(hash(f"{tenant_id}_{item.item_id}")) % (2**63)
                self.client.upsert(
                    collection_name=self.collection_name,
                    points=[PointStruct(id=point_id, vector=vectors, payload=payload)]
                )
                logger.info(f"[VectorDB] Point {point_id} synced to Qdrant (tenant={tenant_id}).")
            except Exception as e:
                logger.error(f"Qdrant upsert failed: {e}")
        return True

    def get_item_by_id(self, item_id: str, tenant_id: Optional[str] = None) -> Optional[IndexResult]:
        item = self._local_store.get(item_id)
        if item is not None:
            if tenant_id and getattr(item, "tenant_id", "default") != tenant_id:
                return None
            return item

        # If not in memory, query Qdrant directly
        if self._is_qdrant_live and self.client:
            try:
                tid = tenant_id or "default"
                point_id = abs(hash(f"{tid}_{item_id}")) % (2**63)
                records = self.client.retrieve(collection_name=self.collection_name, ids=[point_id], with_payload=True)
                if records:
                    p = records[0].payload or {}
                    if tenant_id and p.get("tenant_id") != tenant_id:
                        return None
                    return IndexResult(
                        item_id=p.get("item_id", item_id),
                        tenant_id=p.get("tenant_id", "default"),
                        media_type=MediaType(p.get("media_type", "image")),
                        file_path=p.get("file_path", ""),
                        md5=p.get("md5", ""),
                        title=p.get("title", ""),
                        description=p.get("description", ""),
                        tags=p.get("tags", []),
                        is_vectorized=p.get("is_vectorized", True),
                        indexed_at=p.get("indexed_at", 0.0)
                    )
            except Exception as e:
                logger.debug(f"Qdrant retrieve error: {e}")
        return None

    def search_similar(
        self,
        query_vector: List[float],
        vector_name: str = "content_vector",
        tenant_id: str = "default",
        only_vectorized: bool = True,
        candidate_item_ids: Optional[List[str]] = None,
        filter_tags: Optional[List[str]] = None,
        filter_media_type: Optional[str] = None,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Multi-tenant isolated vector search with strict vectorization eligibility.
        """
        results = []
        target_tenant = tenant_id or "default"

        if self._is_qdrant_live and self.client:
            try:
                from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny

                must_conditions = [
                    FieldCondition(key="tenant_id", match=MatchValue(value=target_tenant))
                ]
                if only_vectorized:
                    must_conditions.append(FieldCondition(key="is_vectorized", match=MatchValue(value=True)))
                if filter_media_type:
                    must_conditions.append(FieldCondition(key="media_type", match=MatchValue(value=filter_media_type)))
                if candidate_item_ids:
                    must_conditions.append(FieldCondition(key="item_id", match=MatchAny(any=candidate_item_ids)))

                query_filter = Filter(must=must_conditions)

                if hasattr(self.client, "query_points"):
                    query_res = self.client.query_points(
                        collection_name=self.collection_name,
                        query=query_vector,
                        using=vector_name,
                        query_filter=query_filter,
                        limit=top_k
                    )
                    points = query_res.points
                else:
                    points = self.client.search(
                        collection_name=self.collection_name,
                        query_vector=(vector_name, query_vector),
                        query_filter=query_filter,
                        limit=top_k
                    )

                for hit in points:
                    payload = hit.payload or {}
                    # Tag filtering if specified
                    if filter_tags and not any(tag in payload.get("tags", []) for tag in filter_tags):
                        continue
                    results.append({
                        "item_id": payload.get("item_id") or str(hit.id),
                        "tenant_id": payload.get("tenant_id", target_tenant),
                        "score": float(hit.score),
                        "is_vectorized": payload.get("is_vectorized", True),
                        "payload": payload
                    })
                return results
            except Exception as e:
                logger.warning(f"Qdrant live search with tenant filter failed: {e}. Using in-memory fallback.")

        # In-memory fallback cosine search with strict tenant & vectorization isolation
        q_vec = np.array(query_vector)
        q_norm = np.linalg.norm(q_vec) + 1e-9

        scored_items = []
        for item_id, item in self._local_store.items():
            # 1. Multi-tenant isolation filter
            if getattr(item, "tenant_id", "default") != target_tenant:
                continue

            # 2. Only vectorized filter
            if only_vectorized and not getattr(item, "is_vectorized", True):
                continue

            # 3. Candidate subset filter
            if candidate_item_ids and item.item_id not in candidate_item_ids:
                continue

            # 4. Media type filter
            if filter_media_type:
                mt_val = item.media_type.value if hasattr(item.media_type, "value") else str(item.media_type)
                if mt_val != filter_media_type:
                    continue

            # 5. Tag filter
            if filter_tags and not any(tag in item.tags for tag in filter_tags):
                continue

            target_vec = item.content_vector if vector_name == "content_vector" else (item.audio_vector or item.thumbnail_vector or item.content_vector)
            if not target_vec:
                continue

            t_vec = np.array(target_vec)
            min_dim = min(len(q_vec), len(t_vec))
            sim = float(np.dot(q_vec[:min_dim], t_vec[:min_dim]) / (np.linalg.norm(q_vec[:min_dim]) * np.linalg.norm(t_vec[:min_dim]) + 1e-9))
            
            scored_items.append({
                "item_id": item.item_id,
                "tenant_id": target_tenant,
                "score": sim,
                "is_vectorized": getattr(item, "is_vectorized", True),
                "payload": {
                    "item_id": item.item_id,
                    "tenant_id": target_tenant,
                    "media_type": item.media_type.value if hasattr(item.media_type, "value") else str(item.media_type),
                    "file_path": item.file_path,
                    "title": item.title,
                    "description": item.description,
                    "tags": item.tags,
                    "is_vectorized": getattr(item, "is_vectorized", True)
                }
            })

        scored_items.sort(key=lambda x: x["score"], reverse=True)
        return scored_items[:top_k]

    def list_all_items(self, tenant_id: Optional[str] = None) -> List[IndexResult]:
        """Return list of all indexed media items, optionally filtered by tenant."""
        items = list(self._local_store.values())
        if tenant_id:
            items = [it for it in items if getattr(it, "tenant_id", "default") == tenant_id]
        return items

    def delete_item(self, item_id: str, tenant_id: str = "default") -> bool:
        """Delete an item from vector DB."""
        if item_id in self._local_store:
            del self._local_store[item_id]
            logger.info(f"[VectorDB] Deleted item_id={item_id} from local store.")
        if self._is_qdrant_live and self.client:
            try:
                point_id = abs(hash(f"{tenant_id}_{item_id}")) % (2**63)
                self.client.delete(collection_name=self.collection_name, points_selector=[point_id])
            except Exception as e:
                logger.error(f"Failed to delete {item_id} from Qdrant: {e}")
        return True


vector_db_client = VectorDBClient()
