# 本地模型目录结构

本项目支持在 Apple Silicon (Metal GPU) 与通用 Linux/Mac 上本地运行多模态模型。
由于模型权重文件体积较大（约 17GB），不纳入 Git 版本控制。

## 模型放置路径结构

```
backend/models/
├── mlx_model/                  # Qwen/Qwen3-VL-8B-Instruct-4bit (MLX 格式)
│   ├── config.json
│   ├── model.safetensors
│   └── tokenizer.json
├── qwen3_vl_embedding_8b/      # Qwen3-VL-Embedding-8B (2048d 稠密特征)
├── reranker_model/             # Qwen3-VL-Reranker-2B (Cross-Encoder 精排)
├── clap_model/                 # laion/larger_clap_general (512d 音频特征)
└── bonsai_8b_mlx/              # Bonsai-8B-MLX / Qwen3-8B (自然语言推荐解释生成)
```

## 模型下载指南

可以使用 `huggingface-cli` 或 `modelscope` 下载对应模型权重至上述目录：

```bash
# 1. 下载 Qwen3-VL-8B MLX
huggingface-cli download mlx-community/Qwen3-VL-8B-Instruct-4bit --local-dir backend/models/mlx_model

# 2. 下载 Qwen3-VL-Reranker
huggingface-cli download Qwen/Qwen3-VL-Reranker-2B --local-dir backend/models/reranker_model

# 3. 下载 LAION-CLAP
huggingface-cli download laion/larger_clap_general --local-dir backend/models/clap_model
```
