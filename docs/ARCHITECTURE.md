# Antigravity 多模态推荐系统 — 架构设计文档 v2.0

> 更新时间: 2026-08-16 | 状态: 已优化落地

---

## 一、系统全景架构

```mermaid
graph TB
    subgraph CLIENT["客户端层"]
        B1["🖥️ React 19 前端<br/>5 Tab 控制台"]
        B2["🔧 第三方调用<br/>cURL / SDK"]
    end

    subgraph API["API 网关层 (FastAPI)"]
        A1["POST /api/v1/upload<br/>模式路由"]
        A2["POST /api/v1/analyze<br/>直接 VLM 推演"]
        A3["POST /api/v1/embed<br/>向量生成"]
        A4["POST /api/v1/search<br/>多模态检索"]
        A5["POST /api/v1/recommend<br/>关联推荐"]
        A6["WS /ws/progress<br/>实时推送"]
    end

    subgraph PIPELINE["管线层"]
        P1["ProgressiveIndexer L1<br/>快速索引 <10ms"]
        P2["ProgressiveIndexer L2<br/>VLM 深度推演 BG"]
        P3["TagGenerator<br/>6维分类标签"]
        P4["BatchProcessor<br/>优先级任务队列"]
    end

    subgraph MODELS["模型层 Apple Silicon Metal GPU"]
        M1["🧠 Qwen3-VL-8B MLX 4-bit 5.4GB ✅ 真实推理"]
        M2["🎯 Qwen3-VL-Embedding 2048d 2.0GB ✅ 真实接入"]
        M3["📊 Qwen3-VL-Reranker-2B 2.0GB ✅ 真实Cross-Encoder推理"]
        M4["🔊 LAION CLAP 512d 0.6GB ✅ 真实音频/文本向量"]
        M5["🎵 Whisper-large-v3 ASR 0.7GB ✅ 已接入"]
        M6["💡 Bonsai-8B-MLX LLM 1.3GB ✅ 已接入"]
    end

    subgraph STORAGE["存储层"]
        S1["Qdrant 向量数据库<br/>HNSW + INT8量化 ✅ 已上线"]
        S2["内存 dict 降级<br/>Qdrant 不可用时自动切换"]
        S3["DiskCache L2<br/>MD5索引持久化"]
    end

    CLIENT --> API
    A1 --> P1 --> S1
    A1 --> P2 --> M1
    P2 --> M2 --> S1
    P2 --> P3
    A2 --> M1
    A3 --> M2
    A4 --> E1["RetrievalEngine RRF"]
    A5 --> E2["RecommendEngine MMR"]
    E1 --> S1
    E2 --> S1
    S1 -.->|降级| S2
    A6 -.->|推送| CLIENT
```

---

## 二、核心数据流

### 2.1 上传全流程 (Full Pipeline Mode)

```mermaid
sequenceDiagram
    participant FE as 前端
    participant API as FastAPI
    participant IDX as ProgressiveIndexer
    participant VLM as Qwen3-VL-8B
    participant EMB as Embedding Model
    participant VDB as Vector DB
    participant WS as WebSocket

    FE->>API: POST /upload (file, mode=full, focus_dims)
    API->>IDX: index_file_l1_fast(path, media_type)
    Note over IDX: MD5 + 主色提取 + 临时向量 <10ms
    IDX-->>WS: l1_start
    IDX->>VDB: upsert L1 result
    IDX-->>WS: l1_done
    API-->>FE: HTTP 200 (L1 IndexResult)

    Note over API: BackgroundTask 启动
    IDX-->>WS: l2_start
    IDX->>VLM: predict(path, dynamic_prompt)
    VLM-->>IDX: 富文本描述 (6维结构)
    IDX->>IDX: TagGenerator 提取标签
    IDX->>EMB: predict(description)
    EMB-->>IDX: 2048d 向量
    IDX->>VDB: upsert L2 full result
    IDX-->>WS: l2_done + result
    WS-->>FE: 实时更新 UI
```

### 2.2 执行模式路由

```mermaid
flowchart LR
    UP["/upload"] --> M{mode}
    M -->|fast_vector| L1["L1 仅快速向量 <10ms"]
    M -->|embedding_only| EMB["直接 2048d Embedding"]
    M -->|vlm_only| V2["L1 + L2 VLM 跳过推荐"]
    M -->|full| FULL["L1 + L2 + 向量 + 推荐"]
    L1 & EMB & V2 & FULL --> R["HTTP 200 立即返回"]
    V2 & FULL -.->|BG| WS["WS 推送 l2_done"]
```

---

## 三、API 接口规范

### 统一响应格式

```json
// 成功
{ "status": "success", "data": {...}, "latency_ms": 42.5 }

// 失败
{ "status": "error", "code": "FILE_NOT_FOUND", "message": "..." }
```

### 接口一览

| 方法 | 路径 | 核心参数 | 功能 |
|:-----|:-----|:---------|:-----|
| `POST` | `/api/v1/upload` | `file, mode, focus_dimensions, custom_prompt` | 文件上传与渐进式索引 |
| `POST` | `/api/v1/analyze` | `file_path, media_type, focus_dimensions, custom_prompt` | 纯 VLM 推演 (不入库) |
| `POST` | `/api/v1/embed` | `text` 或 `file_path, media_type` | 生成 2048d 向量 |
| `POST` | `/api/v1/search` | `query_text, filter_media_type, top_k, enable_rerank` | 语义检索 |
| `POST` | `/api/v1/recommend` | `item_id, top_k, enable_explanation` | Item-to-Item 推荐 |
| `GET` | `/api/v1/items` | - | 全量索引列表 |
| `DELETE` | `/api/v1/items/{id}` | - | 删除条目 |
| `GET` | `/api/v1/models/status` | - | 模型状态与显存 |
| `WS` | `/ws/progress` | - | 实时推理进度流 |

---

## 四、内存分层设计

```
Apple M 系列 24GB 统一内存
├── System Reserved      4.0 GB
└── App Budget          20.0 GB
    ├── L0 Permanent    12.0 GB  永不换出
    │   ├── Qwen3-VL-8B (MLX)     5.4 GB  ✅ 真实推理 (MLX Metal GPU)
    │   ├── Qwen3-VL-Embedding     2.0 GB  ✅ 真实接入 (2048d 稠密向量)
    │   ├── Qwen3-VL-Reranker      2.0 GB  ✅ 真实推理 (Cross-Encoder 精排)
    │   ├── Bonsai-8B-MLX          1.3 GB  ✅ 真实接入 (智能推荐解释生成)
    │   ├── Whisper-large-v3       0.7 GB  ✅ 真实接入 (ASR 语音转写)
    │   └── LAION CLAP             0.6 GB  ✅ 真实推理 (512d 音频/文本对齐向量)
    └── L1 Hot Cache     8.0 GB  5min TTL
```

---

## 五、向量数据库 Schema

```yaml
# Qdrant Collection: media_items  ✅ 已创建并运行
named_vectors:
  content_vector:   dim: 2048  distance: Cosine
  thumbnail_vector: dim: 2048  distance: Cosine
  audio_vector:     dim: 512   distance: Cosine

hnsw_config:  { m: 16, ef_construct: 64 }
quantization: { type: int8, quantile: 0.99, always_ram: true }

payload_schema:
  item_id, media_type, file_path, md5,
  title, description, tags, indexed_at

# 部署信息
binary:    backend/bin/qdrant          (aarch64-apple-darwin)
config:    backend/qdrant_config.yaml
storage:   backend/data/qdrant/        (持久化到磁盘)
HTTP port: 6333
gRPC port: 6334

# 降级策略
Qdrant OK  →  HNSW 精确向量检索 (sub-ms)
Qdrant 不可用  →  numpy 余弦相似度 (内存 dict)
```

---

## 六、Bug 修复与优化清单

| 优先级 | 问题 | 位置 | 状态 |
|:------:|:-----|:-----|:----:|
| 🔴 P0 | `audio_service.extract_audio_feature_vector()` 缺失导致 AttributeError | `audio_service.py` | ✅ 已修复 |
| 🔴 P0 | `progressive_indexer.index_file()` 缺失，/index 端点崩溃 | `progressive_indexer.py` | ✅ 已修复 |
| 🔴 P0 | `EmbeddingWrapper.predict()` 返回随机哈希向量 | `embedding.py` | ✅ 接入真实模型 |
| 🟡 P1 | `BatchProcessor` 有入队但无消费者 worker 线程 | `batch_processor.py` | ✅ 已修复 |
| 🟡 P1 | `requirements.txt` 缺少 `opencv-python`, `Pillow`, `diskcache` | `requirements.txt` | ✅ 已补全 |
| 🟡 P1 | `/metrics` 返回硬编码静态文本 | `server.py` | ✅ 动态实现 |
| 🟡 P1 | VLM `max_tokens=200` 硬编码 | `progressive_indexer.py` | ✅ 已调整为 512 |
| 🟢 P2 | App.tsx 单文件 1868 行 | `frontend/src/` | 📋 规划中 |
| 🟢 P2 | Qdrant 未安装，向量重启丢失 | 部署层 | 📋 规划中 |
