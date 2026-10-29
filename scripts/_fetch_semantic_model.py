"""下载本地语义模型 paraphrase-multilingual-MiniLM-L12-v2（重试+续传，hf-mirror）。"""
import os
import sys
import time
from pathlib import Path

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["HF_HUB_DOWNLOAD_TIMEOUT"] = "120"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "models" / "semantic" / "paraphrase-multilingual-MiniLM-L12-v2"
DEST.mkdir(parents=True, exist_ok=True)

from huggingface_hub import hf_hub_download

REPO = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
FILES = ["config.json", "sentence_bert_config.json", "modules.json", "tokenizer.json",
         "tokenizer_config.json", "special_tokens_map.json",
         "pytorch_model.bin"]

for fname in FILES:
    final = DEST / fname
    if final.exists() and final.stat().st_size > 1000:
        print(f"SKIP {fname}")
        continue
    ok = False
    for attempt in range(1, 11):
        try:
            print(f"[{attempt}] {fname} ...")
            p = hf_hub_download(repo_id=REPO, filename=fname, local_dir=str(DEST))
            print(f"    OK -> {p}")
            ok = True
            break
        except Exception as e:  # noqa: BLE001
            print(f"    失败: {type(e).__name__}: {str(e)[:100]}")
            time.sleep(4 * attempt)
    if not ok:
        sys.exit(f"下载失败: {fname}")

print("语义模型下载完成。")
