"""JARVIS 选题研究：8 个技术维度联网检索（研究侧 8E 链，非生产入口）。"""
import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from video_studio.core.env import load_env  # noqa: E402
load_env(ROOT / ".env")
from video_studio.tools.evidence_retrieval import retrieve_with_fallback, source_quality  # noqa: E402

DIMS = [
    ("nlp", "自然语言理解与对话", "大语言模型 多轮对话 能力 局限 幻觉"),
    ("memory", "长期记忆与用户建模", "AI 长期记忆 个性化 用户建模 局限"),
    ("voice", "实时语音交互", "实时语音对话 AI 延迟 语音助手 自然交互"),
    ("multimodal", "多模态视觉理解", "多模态大模型 视觉理解 能力 视频"),
    ("agent", "Agent 自主任务执行", "AI Agent 自主任务 工具调用 局限 可靠性"),
    ("device", "计算机与现实设备控制", "AI 控制电脑 手机 设备 自动化 GUI Agent"),
    ("perception", "实时环境感知", "AI 实时环境感知 传感器 智能家居 物联网"),
    ("embodied", "机器人身体与现实执行", "具身智能 机器人 现实世界 操作 进展 局限"),
]

OUT = ROOT / "output" / "production_002"
OUT.mkdir(parents=True, exist_ok=True)
all_res = {}
for key, name, query in DIMS:
    t0 = time.perf_counter()
    res = retrieve_with_fallback(query, max_usable=4, per_provider=4)
    dt = time.perf_counter() - t0
    usable = res["usable"]
    all_res[key] = {"dim": name, "query": query, "elapsed_s": round(dt, 1),
                    "usable": [{"url": e["url"], "title": e["title"], "snippet": e["snippet"],
                                "body": e["body"],
                                "tier": source_quality(e["url"], e["title"], e["body"])["tier"]}
                               for e in usable],
                    "failures": res["failures"]}
    print(f"[{key}] {name} | 可用 {len(usable)} 条 | {dt:.1f}s")
    for e in usable:
        print(f"    [{e['url'][:45]:46s}] {e['title'][:34]}")

(OUT / "research.json").write_text(json.dumps(all_res, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nresearch.json 已写入 {OUT/'research.json'}")
