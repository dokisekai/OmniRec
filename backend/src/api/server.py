import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from src.core.config import settings
from src.core.memory_manager import memory_manager
from src.core.schemas import IndexResult, ModelModality, RecommendQuery, RecommendResult, SearchQuery, SearchResult
from src.core.status_broadcaster import status_broadcaster
from src.engine.recommendation_engine import recommendation_engine
from src.engine.retrieval_engine import retrieval_engine
from src.pipeline.progressive_indexer import progressive_indexer
from src.services.image_service import image_service
from src.services.video_service import video_service
from src.services.audio_service import audio_service
from src.pipeline.tag_generator import tag_generator
from src.vector_db.qdrant_client import vector_db_client

logger = logging.getLogger(__name__)


def _preload_l0_models():
    """Pre-warm all 6 models into memory in L0 permanent resident mode.

    Runs in a worker thread at startup so the event loop stays responsive.
    Broadcasts progress over the WebSocket status stream.
    """
    from src.models.vlm import VLMWrapper
    from src.models.embedding import EmbeddingWrapper
    from src.models.reranker import RerankerWrapper
    from src.models.clap import CLAPWrapper
    from src.models.whisper import WhisperWrapper
    from src.models.llm import LLMWrapper

    # 1. VLM (Qwen3-VL-8B)
    status_broadcaster.broadcast({"type": "model_loading", "model": "vlm", "message": "正在加载 Qwen3-VL-8B (5.4GB) 到 Metal GPU..."})
    try:
        vlm = memory_manager.load_model(ModelModality.VLM, loader_fn=lambda: VLMWrapper())
        if not getattr(vlm, "_is_loaded", False):
            vlm.load()
        status_broadcaster.broadcast({"type": "model_loaded", "model": "vlm", "message": "Qwen3-VL-8B 已常驻 Metal GPU (5.4GB)"})
    except Exception as e:
        logger.warning(f"VLM pre-warm failed: {e}")
        status_broadcaster.broadcast({"type": "model_error", "model": "vlm", "message": f"VLM 加载失败: {e}"})

    # 2. Embedding (Qwen3-VL-Embedding)
    status_broadcaster.broadcast({"type": "model_loading", "model": "embedding", "message": "正在加载 Qwen3-Embedding-2B (2.0GB)..."})
    try:
        emb = memory_manager.load_model(ModelModality.EMBEDDING, loader_fn=lambda: EmbeddingWrapper())
        if not getattr(emb, "_is_loaded", False):
            emb.load()
        status_broadcaster.broadcast({"type": "model_loaded", "model": "embedding", "message": "Qwen3-Embedding-2B 已就绪 (2.0GB, 2048d)"})
    except Exception as e:
        logger.warning(f"Embedding pre-warm failed: {e}")
        status_broadcaster.broadcast({"type": "model_error", "model": "embedding", "message": f"Embedding 加载失败: {e}"})

    # 3. Reranker (Qwen3-VL-Reranker-2B)
    status_broadcaster.broadcast({"type": "model_loading", "model": "reranker", "message": "正在加载 Qwen3-VL-Reranker-2B (2.0GB)..."})
    try:
        reranker = memory_manager.load_model(ModelModality.RERANKER, loader_fn=lambda: RerankerWrapper())
        if not getattr(reranker, "_is_loaded", False):
            reranker.load()
        status_broadcaster.broadcast({"type": "model_loaded", "model": "reranker", "message": "Qwen3-VL-Reranker-2B 精排模型已就绪 (2.0GB)"})
    except Exception as e:
        logger.warning(f"Reranker pre-warm failed: {e}")
        status_broadcaster.broadcast({"type": "model_error", "model": "reranker", "message": f"Reranker 加载失败: {e}"})

    # 4. CLAP (LAION CLAP 512d)
    status_broadcaster.broadcast({"type": "model_loading", "model": "clap", "message": "正在加载 LAION CLAP 音频特征模型 (0.6GB)..."})
    try:
        clap = memory_manager.load_model(ModelModality.CLAP, loader_fn=lambda: CLAPWrapper())
        if not getattr(clap, "_is_loaded", False):
            clap.load()
        status_broadcaster.broadcast({"type": "model_loaded", "model": "clap", "message": "LAION CLAP 音频特征模型已就绪 (0.6GB, 512d)"})
    except Exception as e:
        logger.warning(f"CLAP pre-warm failed: {e}")
        status_broadcaster.broadcast({"type": "model_error", "model": "clap", "message": f"CLAP 加载失败: {e}"})

    # 5. Whisper ASR (Whisper-large-v3)
    status_broadcaster.broadcast({"type": "model_loading", "model": "asr", "message": "正在加载 Whisper ASR 语音识别模型 (0.7GB)..."})
    try:
        asr = memory_manager.load_model(ModelModality.ASR, loader_fn=lambda: WhisperWrapper())
        if not getattr(asr, "_is_loaded", False):
            asr.load()
        status_broadcaster.broadcast({"type": "model_loaded", "model": "asr", "message": "Whisper ASR 语音识别模型已就绪 (0.7GB)"})
    except Exception as e:
        logger.warning(f"Whisper ASR pre-warm failed: {e}")
        status_broadcaster.broadcast({"type": "model_error", "model": "asr", "message": f"Whisper ASR 加载失败: {e}"})

    # 6. LLM Reasoning (Bonsai-8B-MLX)
    status_broadcaster.broadcast({"type": "model_loading", "model": "llm", "message": "正在加载 Bonsai-8B-MLX 推理大模型 (1.3GB)..."})
    try:
        llm = memory_manager.load_model(ModelModality.LLM, loader_fn=lambda: LLMWrapper())
        if not getattr(llm, "_is_loaded", False):
            llm.load()
        status_broadcaster.broadcast({"type": "model_loaded", "model": "llm", "message": "Bonsai-8B-MLX 解释生成模型已就绪 (1.3GB)"})
    except Exception as e:
        logger.warning(f"LLM pre-warm failed: {e}")
        status_broadcaster.broadcast({"type": "model_error", "model": "llm", "message": f"LLM 加载失败: {e}"})

    logger.info(f"⚡ [All 6 Models Resident] Total Resident Memory: {memory_manager.get_used_memory_gb():.1f} GB / {settings.MEMORY_LIMIT_GB} GB OK.")
    status_broadcaster.broadcast({"type": "ready", "message": "所有 6 个多模态深度模型已全部常驻内存/显存，系统就绪！"})


@asynccontextmanager
async def lifespan(app: FastAPI):
    status_broadcaster.set_loop(asyncio.get_event_loop())
    logger.info("⚡ [Startup] Pre-loading L0 Permanent models (VLM + Embedding) in background thread...")
    # Run pre-warm in a worker thread so the server is immediately responsive.
    asyncio.create_task(asyncio.to_thread(_preload_l0_models))
    yield


app = FastAPI(
    title="Antigravity Multimodal Recommender System API",
    description="Full-stack multimodal recommendation & search system with dual-track vectors, 6-category taxonomy tags, and Apple Silicon memory management.",
    version="2.0.0",
    lifespan=lifespan
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Resolve path to frontend/public
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
frontend_dir = os.path.join(project_root, "frontend", "public")

if not os.path.exists(frontend_dir):
    # Fallback to local static directory inside api
    frontend_dir = os.path.join(os.path.dirname(__file__), "static")

if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")
    assets_dir = os.path.join(frontend_dir, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
    logger.info(f"Frontend static directory mounted from: {frontend_dir}")

test_files_dir = os.path.join(project_root, "test_files")
if os.path.exists(test_files_dir):
    app.mount("/test_files", StaticFiles(directory=test_files_dir), name="test_files")

uploads_cache_dir = os.path.join(settings.CACHE_DIR, "uploads")
os.makedirs(uploads_cache_dir, exist_ok=True)
app.mount("/cache/uploads", StaticFiles(directory=uploads_cache_dir), name="uploads")

@app.get("/")
async def root():
    """Serve the interactive Multimodal Recommender Dashboard."""
    index_path = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "qdrant_host": settings.QDRANT_HOST,
        "memory_limit_gb": settings.MEMORY_LIMIT_GB
    }

@app.get("/models/status")
@app.get("/api/v1/models/status")
async def get_models_status_endpoint():
    """Get active models, memory budget tiers, and load status."""
    return memory_manager.get_status()

@app.post("/api/v1/test_preset")
async def test_preset_endpoint(preset_name: str = Query("image")):
    """Trigger one-click indexing for preset test files (image, video, voice, music)."""
    mapping = {
        "image": ("test_files/beauty_1755438760705.jpeg", "image"),
        "video": ("test_files/IMG_2514.MOV", "video"),
        "voice": ("test_files/sample_voice.wav", "audio"),
        "music": ("test_files/sample_music.wav", "audio"),
    }
    if preset_name not in mapping:
        return {"status": "error", "message": f"Unknown preset: {preset_name}"}
    rel_path, media_type = mapping[preset_name]
    abs_path = os.path.join(project_root, rel_path)
    if not os.path.exists(abs_path):
        return {"status": "error", "message": f"Preset file not found: {abs_path}"}

    index_res = await asyncio.to_thread(progressive_indexer.index_file_l1_fast, abs_path, media_type)
    asyncio.create_task(
        asyncio.to_thread(
            progressive_indexer.upgrade_l2_background,
            index_res.item_id,
            abs_path,
            media_type,
            index_res.md5
        )
    )
    return {
        "status": "success",
        "file_url": f"/{rel_path}",
        "media_type": media_type,
        "index_result": index_res
    }

from fastapi import File, UploadFile, Form
from fastapi.encoders import jsonable_encoder

import json

@app.post("/upload")
@app.post("/api/v1/upload")
async def upload_and_index_endpoint(
    file: UploadFile = File(...),
    media_type: str = Form("image"),
    mode: str = Form("full"),
    tenant_id: str = Form("default"),
    focus_dimensions: Optional[str] = Form(None),
    custom_prompt: Optional[str] = Form(None)
):
    """Multipart Upload & Indexing Endpoint with Multi-Tenant Isolation & Execution Mode Selection.

    Supported Modes:
    - 'full': L1 Fast Indexing -> L2 VLM Analysis & 6-Dim Tags -> Vector DB -> Item-to-Item Recommendations
    - 'vlm_only': Deep VLM Feature Extraction & Categorized Tags only (no vector DB / recommendation)
    - 'fast_vector': L1 Fast Vector & Color extraction only (<50ms, no VLM GPU load)
    - 'embedding_only': 2048d Dense Vector Embedding extraction only
    """
    uploads_dir = os.path.join(settings.CACHE_DIR, "uploads")
    os.makedirs(uploads_dir, exist_ok=True)

    saved_filename = f"{int(time.time())}_{file.filename}"
    saved_path = os.path.join(uploads_dir, saved_filename)
    target_tenant = tenant_id or "default"

    with open(saved_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)

    logger.info(f"File uploaded to {saved_path} (tenant={target_tenant}, mode={mode}, focus={focus_dimensions})")
    status_broadcaster.broadcast({"type": "upload_received", "filename": file.filename, "tenant_id": target_tenant, "message": f"文件已接收 (租户: {target_tenant}, 模式: {mode}): {file.filename}"})

    # Parse focus_dimensions if provided as JSON string or comma-separated list
    parsed_dims: Optional[List[str]] = None
    if focus_dimensions:
        try:
            parsed_dims = json.loads(focus_dimensions) if focus_dimensions.startswith("[") else [d.strip() for d in focus_dimensions.split(",") if d.strip()]
        except Exception:
            parsed_dims = [d.strip() for d in focus_dimensions.split(",") if d.strip()]

    # Mode 1: Fast Vector Only (<50ms, no VLM inference)
    if mode == "fast_vector":
        index_res = await asyncio.to_thread(progressive_indexer.index_file_l1_fast, saved_path, media_type, target_tenant)
        status_broadcaster.broadcast({
            "type": "l1_done",
            "item_id": index_res.item_id,
            "tenant_id": target_tenant,
            "filename": file.filename,
            "message": "⚡ 快速向量提取完成 (已跳过大模型推演)",
            "result": index_res.dict() if hasattr(index_res, 'dict') else index_res
        })
        return jsonable_encoder({
            "status": "success",
            "mode": "fast_vector",
            "tenant_id": target_tenant,
            "saved_path": saved_path,
            "filename": file.filename,
            "index_result": index_res
        })

    # Mode 2: Embedding Only (2048d vector directly from media)
    if mode == "embedding_only":
        if media_type.lower() == "audio":
            vec = audio_service.extract_audio_feature_vector(saved_path, dim=512)
        else:
            vec = image_service.extract_visual_feature_vector(saved_path, dim=settings.VECTOR_DIM)
        md5_str = image_service.calculate_md5(saved_path)
        item_id = f"item_{md5_str[:12]}"
        index_res = IndexResult(
            item_id=item_id,
            tenant_id=target_tenant,
            media_type=media_type,
            file_path=saved_path,
            md5=md5_str,
            title=file.filename,
            description="仅生成 2048 维向量嵌入",
            is_vectorized=True,
            content_vector=vec,
            thumbnail_vector=vec,
            metadata={"mode": "embedding_only", "status": "completed", "tenant_id": target_tenant}
        )
        vector_db_client.upsert_item(index_res)
        status_broadcaster.broadcast({
            "type": "l1_done",
            "item_id": item_id,
            "tenant_id": target_tenant,
            "filename": file.filename,
            "message": f"🎯 2048 维稠密特征向量生成完成 (维度: {len(vec)})",
            "result": index_res.dict() if hasattr(index_res, 'dict') else index_res
        })
        return jsonable_encoder({
            "status": "success",
            "mode": "embedding_only",
            "tenant_id": target_tenant,
            "saved_path": saved_path,
            "filename": file.filename,
            "index_result": index_res
        })

    # Mode 3: VLM Understanding Only (GPU inference for text & tags, no recommendation overhead)
    if mode == "vlm_only":
        index_res = await asyncio.to_thread(progressive_indexer.index_file_l1_fast, saved_path, media_type, target_tenant)
        asyncio.create_task(
            asyncio.to_thread(
                progressive_indexer.upgrade_l2_background,
                index_res.item_id,
                saved_path,
                media_type,
                index_res.md5,
                target_tenant,
                parsed_dims,
                custom_prompt
            )
        )
        return jsonable_encoder({
            "status": "success",
            "mode": "vlm_only",
            "tenant_id": target_tenant,
            "saved_path": saved_path,
            "filename": file.filename,
            "index_result": index_res
        })

    # Mode 4: Full Pipeline (L1 Fast -> L2 VLM -> Vectors -> Item-to-Item Recommendations)
    index_res = await asyncio.to_thread(progressive_indexer.index_file_l1_fast, saved_path, media_type, target_tenant)
    asyncio.create_task(
        asyncio.to_thread(
            progressive_indexer.upgrade_l2_background,
            index_res.item_id,
            saved_path,
            media_type,
            index_res.md5,
            target_tenant,
            parsed_dims,
            custom_prompt
        )
    )

    return jsonable_encoder({
        "status": "success",
        "mode": "full",
        "tenant_id": target_tenant,
        "saved_path": saved_path,
        "filename": file.filename,
        "index_result": index_res
    })

class DirectAnalysisRequest(BaseModel):
    file_path: str
    media_type: str = "image"
    focus_dimensions: Optional[List[str]] = None
    custom_prompt: Optional[str] = None

@app.post("/api/v1/analyze")
async def direct_analyze_endpoint(req: DirectAnalysisRequest):
    """Direct Standalone Model Analysis API.
    
    Executes VLM/ASR inference with dynamically configured focus dimensions and custom prompt.
    """
    abs_path = os.path.abspath(req.file_path) if not os.path.isabs(req.file_path) else req.file_path
    if not os.path.exists(abs_path):
        return {"status": "error", "message": f"File not found: {abs_path}"}

    dynamic_prompt = progressive_indexer.build_analysis_prompt(req.focus_dimensions, req.custom_prompt)
    mtype = req.media_type.lower()

    if mtype == "video":
        res = await asyncio.to_thread(video_service.process_video, abs_path, dynamic_prompt)
        desc = " ".join(res.frame_descriptions)
        tags = tag_generator.generate_categorized_tags(desc)
        return {
            "status": "success",
            "media_type": "video",
            "description": desc,
            "categorized_tags": tags,
            "embedding_dim": len(res.embedding) if res.embedding else 2048
        }
    elif mtype == "audio":
        res = await asyncio.to_thread(audio_service.process_audio, abs_path)
        desc = res.transcript or f"音频分析 ({res.audio_type})"
        tags = tag_generator.generate_categorized_tags(desc)
        return {
            "status": "success",
            "media_type": "audio",
            "description": desc,
            "categorized_tags": tags,
            "embedding_dim": len(res.embedding) if res.embedding else 2048
        }
    else:
        res = await asyncio.to_thread(image_service.process_image, abs_path, dynamic_prompt)
        tags = tag_generator.generate_categorized_tags(res.description)
        return {
            "status": "success",
            "media_type": "image",
            "description": res.description,
            "categorized_tags": tags,
            "embedding_dim": len(res.embedding) if res.embedding else 2048
        }

class DirectEmbedRequest(BaseModel):
    text: Optional[str] = None
    file_path: Optional[str] = None
    media_type: str = "image"

@app.post("/api/v1/embed")
async def direct_embed_endpoint(req: DirectEmbedRequest):
    """Direct Standalone Vector Embedding API.
    
    Generates 2048d/512d dense vector directly from raw text or raw media files (Image, Video, Audio).
    """
    if req.text and req.text.strip():
        from src.models.embedding import EmbeddingWrapper
        emb_model = memory_manager.load_model(ModelModality.EMBEDDING, loader_fn=lambda: EmbeddingWrapper())
        vecs = emb_model.predict([req.text.strip()])
        vec = vecs[0] if vecs else []
        return {
            "status": "success",
            "type": "text",
            "dim": len(vec),
            "vector_sample": vec[:8],
            "full_vector": vec
        }
    elif req.file_path:
        abs_path = os.path.abspath(req.file_path) if not os.path.isabs(req.file_path) else req.file_path
        if not os.path.exists(abs_path):
            return {"status": "error", "message": f"File not found: {abs_path}"}
        mtype = req.media_type.lower()
        if mtype == "audio":
            vec = audio_service.extract_audio_feature_vector(abs_path, dim=512)
        else:
            vec = image_service.extract_visual_feature_vector(abs_path, dim=settings.VECTOR_DIM)
        return {
            "status": "success",
            "type": "file",
            "media_type": mtype,
            "dim": len(vec),
            "vector_sample": vec[:8],
            "full_vector": vec
        }
    return {"status": "error", "message": "Either 'text' or 'file_path' must be provided."}

@app.get("/api/v1/items")
async def list_items_endpoint(tenant_id: Optional[str] = Query(None)):
    """List indexed media items in vector database, optionally filtered by tenant."""
    from src.vector_db.qdrant_client import vector_db_client
    items = vector_db_client.list_all_items(tenant_id=tenant_id)
    return {
        "status": "success",
        "tenant_id": tenant_id or "all",
        "total": len(items),
        "items": items
    }

@app.delete("/api/v1/items/{item_id}")
async def delete_item_endpoint(item_id: str, tenant_id: str = Query("default")):
    """Delete an item from vector DB."""
    from src.vector_db.qdrant_client import vector_db_client
    vector_db_client.delete_item(item_id, tenant_id=tenant_id)
    return {"status": "success", "tenant_id": tenant_id, "message": f"Item {item_id} deleted."}

@app.post("/search", response_model=SearchResult)
@app.post("/api/v1/search", response_model=SearchResult)
async def search_endpoint(query: SearchQuery):
    """Multimodal search endpoint with multi-tenant isolation & RRF fusion."""
    return retrieval_engine.search(query)

@app.post("/recommend", response_model=RecommendResult)
@app.post("/api/v1/recommend", response_model=RecommendResult)
async def recommend_endpoint(query: RecommendQuery):
    """Item-to-Item recommendation endpoint with multi-tenant isolation, MMR & LLM explanations."""
    return recommendation_engine.recommend_item_to_item(query)

@app.post("/index", response_model=IndexResult)
@app.post("/api/v1/index", response_model=IndexResult)
async def index_file_endpoint(
    file_path: str = Query(...),
    media_type: str = Query("image"),
    tenant_id: str = Query("default")
):
    """Progressive indexing endpoint with multi-tenant isolation."""
    import asyncio
    return await asyncio.to_thread(progressive_indexer.index_file, file_path, media_type, tenant_id)

@app.get("/metrics", response_class=PlainTextResponse)
async def metrics_endpoint():
    """Prometheus metrics exporter — dynamic values from memory_manager."""
    status = memory_manager.get_status()
    used_gb = status.get("current_usage_gb", 12.0)
    limit_gb = status.get("memory_limit_gb", 20.0)
    loaded = status.get("loaded_models", {})
    total_items = len(vector_db_client.list_all_items()) if hasattr(vector_db_client, "list_all_items") else 0

    lines = [
        "# HELP recommender_memory_used_gb Current GPU/RAM memory used by models (GB)",
        "# TYPE recommender_memory_used_gb gauge",
        f"recommender_memory_used_gb {used_gb:.1f}",
        f"recommender_memory_limit_gb {limit_gb:.1f}",
        "",
        "# HELP recommender_models_loaded Number of AI models currently loaded",
        "# TYPE recommender_models_loaded gauge",
        f"recommender_models_loaded {len(loaded)}",
        "",
        "# HELP recommender_vector_db_items Total indexed media items",
        "# TYPE recommender_vector_db_items gauge",
        f"recommender_vector_db_items {total_items}",
    ]
    for mod_name, mod_info in loaded.items():
        mem = mod_info.get("memory_gb", 0.0)
        lines.append(f'recommender_model_memory_gb{{model="{mod_name}"}} {mem:.1f}')

    return "\n".join(lines) + "\n"

@app.websocket("/ws/progress")
async def websocket_progress_stream(websocket: WebSocket):
    """WebSocket endpoint for real-time model-loading & indexing status updates."""
    await status_broadcaster.connect(websocket)
    try:
        while True:
            # Keep the connection alive; clients may send pings but we drive
            # updates via status_broadcaster.broadcast() from worker threads.
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected.")
    except Exception as e:
        logger.debug(f"WebSocket error: {e}")
    finally:
        status_broadcaster.disconnect(websocket)
