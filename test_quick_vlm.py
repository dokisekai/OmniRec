import os
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

from src.models.vlm import VLMWrapper

def main():
    img_path = os.path.abspath("test_files/beauty_1755438760705.jpeg")
    print("==================================================", flush=True)
    print("测试 VLMWrapper 本地 5.7GB 模型实时推理", flush=True)
    print("==================================================", flush=True)

    vlm = VLMWrapper()
    vlm.load()
    
    print("\n开始向 Apple Silicon GPU 发送图像推演...", flush=True)
    res_text = vlm.predict(img_path, prompt="用一句话描述这张图片的主体与氛围。", max_tokens=50)
    
    print("\n==================== 【Qwen3-VL 8B 真实模型推演输出】 ====================", flush=True)
    print(res_text, flush=True)
    print("==========================================================================", flush=True)

if __name__ == "__main__":
    main()
