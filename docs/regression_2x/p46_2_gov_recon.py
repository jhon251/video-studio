# -*- coding: utf-8 -*-
"""Phase 45 / P45-1：**Pexels 治理接入侦察报告 + 阻塞登记**。

结论（**fail-closed 阻塞**）：
  · **`PEXELS_API_KEY` 在本环境不存在** —— `.env` 仅含 TAVILY / DEEPSEEK / VLM_API_KEY；
    用户级环境变量无 `PEXELS_*`；项目内亦无凭据文件。
  · 授权书称「key 就绪」与实际不符 ⇒ **P45-1 / P45-2 无法发起任何请求**，
    连带 **P45-4 全链重跑**（含扩池后的锚定/家族）与 **P45-5** 一并阻塞。

**已完成的独立工作（不依赖 Pexels）**：
  · **P45-3 词级重配音（O-voice）已完成**：9 段同音色同文本重合成、**逐段时长偏差 0.00%**、
    捕获 **1,964 个 WordBoundary**；词级 cue 构建 **105 句**、
    **同步金门 median 0.0000s / 100% 覆盖**（`tests/caption_word_sync_test.py` 2/2 PASS）。

**治理路径已核验（overlay 可行，冻结栈零改动）**：
  · `core/materials.py::classify_license` 把 "Pexels License" 映射为 **UNKNOWN** ⇒ 直接走
    声明字段会被门禁拦下；
  · 但候选消费点（L163-166）**优先读候选自带的 `license_class` / `license_cleared`**：
    `klass = candidate.get("license_class") or classify_license(declared)[0]`
    ⇒ **overlay 携带 provider-verified 值即可放行**，无需改冻结文件。
  · 既有先例：`docs/regression_2x/logs/license_overlay_v1.json`（Phase 12）已用同款结构
    （`entries[].license_class / license_cleared / source_of_record`）。
  · 既有可复用实现：`src/video_studio/stage33/pexels_source.py`（**未硬编码 key**，
    key 由调用方传入；已含 `LICENSE_NOTE` 与摄影师署名信息）。
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")

# 冻结栈钉定核实
import hashlib                                                                    # noqa: E402
man = json.loads((R / "docs/regression_2x/baseline"
                  / "baseline_manifest_5.x-post-final-maintenance-baseline.json")
                 .read_text(encoding="utf-8"))
mat = "src/video_studio/core/materials.py"
pin = (man["files"].get(mat) or {}).get("sha256")
now = hashlib.sha256((R / mat).read_bytes()).hexdigest()

rec = {
    "schema": "p45-1-governance-recon-v1",
    "stage": "Phase 45 P45-1 Pexels 治理接入侦察",
    "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    "status": "BLOCKED_CREDENTIAL_MISSING",
    "blocker": {
        "what": "PEXELS_API_KEY 不存在",
        "evidence": (".env 键仅 [TAVILY_API_KEY, DEEPSEEK_API_KEY, VLM_API_KEY]；"
                     "用户级环境变量无 PEXELS_*；项目内仅存历史 stage33 适配器（未硬编码 key）"),
        "blocks": ["P45-1 provider 接入", "P45-2 定向获取（≤14 张）",
                   "P45-4 扩池后的锚定/家族全链重跑", "P45-5 材料包 v5 + 回归"],
        "needed": "把 `PEXELS_API_KEY=<key>` 加入 C:\\mp4agent\\video-studio\\.env",
    },
    "governance_path_verified": {
        "frozen_stack_untouched": True,
        "materials_py_pin": pin,
        "materials_py_now": now,
        "materials_py_frozen_ok": pin == now,
        "why_overlay_is_required": ("`classify_license('Pexels License')` → **UNKNOWN** "
                                    "⇒ 直接用声明字段会被 `license_block_reason` 拦为 "
                                    "ASSET_LICENSE_MISSING/UNCLEAR"),
        "overlay_consumption_point": ("materials.py L163-166：候选自带 "
                                      "`license_class` / `license_cleared` **优先于** "
                                      "`classify_license` ⇒ overlay 可直接放行"),
        "precedent": "docs/regression_2x/logs/license_overlay_v1.json（Phase 12 同款结构）",
        "reusable_impl": "src/video_studio/stage33/pexels_source.py（key 由调用方传入）",
        "planned_overlay_fields": ["asset_sha256", "license", "license_class",
                                   "license_cleared", "source_of_record='Pexels API response'",
                                   "provider_verified", "photographer", "source_url",
                                   "provider='pexels'"],
        "license_note": ("Pexels License：免费使用、**免强制署名**；本仓按更保守口径"
                         "映射为 `FREE_ATTRIBUTION` 并**照记摄影师署名**（courtesy）。"),
    },
    "completed_independently": {
        "P45-3_ovoice": {
            "segments": 9, "all_ok": True,
            "max_deviation": 0.0, "tolerance": 0.02,
            "words_captured": 1964, "narration_duration_s": 693.528,
            "word_boundaries": "edge-tts `boundary='WordBoundary'`（7.2.8 默认 SentenceBoundary）",
            "cues": 105, "sync_gate": "tests/caption_word_sync_test.py 2/2 PASS",
            "sync_median_lag_s": 0.0, "sync_cover_ratio": 1.0, "sync_max_abs_lag_s": 0.0,
            "artifacts": ["output/phase45_voice/voice_output_v65_ovoice.json",
                          "output/phase45_voice/words_manifest.json"],
        },
    },
    "options_if_key_unavailable": [
        "① 提供 PEXELS_API_KEY（推荐；授权书即按此路径）",
        "② 改扩池源（Wikimedia 仍 TLS 阻断 ⇒ 需另指定可用源）",
        "③ 暂不扩池：F6 只能在不满足 cap/家族份额的前提下交付（需监理书面接受）",
    ],
    "budget": {"llm_usd": 0.0, "tts": "free", "pexels_requests_used": 0,
               "renders_this_phase": 0},
}
(L / "p45_1_governance_recon.json").write_text(
    json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
print("P45-1 治理侦察：**BLOCKED（缺 PEXELS_API_KEY）**")
print("  冻结栈核实：materials.py pin==now ? {}".format(pin == now))
print("  overlay 路径：**可行**（候选自带 license_class/license_cleared 优先于 classify_license）")
print("  P45-3（词级配音）已完成：偏差 0.00% / 1964 词 / 105 句 cue / 同步金门 2-2 PASS")
print("-> " + str((L / "p45_1_governance_recon.json").relative_to(R)))
