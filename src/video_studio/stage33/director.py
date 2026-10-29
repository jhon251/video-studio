"""director（v3-mvp）：LLM 输出 Visual Statement，而不是模板名。

两阶段：
  A) 全片 attention flow：每镜焦点提示 + 与上一镜关系 + climax/release 标注
  B) 逐镜 statement：七问 + 分层 + 时序 + 运动必要性 + 导演阐述

安全面：仅 http://127.0.0.1:8081；无文件系统/网络/FFmpeg；输出只进 Validator。
"""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[3]
LLAMA_SERVER = ROOT / "bin" / "llamacpp" / "llama-server.exe"
MODEL_PATH = ROOT / "models" / "llm" / "qwen2.5-3b-instruct-q4_k_m.gguf"
BASE = "http://127.0.0.1:8081"
LLM_TAG = "Qwen2.5-3B-Instruct-Q4_K_M (llama.cpp b9637)"

SYSTEM = """你是一名视频视觉导演。你的决策单位是【视觉命题 Visual Statement】，不是模板。

对每一段口播（beat），你必须回答七个问题，并用下面的结构化字段输出：
1. 这一句在叙事里做什么？（narrative_intent）
2. 观众第一眼应该看什么？为什么是它？（attention_target + attention_path：第一眼看X→第二眼理解Y）
3. 画面如何让这句话变得"可见"？画面中的证据是什么？（visual_evidence：白名单素材或口播原文中的数字/关键词）
4. 如果没有真实素材，如何用最少的视觉元素把语义演绎出来？（visual_metaphor：必须引用口播原文词；禁止发明事实）
5. 画面由哪几层组成、每层干什么？（composition.layers：background/midground/foreground，≤3 层，每层一个独立职责）
6. 这个镜头为什么接在前一个镜头之后？（relation_to_previous：continuation/contrast/escalation/release/handoff/none + explain；none 必须写清"为什么本镜独立"）
7. 运动：删除这个运动观众会损失什么？（motion.necessity 必须非空；intent ∈ attention_shift/process_expression/revelation/none；默认静止）

【铁律】
- 禁止在文本中使用任何模板/枚举名（如"图形卡/分栏/满屏/推近"之类的实现名词只允许出现在 describe 的自然语言里，且必须说明语义理由）；
- 禁止"因为这是数据句，所以用某模板"式的理由——理由必须是注意力/认知/关系语言；
- 图形层 graphic_layer.text 只放锚点词/数字（≤12 字，必须逐字来自口播原文）；画面不重复字幕全文；
- evidence_material 只能是本镜白名单 material_id 或 null；无素材时 visual_metaphor 必填且 temporal_behavior.stages ≥1；
- 你只能要求以下可执行行为之一或组合（executor 能力边界）：
  static_composition；integer_pan；integer_zoom_in/out；layered_composition(≤3层)；geometric_mask；temporal_reveal(进入/停留/揭示/退出)；emphasis；contrast_juxtaposition；keyword_dynamics(进入/点亮/淡出各一次)
- 全片节奏：高潮 = 视觉落差（前一镜压低、高潮镜骤升），不是堆更多元素；收束 = 去层+静止。

输出严格 JSON，遵守给定 schema。"""

ARC_SCHEMA = {
    "type": "object",
    "properties": {
        "flow": {"type": "array", "minItems": 1, "maxItems": 20, "items": {
            "type": "object",
            "properties": {
                "shot_id": {"type": "string"},
                "focus_hint": {"type": "string"},
                "relation_to_prev": {"type": "string", "enum": [
                    "continuation", "contrast", "escalation", "release", "handoff", "none"]},
                "relation_explain": {"type": "string"}
            },
            "required": ["shot_id", "focus_hint", "relation_to_prev", "relation_explain"]}},
        "climax_shot": {"type": "string"},
        "release_shots": {"type": "array", "items": {"type": "string"}},
        "pacing_note": {"type": "string"}
    },
    "required": ["flow", "climax_shot", "pacing_note"]
}

SHOT_SCHEMA = {
    "type": "object",
    "properties": {
        "shot_id": {"type": "string"},
        "beats": {"type": "array", "minItems": 1, "maxItems": 3, "items": {
            "type": "object",
            "properties": {
                "beat_text": {"type": "string"},
                "narrative_intent": {"type": "string"},
                "attention_target": {"type": "string"},
                "attention_path": {"type": "string"},
                "visual_evidence": {"type": "string"},
                "evidence_material": {"type": ["string", "null"]},
                "visual_metaphor": {"type": ["string", "null"]},
                "composition": {"type": "object", "properties": {
                    "layers": {"type": "array", "minItems": 1, "maxItems": 3, "items": {
                        "type": "object",
                        "properties": {
                            "role": {"type": "string", "enum": ["background", "midground",
                                                               "foreground"]},
                            "content": {"type": "string"},
                            "purpose": {"type": "string"}
                        },
                        "required": ["role", "content", "purpose"]}}},
                    "required": ["layers"]},
                "shot_language": {"type": "string"},
                "temporal_behavior": {"type": "object", "properties": {
                    "stages": {"type": "array", "minItems": 1, "maxItems": 4, "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "enum": ["enter", "hold", "reveal",
                                                                "exit"]},
                            "action": {"type": "string"},
                            "purpose": {"type": "string"}
                        },
                        "required": ["name", "action", "purpose"]}}},
                    "required": ["stages"]},
                "relation_to_previous": {"type": "object", "properties": {
                    "type": {"type": "string", "enum": [
                        "continuation", "contrast", "escalation", "release", "handoff", "none"]},
                    "explain": {"type": "string"}},
                    "required": ["type", "explain"]},
                "relation_to_next": {"type": "object", "properties": {
                    "type": {"type": "string", "enum": [
                        "continuation", "contrast", "escalation", "release", "handoff", "none"]},
                    "explain": {"type": "string"}},
                    "required": ["type", "explain"]},
                "graphic_layer": {"type": ["object", "null"], "properties": {
                    "text": {"type": "string"},
                    "purpose": {"type": "string"}},
                    "required": ["text", "purpose"]},
                "motion": {"type": "object", "properties": {
                    "necessity": {"type": "string"},
                    "intent": {"type": "string", "enum": [
                        "attention_shift", "process_expression", "revelation", "none"]},
                    "describe": {"type": "string"}},
                    "required": ["necessity", "intent", "describe"]},
                "audio_relationship": {"type": "string"},
                "director_note": {"type": "string"}
            },
            "required": ["beat_text", "narrative_intent", "attention_target", "attention_path",
                         "visual_evidence", "evidence_material", "visual_metaphor",
                         "composition", "shot_language", "temporal_behavior",
                         "relation_to_previous", "relation_to_next", "graphic_layer", "motion",
                         "audio_relationship", "director_note"]}}
    },
    "required": ["shot_id", "beats"]
}


def _server_running() -> bool:
    try:
        r = requests.get(f"{BASE}/health", timeout=3)
        return r.status_code == 200
    except Exception:  # noqa: BLE001
        return False


def ensure_server(ctx: int = 16384, port: int = 8081) -> None:
    global BASE
    BASE = f"http://127.0.0.1:{port}"
    if _server_running():
        return
    log = ROOT / "output" / "stage33" / "coral" / "v3" / "llm_raw" / "server.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "w", encoding="utf-8") as fo, \
            open(str(log) + ".err", "w", encoding="utf-8") as fe:
        subprocess.Popen(
            [str(LLAMA_SERVER), "-m", str(MODEL_PATH), "--host", "127.0.0.1",
             "--port", str(port), "--ctx-size", str(ctx), "--jinja"],
            cwd=str(LLAMA_SERVER.parent), stdout=fo, stderr=fe)
    for _ in range(120):
        if _server_running():
            return
        time.sleep(2)
    raise RuntimeError("llama-server 启动超时")


def stop_server() -> None:
    try:
        r = requests.post(f"{BASE}/shutdown", timeout=5)
        r.close()
    except Exception:  # noqa: BLE001
        pass


def _chat(messages: list, schema: dict, name: str, max_tokens: int,
          temperature: float = 0.6, retries: int = 2) -> dict:
    payload = {
        "model": "qwen2.5-3b",
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "response_format": {"type": "json_schema",
                            "json_schema": {"name": name, "schema": schema}},
        "stream": False,
    }
    last = None
    for attempt in range(retries + 1):
        try:
            r = requests.post(f"{BASE}/v1/chat/completions", json=payload, timeout=1200)
            r.raise_for_status()
            obj = r.json()
            content = obj["choices"][0]["message"]["content"]
            usage = obj.get("usage", {})
            parsed = json.loads(content)
            return {"data": parsed, "usage": usage, "raw_text": content}
        except Exception as e:  # noqa: BLE001
            last = f"{type(e).__name__}: {e}"
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"LLM 调用失败（重试后）: {last}")


def _arc_prompt(ctx: dict) -> str:
    lines = ["这是整片 20 镜的口播清单。请给出全片注意力流：每镜的焦点提示、与上一镜的关系，"
             "以及高潮镜与释放镜。", "（关系=视觉焦点如何从上一镜交接/对比/递进到本镜；"
             "无关系就写 none 并说明。）"]
    for s in ctx["shots"]:
        n = len(s["whitelisted_candidates"])
        lines.append(f"- {s['shot_id']}（{s['shot_role']}）{s['narration']}｜SAFE素材 {n} 个")
    return "\n".join(lines)


def _shot_prompt(ctx: dict, arc_summary: dict, prev_summary: str, sid: str) -> str:
    s = next(x for x in ctx["shots"] if x["shot_id"] == sid)
    cands = "\n".join(
        f"  {c['material_id']}｜{c['content_type']}｜sem={c['semantic_match']:.0f}｜"
        f"{c['visual_description']}" for c in s["whitelisted_candidates"]) or "  （无 SAFE 素材）"
    prev = prev_summary or "（无，本镜为第一镜）"
    return (f"【本镜】{sid}（角色 {s['shot_role']}）口播：「{s['narration']}」\n"
            f"【白名单素材】\n{cands}\n"
            f"【全片注意力流】{json.dumps(arc_summary, ensure_ascii=False)}\n"
            f"【上一镜决策摘要】{prev}\n"
            f"请把本镜口播拆成 1~3 个视觉 beat，逐 beat 输出完整 Visual Statement。"
            f"beat_text 必须逐字复制口播原文片段（含标点），拼接严格等于原句。"
            f"attention_target 必须是口播原文中的词/数字。graphic_layer.text ≤12 字且来自原文。"
            f"禁止使用模板名；motion.necessity 必须写清删掉运动观众损失什么。")


def run_director(ctx: dict, out_dir: Path) -> dict:
    ensure_server()
    raw_dir = out_dir / "llm_raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    stats = {"arc": {}, "shots": [], "total": {}}

    t0 = time.time()
    arc_res = _chat([{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": _arc_prompt(ctx)}],
                    ARC_SCHEMA, "attention_flow", 1400, temperature=0.5)
    arc = arc_res["data"]
    (raw_dir / "llm_raw_arc.json").write_text(
        json.dumps(arc_res["raw_text"], ensure_ascii=False, indent=2), encoding="utf-8")
    stats["arc"] = {"prompt_tokens": arc_res["usage"].get("prompt_tokens"),
                    "completion_tokens": arc_res["usage"].get("completion_tokens"),
                    "elapsed_s": round(time.time() - t0, 1)}

    arc_summary = {"flow": arc.get("flow", []), "climax_shot": arc.get("climax_shot"),
                   "release_shots": arc.get("release_shots", []),
                   "pacing_note": arc.get("pacing_note", "")}
    shot_results, prev_summary = {}, ""
    for s in ctx["shots"]:
        sid = s["shot_id"]
        t1 = time.time()
        res = _chat([{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": _shot_prompt(ctx, arc_summary,
                                                              prev_summary, sid)}],
                    SHOT_SCHEMA, f"shot_{sid}", 2400, temperature=0.6)
        shot_results[sid] = res["data"]
        (raw_dir / f"llm_raw_{sid}.json").write_text(
            json.dumps(res["raw_text"], ensure_ascii=False, indent=2), encoding="utf-8")
        b = res["data"].get("beats", [])
        prev_summary = "；".join(
            f"{x.get('beat_text','')[:14]}|焦点={x.get('attention_target','')[:10]}"
            f"|关系={x.get('relation_to_next',{}).get('type')}" for x in b[:3])
        stats["shots"].append({"shot_id": sid,
                               "prompt_tokens": res["usage"].get("prompt_tokens"),
                               "completion_tokens": res["usage"].get("completion_tokens"),
                               "elapsed_s": round(time.time() - t1, 1)})
    stats["total"] = {"elapsed_s": round(time.time() - t0, 1),
                      "prompt_tokens": sum(x["prompt_tokens"] or 0 for x in stats["shots"]),
                      "completion_tokens": sum(x["completion_tokens"] or 0
                                               for x in stats["shots"])}
    return {"arc": arc, "shots": shot_results, "stats": stats}
