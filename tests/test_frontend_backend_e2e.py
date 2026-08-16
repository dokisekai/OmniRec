import os
import time
import logging
from fastapi.testclient import TestClient
from src.api.server import app

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("test_e2e")

def main():
    client = TestClient(app)
    img_path = os.path.abspath("test_files/beauty_1755438760705.jpeg")

    print("==================================================", flush=True)
    print("模拟前端 React 发起 /api/v1/upload 二进制文件上传与大模型实测", flush=True)
    print("==================================================", flush=True)

    with open(img_path, "rb") as f:
        files = {"file": (os.path.basename(img_path), f, "image/jpeg")}
        data = {"media_type": "image"}
        
        start_time = time.time()
        print("► 正在向后端 POST /api/v1/upload 发送 FormData 二进制文件...", flush=True)
        response = client.post("/api/v1/upload", files=files, data=data)
        elapsed = time.time() - start_time

    print(f"✅ 后端响应成功！HTTP 状态码: {response.status_code} (总耗时 {elapsed:.2f}s)", flush=True)
    res_json = response.json()
    
    print("\n==================== 【前端接收到的真实 JSON 响应数据】 ====================")
    print(f"Status: {res_json.get('status')}")
    print(f"Saved Path: {res_json.get('saved_path')}")
    
    idx = res_json.get("index_result", {})
    print(f"Indexed Item ID: {idx.get('item_id')}")
    print(f"VLM 原生大模型描述:\n{idx.get('description')}\n")
    print(f"6 大维度分类标签 (Categorized Tags):")
    import json
    print(json.dumps(idx.get("categorized_tags", {}), ensure_ascii=False, indent=2))
    print(f"Hex 图片主色调: {idx.get('dominant_colors')}")
    print("============================================================================\n")

if __name__ == "__main__":
    main()
