import os
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

from src.services.image_service import image_service

def main():
    img_path = os.path.abspath("test_files/beauty_1755438760705.jpeg")
    print("==================================================", flush=True)
    print("测试后端 ImageService -> VLMWrapper 真实大模型调用", flush=True)
    print("==================================================", flush=True)

    result = image_service.process_image(img_path)
    print("\n==================== 【后端真实 Qwen3-VL-8B 推理输出】 ====================")
    print(result.description)
    print("============================================================================")
    print("\n抽取标签:", result.tags)

if __name__ == "__main__":
    main()
