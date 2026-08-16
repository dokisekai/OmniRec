import os
import sys
import mlx_vlm
from mlx_vlm.prompt_utils import apply_chat_template
from mlx_vlm.utils import load_config

model_path = os.path.abspath("backend/models/mlx_model")
img_path = os.path.abspath("test_files/beauty_1755438760705.jpeg")

model, processor = mlx_vlm.load(model_path)
config = load_config(model_path)

formatted_prompt = apply_chat_template(processor, config, "描述这张图片的内容：主体、背景与颜色氛围。", num_images=1)
print("Formatted Prompt:", repr(formatted_prompt), flush=True)

# Generate with max_tokens=60 for quick real output
output = mlx_vlm.generate(model, processor, image=img_path, prompt=formatted_prompt, max_tokens=60, verbose=True)
print("RESULT:", output, flush=True)
