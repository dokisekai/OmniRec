import os
import time
import requests

def test_file(filename, media_type):
    url = "http://localhost:8000/api/v1/upload"
    file_path = os.path.abspath(f"test_files/{filename}")
    
    print(f"\n==================================================", flush=True)
    print(f"测试真实 HTTP POST {url} 上传 {filename}", flush=True)
    print(f"==================================================", flush=True)

    with open(file_path, "rb") as f:
        files = {"file": (filename, f)}
        data = {"media_type": media_type}
        
        start = time.time()
        print("► 发送上传与 3 级渐进式向量索引请求...", flush=True)
        res = requests.post(url, files=files, data=data)
        elapsed = time.time() - start

    print(f"✅ HTTP 状态码: {res.status_code} (耗时 {elapsed:.2f}s)", flush=True)
    if res.status_code == 200:
        json_data = res.json()
        print("状态:", json_data.get("status"))
        idx = json_data.get("index_result", {})
        print("Item ID:", idx.get("item_id"))
        print("VLM 描述:\n", idx.get("description"))
        print("6 维归类标签:\n", idx.get("metadata", {}).get("categorized_tags"))
        print("主色调:", idx.get("metadata", {}).get("dominant_colors"))
    else:
        print("❌ 报错内容:\n", res.text)

if __name__ == "__main__":
    test_file("beauty_1755438760705.jpeg", "image")
