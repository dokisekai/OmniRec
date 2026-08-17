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
            content_vector=visual_vec,
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
            "person_details": md.get("person_details", {}),
            "fashion_details": md.get("fashion_details", {}),
            "socks_details": md.get("socks_details", {}),
            "compliance_audit": md.get("compliance_audit", {}),
        }

    def build_analysis_prompt(
        self,
        focus_dimensions: Optional[List[str]] = None,
        custom_prompt: Optional[str] = None
    ) -> str:
        """Construct prompt incorporating user-selected focus dimensions."""
        dim_map = {
            "Subject": "1. 主体与人物全貌（深度分析核心人物/对象的面容、年龄感知、发型发色、体态神情与核心动作）",
            "PersonFashion": "2. 穿搭服装与首饰配饰（从头到脚详细解构：发型与妆容、上衣/外套款式与面料、下装/裙装与鞋履、项链/耳环/戒指/手镯/手表/发饰/眼镜/包包等珠宝首饰细节）",
            "FashionIndustry": "2. 服装行业专业多维解构（深度解构品类款式、H/A/X茧型版型剪裁、真丝/纯棉/亚麻/羊绒/羊毛/皮革/牛仔/雪纺等面料材质肌理、西装驳领/方领/V领/立领/泡泡袖/落肩等领袖型、千鸟格/格纹/条纹/印花与明线/贝壳扣/牛角扣等工艺辅料、静奢老钱风/Cleanfit/法式复古/新中式等穿搭风格）",
            "SocksHosiery": "2. 袜品垂直专业解构（精确识别所穿袜子的品类长度如隐形船袜/短袜/中筒堆堆袜/小腿袜/长筒过膝袜/连裤丝袜/运动毛圈袜；精准识别颜色与透明度D数如纯黑/奶白/自然肤色/焦糖美拉德/超薄透肉10D/哑光不透肉120D/加绒；分析材质织造如精梳棉/尼龙丝滑/天鹅绒/双针罗纹/细坑条/无骨缝头及鞋履搭配与穿搭风格）",
            "ColorStyle": "3. 色彩基调与光影（分析冷暖色温、主色辅色、明暗光影、色彩美学如美拉德/多巴胺/莫兰迪等）",
            "Scene": "4. 场景与空间构图（分析所处室内/室外/街头/职场/展厅环境与透视纵深）",
            "Emotion": "5. 情绪氛围与美学质感（分析意境表达、人物情绪如治愈/从容/自信/知性、穿搭美学风格流派）",
            "Composition": "6. 构图法则与镜头语言（分析特写/近景/全身、三分法、景深虚化、焦距视角）",
            "Entity": "7. 核心实体与属性标签（提炼关键具象名词，包括首饰品牌品类、服装材质、道具实体）",
            "AdultContentAudit": "8. 场景适宜度与合规诊断（客观评估着装覆盖适宜度、镜头景别与机位特写、动作姿态与场景契合度；若存在不合规或边缘瑕疵，明确指出问题并输出具体的整改建议）"
        }

        parts = []
        if custom_prompt and custom_prompt.strip():
            parts.append(f"【用户自定义关注要求】\n{custom_prompt.strip()}")

        if focus_dimensions:
            selected_dims = [dim_map[d] for d in focus_dimensions if d in dim_map]
            if selected_dims:
                parts.append("【请重点深入分析以下维度】\n" + "\n".join(selected_dims))

        if not parts:
            parts.append(
                "请对本画面进行全维深度多模态分析：\n"
                "1. 人物与面容妆发：性别体态、发型发色、妆容唇色、表情神态\n"
                "2. 服饰穿搭解构：上衣/下装/裙装/鞋履的款式、颜色与面料材质\n"
                "3. 珠宝首饰与配饰：项链、耳饰、戒指、手链手镯、腕表、发饰、眼镜、包袋等细致清单\n"
                "4. 色彩光影与场景构图：场景环境、冷暖基调与构图视角\n"
                "5. 风格美学流派：如法式复古、极简通勤、轻奢名媛、新中式、街头潮流等。"
            )

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
                "message": f"正在调用 Apple Silicon Metal GPU (Qwen3-VL-8B) 执行人物与全维推演: {filename}..."
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
                desc = f"视频关键帧剧情与穿搭描述: {' '.join(analysis.frame_descriptions)}"
                tags = list(set(tags + analysis.tags))
                content_vec = analysis.embedding
                cat_tags = tag_generator.generate_categorized_tags(desc)
            elif media_type == MediaType.AUDIO:
                analysis = audio_service.process_audio(file_path)
                desc = analysis.transcript or f"音频分析 ({analysis.audio_type})"
                tags = list(set(tags + analysis.tags))
                content_vec = analysis.embedding
                cat_tags = tag_generator.generate_categorized_tags(desc)

            # Deep Person & Fashion extraction
            person_details = tag_generator.extract_person_details(desc)
            if person_details.get("has_person"):
                tags.extend(person_details.get("jewelry_accessories", []))
                tags.extend(person_details.get("apparel_top", []))
                tags.extend(person_details.get("apparel_bottom", []))
                tags.extend(person_details.get("style_aesthetics", []))

            # Professional Fashion Industry Breakdown extraction
            fashion_details = tag_generator.extract_fashion_industry_details(desc)
            if fashion_details.get("has_fashion_analysis"):
                tags.extend(fashion_details.get("garment_categories", []))
                tags.extend(fashion_details.get("fabrics_textures", []))
                tags.extend(fashion_details.get("silhouettes", []))
                tags.extend(fashion_details.get("collars_sleeves", []))
                tags.extend(fashion_details.get("patterns_crafts", []))
                tags.extend(fashion_details.get("style_aesthetics", []))

            # Specialized Hosiery & Socks Industry extraction
            socks_details = tag_generator.extract_socks_details(desc)
            if socks_details.get("has_socks"):
                tags.extend(socks_details.get("socks_types", []))
                tags.extend(socks_details.get("colors_denier", []))
                tags.extend(socks_details.get("materials_weaves", []))
                tags.extend(socks_details.get("patterns_crafts", []))
                tags.extend(socks_details.get("pairing_styles", []))

            # Compliance, Appropriateness & Remediation extraction
            compliance_audit = tag_generator.extract_compliance_audit(desc)
            if compliance_audit.get("issue_tags"):
                tags.extend(compliance_audit.get("issue_tags", []))
            tags = list(set(tags))

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
                    "person_details": person_details,
                    "fashion_details": fashion_details,
                    "socks_details": socks_details,
                    "compliance_audit": compliance_audit,
                    "focus_dimensions": focus_dimensions or [],
                    "custom_prompt": custom_prompt or ""
                }
            )
            self.vector_db.upsert_item(full_result)

            cache_manager.set_l2_by_md5(md5_str, {
                "description": desc,
                "tags": tags,
                "categorized_tags": cat_tags,
                "dominant_colors": dom_colors,
                "person_details": person_details,
                "fashion_details": fashion_details,
                "socks_details": socks_details,
                "compliance_audit": compliance_audit,
                "content_vector": content_vec,
                "thumbnail_vector": thumbnail_vec,
                "indexed_at": time.time(),
                "metadata": full_result.metadata
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
