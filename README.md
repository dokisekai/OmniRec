# Antigravity 多模态推荐与检索系统 (Multimodal Recommender)

> 🚀 本地全量私有化部署 · Apple Silicon (Metal GPU) 优化 · 六大模型矩阵 · 零云端依赖与数据防泄露

---

## 🔒 隐私与本地数据安全声明
- **严禁云端外传**：所有用户的原始视频、图片、音频及特征向量**全流程在本地闭环运行**，绝对不向任何外部公有云上传媒体数据。
- **本地存储物理隔离**：`.gitignore` 已全局屏蔽所有音视频格式（`.mp4`, `.MOV`, `.jpeg`, `.wav` 等）及 17GB 模型权重，杜绝私密媒体文件被误推至 Git 仓库。

---

## 📁 规范项目目录结构

```
multimodal-recommender/
├── backend/                     # 后端核心服务
│   ├── main.py                  # 服务统一启动入口
│   ├── requirements.txt         # Python 依赖清单
│   ├── qdrant_config.yaml       # Qdrant 向量数据库配置
│   ├── models/                  # 本地 6 大模型权重目录 (本地私有)
│   │   └── README.md            # 模型存放结构与下载指南
│   └── src/
│       ├── api/server.py        # FastAPI 路由与 WebSocket 状态广播
│       ├── core/                # 配置中心、内存管理器 (MemoryManager)、Schema
│       ├── models/              # VLM、Embedding、Reranker、CLAP、Whisper、LLM 封装
│       ├── pipeline/            # 渐进式索引 (L1/L2)、HSV关键帧抽取、VAD音频能量定位
│       ├── engine/              # 检索引擎 (RRF融合)、推荐引擎 (MMR多样性+租户过滤)
│       ├── vector_db/           # Qdrant 客户端 (命名空间隔离、HNSW量化)
│       └── cache/               # L2 磁盘持久化缓存
├── frontend/                    # 前端 Web 控制台
│   ├── src/App.tsx              # React 19 + Tailwind/Vanilla CSS 控制台界面
│   ├── vite.config.ts           # Vite 构建与 WebSocket 反向代理配置
│   └── dist/                    # 前端编译生产包
├── scripts/                     # 独立模型推演与测试验证脚本
│   ├── run_real_model_inference_all.py
│   ├── run_real_mlx_vlm.py
│   ├── run_complete_real_inference.py
│   └── run_direct_vlm_test.py
├── docs/                        # 架构设计与业务对接规范文档
│   ├── MODELS_SPECIFICATION.md  # 六大模型技术规格与显存预算分配说明书
│   ├── ARCHITECTURE.md          # 详细系统架构与分层设计文档
│   └── 业务对接说明.md          # 咪咕/统一推荐平台三方对接业务规范
└── test_files/                  # 本地私有测试媒体文件 (已 gitignore 屏蔽)
```

---

## 🧠 六大核心模型矩阵 (12.0GB 常驻 / 20.0GB 预算)

| 模态 / 能力 | 模型名称 | 后端 / 量化 | 显存占用 | 功能描述 |
| :--- | :--- | :--- | :---: | :--- |
| **VLM 视觉多模态** | `Qwen3-VL-8B-Instruct` | 4-bit (MLX GPU) | **5.4 GB** | 视频关键帧/图片深度分析，提炼 6 维结构化标签 |
| **稠密向量编码** | `Qwen3-VL-Embedding-8B`| 2048d (MRL) | **2.0 GB** | 图文特征统一映射至 2048 维空间，存入 Qdrant |
| **跨模态精排** | `Qwen3-VL-Reranker-2B` | Cross-Encoder | **2.0 GB** | 候选视频与查询跨模态交叉打分 |
| **推荐理由生成** | `Bonsai-8B-MLX / Qwen3-8B` | 4-bit MLX | **1.3 GB** | 生成可解释性自然语言推荐理由 |
| **语音识别转写** | `Whisper-large-v3` | PyTorch + VAD | **0.7 GB** | 视频对白台词自动转写 |
| **声学特征编码** | `LAION-CLAP-General` | 512d | **0.6 GB** | BGM 背景音乐与声学氛围提取 |

> 详情见 [docs/MODELS_SPECIFICATION.md](docs/MODELS_SPECIFICATION.md)。

---

## ⚡ 快速启动指南

### 1. 安装环境依赖
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
```

### 2. 启动 Qdrant 向量数据库
```bash
cd backend && ./bin/qdrant --config-path qdrant_config.yaml &
cd ..
```

### 3. 启动后端服务
```bash
python backend/main.py
```

### 4. 访问交互控制台
打开浏览器访问：[http://localhost:8000/](http://localhost:8000/) 或 [http://localhost:5174/](http://localhost:5174/)。
