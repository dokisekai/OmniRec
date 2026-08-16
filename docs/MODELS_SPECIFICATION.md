# 🧠 多模态推荐系统 · 全模型选型与技术规格说明书

## 1. 架构总览与隐私安全原则

本项目为**全本地化、私有部署的多模态 AI 推荐与检索系统**，专为 Apple Silicon (Metal GPU) 与生产级本地服务器设计。

### 🔒 核心隐私与数据安全保证
- **零云端外传**：所有用户的原始视频、图片、音频均在本地服务器执行特征提取与向量化，**绝对不向任何公有云 API 上传媒体文件**。
- **Git / 云存储隔离**：工程已在 `.gitignore` 中对所有多媒体格式（`.mp4`, `.MOV`, `.jpeg`, `.wav` 等）及权重缓存进行全局物理屏蔽，防止数据意外泄露。
- **全离线闭环运行**：所有 6 个深度学习模型均在本地显存常驻运行，支持断网离线环境下的全量推理。

---

## 2. 六大模型矩阵与显存预算分配 (12.0GB / 20.0GB)

系统在 Apple Silicon 统一内存（Unified Memory）中常驻 6 个核心模型，总常驻显存为 **12.0 GB**（严格控制在 20.0 GB 预算阈值内），支持并发低延迟调用：

```
统一内存预算: 12.0 GB 常驻 / 20.0 GB 上限 (Apple M 系列 24GB~64GB)
├── [VLM 视觉理解]      Qwen3-VL-8B-Instruct (4-bit MLX Metal)       5.4 GB
├── [稠密向量嵌入]      Qwen3-VL-Embedding-8B (2048d MRL)            2.0 GB
├── [Cross-Encoder 精排] Qwen3-VL-Reranker-2B                         2.0 GB
├── [推荐理由推理]      Bonsai-8B-MLX / Qwen3-8B                      1.3 GB
├── [语音转写 ASR]      Whisper-large-v3 + Silero-VAD                 0.7 GB
└── [声学特征 CLAP]     LAION-CLAP (512d 音频空间)                    0.6 GB
```

---

## 3. 各模型详细技术选型与职责

| 模态 / 能力 | 选型模型 | 格式 / 后端 | 向量维度 / 输出 | 显存占用 | 核心职责 |
| :--- | :--- | :--- | :--- | :---: | :--- |
| **1. 视觉多模态 (VLM)** | `Qwen3-VL-8B-Instruct` | 4-bit 量化 (MLX GPU) | 富文本描述 + 6维标签 | **5.4 GB** | 视频关键帧/图片深度理解，提取主体、色彩光影、场景、情绪、构图、实体 6 维结构化标签。 |
| **2. 语义向量 (Embedding)** | `Qwen3-VL-Embedding-8B` | 2048d / MRL (Transformers) | 2048 维稠密特征向量 | **2.0 GB** | 将图文内容统一映射至 2048 维高维语义多模态空间，写入 Qdrant HNSW 索引。 |
| **3. 跨模态精排 (Reranker)** | `Qwen3-VL-Reranker-2B` | Cross-Encoder (PyTorch) | 0~1 交叉注意力相关度 | **2.0 GB** | 对检索召回的 Top-N 候选视频与查询文本/图片进行深度交叉比对，提高首屏命中率。 |
| **4. 推荐理由生成 (LLM)** | `Bonsai-8B-MLX / Qwen3-8B`| 4-bit MLX / 本地模板推理 | 自然语言推荐解释 | **1.3 GB** | 解释为什么推荐该视频（例如：“同样具有明媚的海边落日风光与清爽夏日穿搭”）。 |
| **5. 语音转写 (ASR)** | `Whisper-large-v3` + `Silero-VAD` | PyTorch / MLX | 语音对白台词文本 | **0.7 GB** | 自动过滤静音区，定位 30s 能量高潮区，精准转写视频口播对白与歌词。 |
| **6. 音乐声学 (CLAP)** | `LAION-CLAP-General` | 512d (Transformers) | 512 维音频特征向量 | **0.6 GB** | 提取背景音乐 BGM、音效、环境音特征，支持“以歌搜片”与音乐相似度推荐。 |

---

## 4. 模型目录与下载指引

本地模型权重均存放在 `backend/models/` 目录下（已被 git 忽略）：

```
backend/models/
├── mlx_model/                  # Qwen3-VL-8B 4-bit (MLX 权重)
├── qwen3_vl_embedding_8b/      # Qwen3-VL-Embedding (2048d)
├── reranker_model/             # Qwen3-VL-Reranker-2B (Cross-Encoder)
├── clap_model/                 # LAION-CLAP (512d 音频)
└── bonsai_8b_mlx/              # 本地自然语言推理模型
```

### 快捷下载命令（使用 HuggingFace CLI）
```bash
# 1. 安装下载工具
pip install -U huggingface_hub

# 2. 下载 Qwen3-VL-8B MLX 模型
huggingface-cli download mlx-community/Qwen3-VL-8B-Instruct-4bit --local-dir backend/models/mlx_model

# 3. 下载 Qwen3-VL-Reranker 精排模型
huggingface-cli download Qwen/Qwen3-VL-Reranker-2B --local-dir backend/models/reranker_model

# 4. 下载 LAION-CLAP 音频模型
huggingface-cli download laion/larger_clap_general --local-dir backend/models/clap_model
```

---

## 5. 推理加速与内存管理机制

1. **图像自适应缩放（防 Patch 爆炸）**：
   - 原始 4K/12MP 相机大图在送入 VLM 前，系统自动将其长边等比缩放至 `1024px`，将 Vision Patch 从 2000+ 骤降至 ~250，单张图片推理时间从 **3.5 分钟降至 2.5 秒**（提速 50 倍且不丢失语义细节）。
2. **L1 / L2 / L3 渐进式索引架构**：
   - **L1 快速建档 (<10ms)**：即时计算 MD5 + 视觉哈希 + 主色调，立即返回 HTTP 200。
   - **L2 深度推演 (异步后台任务)**：GPU 后台调用 Qwen3-VL-8B 提取 6 维结构化标签并写入 Qdrant。
   - **L2 磁盘持久化 (DiskCache)**：重复上传相同 MD5 文件可在 `<5ms` 内秒级恢复，零 GPU 消耗。
