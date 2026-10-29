"""下载 F5-TTS 权重（hf-mirror，带重试与断点续传）：
  models/f5/F5TTS_v1_Base/model_1250000.safetensors
  models/f5/F5TTS_v1_Base/vocab.txt
  models/f5/vocos-mel-24khz/{config.json, model.safetensors}
"""
import os
import sys
import time
from pathlib import Path

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["HF_HUB_DOWNLOAD_TIMEOUT"] = "60"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "models" / "f5"
MODELS.mkdir(parents=True, exist_ok=True)

from huggingface_hub import hf_hub_download

TARGETS = [
    ("SWivid/F5-TTS", "F5TTS_v1_Base/model_1250000.safetensors", MODELS / "F5TTS_v1_Base"),
    ("SWivid/F5-TTS", "F5TTS_v1_Base/vocab.txt", MODELS / "F5TTS_v1_Base"),
    ("charactr/vocos-mel-24khz", "config.yaml", MODELS / "vocos-mel-24khz"),
    ("charactr/vocos-mel-24khz", "pytorch_model.bin", MODELS / "vocos-mel-24khz"),
]

for repo, filename, dest_dir in TARGETS:
    dest_dir.mkdir(parents=True, exist_ok=True)
    final = dest_dir / filename
    if final.exists() and final.stat().st_size > 1024 * 1024:
        print(f"SKIP（已存在）: {filename}")
        continue
    ok = False
    for attempt in range(1, 13):
        try:
            print(f"[{attempt}] {repo} :: {filename} ...")
            p = hf_hub_download(repo_id=repo, filename=filename, local_dir=str(dest_dir))
            print(f"    OK -> {p}")
            ok = True
            break
        except Exception as e:
            print(f"    失败: {type(e).__name__}: {str(e)[:120]}")
            time.sleep(3 * attempt)
    if not ok:
        sys.exit(f"下载失败（重试 12 次）: {filename}")

print("全部模型文件就绪。")
