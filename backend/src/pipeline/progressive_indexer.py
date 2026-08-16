import logging
import os
import time
from typing import Dict, List, Optional

from src.cache.cache_manager import cache_manager
from src.core.schemas import IndexResult, MediaType
from src.core.status_broadcaster import status_broadcaster
from src.services.base_service import BaseService
from src.services.image_service import image_service
from src.services.video_service import video_service
from src.services.audio_service import audio_service
from src.pipeline.tag_generator import tag_generator
from src.vector_db.qdrant_client import vector_db_client

logger = logging.getLogger(__name__)


class ProgressiveIndexer:
    """
    Progressive Multi-Tenant Indexing Pipeline.
    - L1 Fast (<10ms): MD5 + Fast Visual/Text Vectors + Multi-tenant isolation entry.
    - L2 Standard (Async BackgroundTask): Deep VLM inference, 6-dimension taxonomy tags,
      2048d Dense Embeddings, marked with `is_vectorized: True`.
    """

    def __init__(self):
        self.vector_db = vector_db_client
        self.cache = cache_manager

    def index_file_l1_fast(
        self,
        file_path: str,
        media_type: Optional[MediaType] = None,
        tenant_id: str = "default"
    ) -> IndexResult:
        """Execute L1 Fast Indexing with multi-tenant tag and return HTTP 200 in < 10ms."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found for indexing: {file_path}")

        start_time = time.time()
        filename = os.path.basename(file_path)
        tenant = tenant_id or "default"

        if isinstance(media_type, str):
            try:
                media_type = MediaType(media_type.lower())
            except ValueError:
                media_type = MediaType.IMAGE
        elif not media_type:
            media_type = MediaType.IMAGE

        status_broadcaster.broadcast({
            "type": "l1_start", "filename": filename, "tenant_id": tenant,
            "message": f"L1 快速索引开始: MD5 + 视觉特征 + 主色提取 — {filename} (租户: {tenant})"
        })

        md5_str = BaseService.calculate_md5(file_path) if hasattr(BaseService, "calculate_md5") else "mock_md5_" + filename
        item_id = f"item_{md5_str[:12]}"

        # --- Check L2 DiskCache First (<5ms) ---
        cached_l2 = self.cache.get_l2_by_md5(md5_str)
        if cached_l2:
            logger.info(f"[ProgressiveIndexer] Restoring L2 index from persistent DiskCache for {filename} (tenant={tenant})")
            cat_tags = cached_l2.get("categorized_tags", tag_generator.generate_categorized_tags(cached_l2.get("description", "")))
            dom_colors = cached_l2.get("dominant_colors", ["#fdfdfd", "#ffffff"])

            result = IndexResult(
                item_id=item_id,
                tenant_id=tenant,
                media_type=media_type,
                file_path=file_path,
                md5=md5_str,
                title=filename,
                description=cached_l2.get("description", f"文件 {filename} 已成功同步缓存"),
                tags=cached_l2.get("tags", [media_type.value]),
                is_vectorized=True,
                content_vector=cached_l2.get("content_vector"),
                thumbnail_vector=cached_l2.get("thumbnail_vector"),
                metadata={
                    "progressive_level": "L2_Cached",
                    "status": "completed",
                    "tenant_id": tenant,
                    "categorized_tags": cat_tags,
                    "dominant_colors": dom_colors
                }
            )
            self.vector_db.upsert_item(result)
            status_broadcaster.broadcast({
                "type": "l1_done", "item_id": item_id, "filename": filename, "tenant_id": tenant,
                "result": self._result_payload(result),
                "message": f"命中磁盘缓存，索引完成: {filename}"
            })
            return result

        # --- L1 Fast Indexing (<10ms Instant Response) ---
        logger.info(f"[ProgressiveIndexer] Executing L1 Fast Indexing for {filename} (tenant={tenant})...")
        status_broadcaster.broadcast({
            "type": "l1_progress", "filename": filename, "tenant_id": tenant,
            "message": f"提取视觉特征向量与主色调: {filename}"
        })
        visual_vec = image_service.extract_visual_feature_vector(file_path) if media_type == MediaType.IMAGE else None
        dom_colors = image_service.extract_dominant_colors(file_path) if media_type == MediaType.IMAGE else ["#1e293b", "#334155"]

        l1_result = IndexResult(
            item_id=item_id,
            tenant_id=tenant,
            media_type=media_type,
            file_path=file_path,
            md5=md5_str,
            title=filename,
            description=f"文件 {filename} L1 特征建立成功 (MD5 + 视觉向量 + 主色已就绪)",
            tags=[media_type.value, "L1_Fast"],
            is_vectorized=True,
            content_vector=text_service.process_text(filename),
            thumbnail_vector=visual_vec,
            metadata={
                "progressive_level": "L1_Fast",
                "status": "searchable",
                "tenant_id": tenant,
                "categorized_tags": {
                    "Subject": ["媒体对象"],
                    "ColorStyle": ["高清质感"],
                    "Scene": ["应用场景"],
                    "Emotion": ["自然"],
                    "Composition": ["中心构图"],
                    "Entity": [filename]
                },
                "dominant_colors": dom_colors
            }
        )
        self.vector_db.upsert_item(l1_result)

        elapsed = time.time() - start_time
        logger.info(f"[ProgressiveIndexer] L1 Instant response for {filename} in {elapsed*1000:.1f}ms")
        status_broadcaster.broadcast({
            "type": "l1_done", "item_id": item_id, "filename": filename, "tenant_id": tenant,
            "result": self._result_payload(l1_result),
            "message": f"L1 快速索引完成 ({elapsed*1000:.0f}ms): {filename}"
        })
        return l1_result

    def _result_payload(self, result: IndexResult) -> dict:
        md = result.metadata or {}
        mt = result.media_type
        return {
            "item_id": result.item_id,
            "tenant_id": getattr(result, "tenant_id", "default"),
            "media_type": mt.value if hasattr(mt, "value") else str(mt),
            "file_path": result.file_path,
            "md5": result.md5,
            "title": result.title,
            "description": result.description,
            "tags": result.tags,
            "is_vectorized": getattr(result, "is_vectorized", True),
            "categorized_tags": md.get("categorized_tags", {}),
            "dominant_colors": md.get("dominant_colors", ["#fdfdfd", "#ffffff"]),
        }

    def build_analysis_prompt(
        self,
        focus_dimensions: Optional[List[str]] = None,
        custom_prompt: Optional[str] = None
    ) -> str:
        """Construct prompt incorporating user-selected focus dimensions."""
        dim_map = {
            "Subject": "1. 主体特征与细节（分析核心人物/物体外观、动作、面料、微观细节）",
            "ColorStyle": "2. 色彩基调与光影（分析冷暖色温、主色辅色、明暗光影、色彩心理）",
            "Scene": "3. 场景与空间构图（分析所处室内/室外环境、空间纵深、透视视角）",
            "Emotion": "4. 情绪氛围与美学质感（分析意境、情感共鸣、艺术风格）",
            "Composition": "5. 构图法则与镜头语言（分析三分法则、对角线、景深虚化、焦距视角）",
            "Entity": "6. 核心实体与属性标签（提炼关键具象名词、品牌/分类/材质实体）"
        }

        parts = []
        if custom_prompt and custom_prompt.strip():
            parts.append(f"【用户自定义关注要求】\n{custom_prompt.strip()}")

        if focus_dimensions:
            selected_dims = [dim_map[d] for d in focus_dimensions if d in dim_map]
            if selected_dims:
                parts.append("【请重点深入分析以下维度】\n" + "\n".join(selected_dims))

        if not parts:
            parts.append("请详细分析本画面：1. 主体特征与细节 2. 场景与空间构图 3. 色彩基调与光影 4. 情绪氛围与艺术风格。")

        return "\n\n".join(parts)

    def upgrade_l2_background(
        self,
        item_id: str,
        file_path: str,
        media_type_str: str,
        md5_str: str,
        tenant_id: str = "default",
        focus_dimensions: Optional[List[str]] = None,
        custom_prompt: Optional[str] = None
    ):
        """Execute L2 VLM Upgrade asynchronously with multi-tenant isolation."""
        filename = os.path.basename(file_path)
        tenant = tenant_id or "default"
        try:
            logger.info(f"[ProgressiveIndexer BG] Starting L2 VLM Inference for {filename} (tenant={tenant}) with focus={focus_dimensions}...")
            status_broadcaster.broadcast({
                "type": "l2_start", "item_id": item_id, "filename": filename, "tenant_id": tenant,
                "message": f"正在调用 Apple Silicon Metal GPU (Qwen3-VL-8B) 执行多维推演: {filename}..."
            })
            media_type = MediaType(media_type_str.lower())
            cat_tags = {}
            dom_colors = ["#fdfdfd", "#ffffff"]
            desc = ""
            tags = [media_type_str]
            content_vec = None
            thumbnail_vec = None

            dynamic_prompt = self.build_analysis_prompt(focus_dimensions, custom_prompt)

            if media_type == MediaType.IMAGE:
                analysis = image_service.process_image(file_path, prompt=dynamic_prompt)
                desc = analysis.description
                tags = list(set(tags + analysis.tags))
                content_vec = analysis.embedding
                thumbnail_vec = analysis.embedding
                cat_tags = tag_generator.generate_categorized_tags(desc)
                dom_colors = image_service.extract_dominant_colors(file_path)
            elif media_type == MediaType.VIDEO:
                analysis = video_service.process_video(file_path, prompt=dynamic_prompt)
                desc = f"视频关键帧描述: {' '.join(analysis.frame_descriptions)}"
                tags = list(set(tags + analysis.tags))
                content_vec = analysis.embedding
                cat_tags = tag_generator.generate_categorized_tags(desc)
            elif media_type == MediaType.AUDIO:
                analysis = audio_service.process_audio(file_path)
                desc = analysis.transcript or f"音频分析 ({analysis.audio_type})"
                tags = list(set(tags + analysis.tags))
                content_vec = analysis.embedding
                cat_tags = tag_generator.generate_categorized_tags(desc)

            full_result = IndexResult(
                item_id=item_id,
                tenant_id=tenant,
                media_type=media_type,
                file_path=file_path,
                md5=md5_str,
                title=filename,
                description=desc,
                tags=tags,
                is_vectorized=True,
                content_vector=content_vec,
                thumbnail_vector=thumbnail_vec,
                metadata={
                    "progressive_level": "L2_Standard",
                    "status": "completed",
                    "tenant_id": tenant,
                    "categorized_tags": cat_tags,
                    "dominant_colors": dom_colors,
                    "focus_dimensions": focus_dimensions or [],
                    "custom_prompt": custom_prompt or ""
                }
            )
            self.vector_db.upsert_item(full_result)

            # Save to L2 DiskCache
            cache_manager.set_l2_by_md5(md5_str, {
                "description": desc,
                "tags": tags,
                "categorized_tags": cat_tags,
                "dominant_colors": dom_colors,
                "content_vector": content_vec,
                "thumbnail_vector": thumbnail_vec,
                "indexed_at": time.time()
            })
            logger.info(f"[ProgressiveIndexer BG] L2 VLM Upgrade complete for {filename} (tenant={tenant})")
            status_broadcaster.broadcast({
                "type": "l2_done",
                "item_id": item_id,
                "tenant_id": tenant,
                "filename": filename,
                "result": self._result_payload(full_result),
                "message": f"✅ L2 VLM 深度多模态富文本与 6 维标签生成完成！"
            })
        except Exception as e:
            logger.error(f"[ProgressiveIndexer BG] L2 Upgrade error for {filename}: {e}")
            status_broadcaster.broadcast({
                "type": "l2_error", "item_id": item_id, "filename": filename, "tenant_id": tenant,
                "message": f"VLM 深度分析出错: {e}"
            })

    def index_file(self, file_path: str, media_type: str = "image", tenant_id: str = "default") -> IndexResult:
        """Synchronous full indexing alias with tenant support."""
        l1 = self.index_file_l1_fast(file_path, MediaType(media_type), tenant_id=tenant_id)
        self.upgrade_l2_background(l1.item_id, file_path, media_type, l1.md5, tenant_id=tenant_id)
        return self.vector_db.get_item_by_id(l1.item_id, tenant_id=tenant_id) or l1


progressive_indexer = ProgressiveIndexer()
