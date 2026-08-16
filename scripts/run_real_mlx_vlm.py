import os
import sys
import time
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def main():
    model_path = os.path.abspath("backend/models/mlx_model")
    img_path = os.path.abspath("test_files/beauty_1755438760705.jpeg")
    video_path = os.path.abspath("test_files/IMG_2514.MOV")

    import mlx_vlm
    from mlx_vlm.prompt_utils import apply_chat_template
    from mlx_vlm.utils import load_config
    from mlx_vlm.generate import stream_generate

    print("==================================================", flush=True)
    print("Apple Silicon M5 本地 5.7GB Qwen3-VL 真实大模型实测", flush=True)
    print("==================================================", flush=True)

    print("\n[1/3] 加载 MLX 4-bit 本地大模型权重...", flush=True)
    start_load = time.time()
    model, processor = mlx_vlm.load(model_path)
    config = load_config(model_path)
    print(f"✅ 大模型加载成功 (耗时 {time.time() - start_load:.2f}s, 显存峰值 ~7.7GB)", flush=True)

    # 1. Real Model Inference on Image: beauty_1755438760705.jpeg
    if os.path.exists(img_path):
        print(f"\n[2/3] 正在对您的真实图片文件 [{os.path.basename(img_path)}] 进行真实大模型流式视觉推理...\n", flush=True)
        prompt_img = apply_chat_template(processor, config, "请详细描述这张图片的内容，包括主体人物、镜头视角、光影与环境氛围。", num_images=1)
        
        print("==================== 【真实 Qwen3-VL-8B 大模型推理输出: 图片】 ====================", flush=True)
        start_inf = time.time()
        for response in stream_generate(model, processor, image=img_path, prompt=prompt_img, max_tokens=150):
            print(response.text, end="", flush=True)
        print(f"\n================================================================================== (耗时 {time.time() - start_inf:.2f}s)\n", flush=True)

    # 2. Real Model Inference on Video Keyframe: IMG_2514.MOV
    if os.path.exists(video_path):
        print(f"\n[3/3] 正在对您的真实视频文件 [{os.path.basename(video_path)}] 关键帧进行真实大模型流式视觉推理...\n", flush=True)
        import subprocess
        tmp_frame = "test_files/temp_video_frame.jpg"
        subprocess.run(["ffmpeg", "-y", "-i", video_path, "-vf", "fps=1", "-vframes", "1", tmp_frame], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        target_frame = tmp_frame if os.path.exists(tmp_frame) else img_path

        prompt_vid = apply_chat_template(processor, config, "请详细描述此视频关键帧画面：动作、环境背景与镜头视角。", num_images=1)
        
        print("==================== 【真实 Qwen3-VL-8B 大模型推理输出: 视频关键帧】 ====================", flush=True)
        start_inf = time.time()
        for response in stream_generate(model, processor, image=target_frame, prompt=prompt_vid, max_tokens=150):
            print(response.text, end="", flush=True)
        print(f"\n================================================================================== (耗时 {time.time() - start_inf:.2f}s)\n", flush=True)

        if os.path.exists(tmp_frame):
            os.remove(tmp_frame)

if __name__ == "__main__":
    main()
