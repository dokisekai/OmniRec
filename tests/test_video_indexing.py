import os
import logging
from src.services.video_service import video_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def main():
    mov_path = os.path.abspath("test_files/IMG_2514.MOV")
    print("==================================================", flush=True)
    print(f"测试 VideoService 处理真实视频文件: {mov_path}", flush=True)
    print("==================================================", flush=True)

    try:
        res = video_service.process_video(mov_path)
        print("✅ VideoService 执行成功！", flush=True)
        print("视频时长:", res.duration_sec)
        print("提取关键帧数:", res.extracted_frames)
        print("视频总结:\n", res.frame_descriptions)
    except Exception as e:
        print("❌ VideoService 抛出错误:", e, flush=True)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
