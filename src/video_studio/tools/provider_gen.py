# -*- coding: utf-8 -*-
"""Phase 47 / P47-1：**文生图 provider**（`tools/provider_gen.py` 对齐契约）。

契约（与既有 provider 一致）：
  · API key 只从环境变量读（`DASHSCOPE_API_KEY`，缺则回退同平台 `VLM_API_KEY`）；
  · 超时 / 重试 / 尺寸校验 / **PIL 完整解码**；
  · **UTF-8 纪律**：请求体 `encode("utf-8")`，Content-Type 带 `charset=utf-8`
    （踩坑：中文提示词直接进 header 会 `UnicodeEncodeError: 'latin-1'`）；
  · 生成物溯源：`source_of_record` = 生成任务 ID，许可 = 生成物（无第三方署名义务）。

百炼（DashScope）文生图为**异步**：提交 → 轮询 `tasks/<task_id>` → 取 `results[].url`。
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import pathlib
import time
import urllib.request

API = "https://dashscope.aliyuncs.com/api/v1"
SUBMIT = API + "/services/aigc/text2image/image-synthesis"
TASK = API + "/tasks/{}"
DEFAULT_MODEL = "wanx2.1-t2i-turbo"
UA = "video-studio/1.0 (local governed pipeline)"
TIMEOUT = 60
POLL_MAX, POLL_INT = 60, 5


def api_key() -> str | None:
    return os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("VLM_API_KEY")


def _post(url: str, body: dict, key: str, async_hdr: bool = False):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    hdr = {"Authorization": "Bearer " + key,
           "Content-Type": "application/json; charset=utf-8",
           "User-Agent": UA}
    if async_hdr:
        hdr["X-DashScope-Async"] = "enable"
    req = urllib.request.Request(url, data=data, headers=hdr)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


def _get(url: str, key: str):
    req = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + key, "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


def generate(prompt: str, dest: pathlib.Path, model: str = DEFAULT_MODEL,
             size: str = "1024*1024", negative: str | None = None,
             retries: int = 2) -> dict:
    """生成一张图并落盘；返回 {ok, task_id, sha256, width, height, bytes, error}。"""
    key = api_key()
    if not key:
        return {"ok": False, "error": "缺 DASHSCOPE_API_KEY / VLM_API_KEY"}
    body = {"model": model, "input": {"prompt": prompt},
            "parameters": {"size": size, "n": 1}}
    if negative:
        body["input"]["negative_prompt"] = negative
    last = None
    for attempt in range(1, retries + 2):
        try:
            sub = _post(SUBMIT, body, key, async_hdr=True)
            task_id = ((sub.get("output") or {}).get("task_id"))
            if not task_id:
                return {"ok": False, "error": "无 task_id: {}".format(
                    json.dumps(sub, ensure_ascii=False)[:200])}
            url = None
            for _ in range(POLL_MAX):
                time.sleep(POLL_INT)
                st = _get(TASK.format(task_id), key)
                out = st.get("output") or {}
                status = out.get("task_status")
                if status == "SUCCEEDED":
                    res = out.get("results") or []
                    url = (res[0].get("url") if res else None)
                    break
                if status in ("FAILED", "CANCELED", "UNKNOWN"):
                    last = "task {} status {}: {}".format(
                        task_id, status, json.dumps(out, ensure_ascii=False)[:180])
                    break
            if not url:
                last = last or "轮询超时/无结果（task {}）".format(task_id)
                continue
            with urllib.request.urlopen(
                    urllib.request.Request(url, headers={"User-Agent": UA}),
                    timeout=TIMEOUT) as r:
                blob = r.read()
            # ---- 校验链：magic / 完整解码 ----
            # **踩坑（P47-1 实测）**：wanx 返回的是 **PNG**，即使把目标文件命名成
            # `.jpg` —— 硬编码扩展名会导致「扩展名与字节不符」（本仓图片读取器会拒读、
            # 下游按 jpg 处理也可能出问题）。故**按 magic bytes 定扩展名**，
            # 并对已存在的错误命名做**改名**。
            _png = blob[:8].startswith(b"\x89PNG")
            _jpg = blob[:3] == b"\xff\xd8\xff"
            if not (_png or _jpg):
                last = "magic bytes 不符"
                continue
            if _png and dest.suffix.lower() in (".jpg", ".jpeg"):
                dest = dest.with_suffix(".png")
            elif _jpg and dest.suffix.lower() == ".png":
                dest = dest.with_suffix(".jpg")
            try:
                from PIL import Image
                with Image.open(io.BytesIO(blob)) as im:
                    im.verify()
                with Image.open(io.BytesIO(blob)) as im:
                    w, h = im.size
                    im.load()
            except Exception as exc:                                        # noqa: BLE001
                last = "PIL 解码失败: {}: {}".format(type(exc).__name__, str(exc)[:110])
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(blob)
            return {"ok": True, "attempts": attempt, "task_id": task_id,
                    "model": model, "prompt": prompt, "size": size,
                    "sha256": hashlib.sha256(blob).hexdigest(),
                    "width": w, "height": h, "bytes": len(blob),
                    "path": str(dest)}
        except Exception as exc:                                            # noqa: BLE001
            last = "{}: {}".format(type(exc).__name__, str(exc)[:160])
            time.sleep(min(2 ** attempt, 15))
    return {"ok": False, "error": last}
