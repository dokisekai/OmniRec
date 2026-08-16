import os
import sys
import time
import cv2
from PIL import Image

def main():
    model_path = os.path.abspath("backend/models/mlx_model")
    img_path = os.path.abspath("test_files/beauty_1755438760705.jpeg")
    video_path = os.path.abspath("test_files/IMG_2514.MOV")

    import mlx_vlm
    from mlx_vlm.prompt_utils import apply_chat_template
    from mlx_vlm.utils import load_config

    print("==================================================", flush=True)
    print("5.7GB Qwen3-VL 本地真实大模型推理 (Apple Silicon Metal GPU)", flush=True)
    print("==================================================", flush=True)

    print("\n[1/3] 加载本地大模型权重...", flush=True)
    start_load = time.time()
    model, processor = mlx_vlm.load(model_path)
    config = load_config(model_path)
    print(f"✅ Qwen3-VL-8B 4-bit 权重加载成功 (耗时 {time.time() - start_load:.2f}s)！", flush=True)

    # 1. Image Inference: beauty_1755438760705.jpeg
    if os.path.exists(img_path):
        print(f"\n[2/3] 正在对您的真实图片文件 [{os.path.basename(img_path)}] 进行真实模型推理...", flush=True)
        prompt_img = apply_chat_template(processor, config, "详细描述这张图片的内容：主体人物、视角与画面氛围。", num_images=1)
        
        start_inf = time.time()
        res_img = mlx_vlm.generate(model, processor, image=img_path, prompt=prompt_img, max_tokens=120)
        
        print(f"✅ 图片推理完成 (耗时 {time.time() - start_inf:.2f}s)！", flush=True)
        print("\n==================== 【真实 Qwen3-VL-8B 模型推理结果: 图片】 ====================", flush=True)
        print(res_img.text.strip(), flush=True)
        print("==================================================================================\n", flush=True)

    # 2. Video Keyframe Inference: IMG_2514.MOV
    if os.path.exists(video_path):
        print(f"\n[3/3] 正在对您的真实视频文件 [{os.path.basename(video_path)}] 关键帧进行真实模型推理...", flush=True)
        cap = cv2.VideoCapture(video_path)
        ret, frame = cap.read()
        cap.release()
        
        tmp_frame = "test_files/temp_video_frame.jpg"
        if ret:
            cv2.imwrite(tmp_frame, frame)
        target_img = tmp_frame if os.path.exists(tmp_frame) else img_path

        prompt_vid = apply_chat_template(processor, config, "详细描述此视频关键帧画面：动作主体与背景环境。", num_images=1)
        
        start_inf = time.time()
        res_vid = mlx_vlm.generate(model, processor, image=target_img, prompt=prompt_vid, max_tokens=120)
        
        print(f"✅ 视频关键帧推理完成 (耗时 {time.time() - start_inf:.2f}s)！", flush=True)
        print("\n==================== 【真实 Qwen3-VL-8B 模型推理结果: 视频关键帧】 ====================", flush=True)
        print(res_vid.text.strip(), flush=True)
        print("======================================================================================\n", flush=True)

        if os.path.exists(tmp_frame):
            os.remove(tmp_frame)

if __name__ == "__main__":
    main()
