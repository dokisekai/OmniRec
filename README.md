# Antigravity 多模态推荐与检索系统

> 本地部署 · Apple Silicon 优化 · 多模态 AI · 零网络依赖

## 快速启动

```bash
# 安装依赖
cd multimodal-recommender
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt

# 1. 启动 Qdrant 向量数据库 (持久化 HNSW 索引)
cd backend && ./bin/qdrant --config-path qdrant_config.yaml &
cd ..

# 2. 启动后端服务
python backend/main.py

# 访问前端
open http://localhost:8000
```

## 系统能力

| 能力 | 实现方式 |
|:-----|:---------|
| 📸 图片深度理解 | Qwen3-VL-8B MLX 4-bit (5.4GB GPU) |
| 🎬 视频关键帧分析 | FFmpeg 抽帧 + 逐帧 VLM 推演 |
| 🎵 音频特征提取 | LAION CLAP 512d + Whisper ASR |
| 🎯 2048d 稠密向量 | Qwen3-VL-Embedding (MRL) |
| 🔍 语义检索 | RRF 多路召回 + 重排 |
| 💡 关联推荐 | Item-to-Item MMR 多样性重排 |
| 📡 实时状态 | WebSocket 推理进度流 |

## 执行模式

| 模式 | 命令参数 | 耗时 | 适用场景 |
|:-----|:---------|:----:|:---------|
| 全流程推荐 | `mode=full` | ~秒级 | 完整多模态体验 |
| 仅大模型分析 | `mode=vlm_only` | ~秒级 | 生成图文描述与标签 |
| 仅快速向量 | `mode=fast_vector` | <50ms | 大批量快速入库 |
| 仅嵌入向量 | `mode=embedding_only` | ~100ms | 纯向量检索 |

## 模型矩阵

```
显存预算: 12.0 GB / 20.0 GB (Apple M 系 24GB)
├── Qwen3-VL-8B MLX       5.4 GB  VLM 视觉理解
├── Qwen3-VL-Embedding     2.0 GB  2048d 语义向量
├── Qwen3-VL-Reranker      2.0 GB  精排
├── Bonsai-8B-MLX          1.3 GB  推理 LLM
├── Whisper-large-v3       0.7 GB  ASR 转写
└── LAION CLAP             0.6 GB  音频特征
```

## API 接口

| 方法 | 路径 | 功能 |
|:-----|:-----|:-----|
| POST | `/api/v1/upload` | 文件上传与渐进式索引 |
| POST | `/api/v1/analyze` | 纯 VLM 推演（不入库） |
| POST | `/api/v1/embed` | 2048d 向量生成 |
| POST | `/api/v1/search` | 多模态语义检索 |
| POST | `/api/v1/recommend` | Item-to-Item 推荐 |
| GET | `/api/v1/items` | 索引列表 |
| DELETE | `/api/v1/items/{id}` | 删除条目 |
| WS | `/ws/progress` | 实时推理进度 |
| GET | `/docs` | Swagger UI |
| GET | `/metrics` | Prometheus 指标 |

## 架构文档

详见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## 目录结构

```
multimodal-recommender/
├── backend/
│   ├── main.py                  # 服务入口
│   ├── requirements.txt         # Python 依赖
│   ├── models/                  # 本地模型权重
│   │   ├── mlx_model/           # Qwen3-VL-8B MLX 4-bit
│   │   ├── qwen3_vl_embedding_8b/
│   │   ├── reranker_model/
│   │   └── clap_model/
│   └── src/
│       ├── api/server.py        # FastAPI 路由
│       ├── core/                # 配置、内存管理、Schema
│       ├── models/              # VLM、Embedding 封装
│       ├── pipeline/            # 渐进式索引、标签生成
│       ├── services/            # 图片、视频、音频服务
│       ├── engine/              # 检索、推荐引擎
│       ├── vector_db/           # Qdrant 客户端
│       └── cache/               # L2 磁盘缓存
├── frontend/
│   └── src/App.tsx              # React 19 单文件应用
├── docs/
│   └── ARCHITECTURE.md          # 系统架构文档
└── test_files/                  # 测试媒体文件
```
