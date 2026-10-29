"""5.x Phase 5-A：多模态语义验证器（真实视觉模型 CLIP，**只读、默认关闭、fail-closed**）。

**它做什么**：对「旁白/镜头语义 ↔ 实际画面」做**只读**交叉验证 —— 从成片里按镜头窗口抽帧，
用**本地 CLIP 权重**（`models/clip/.../clip-vit-base-patch32`，离线 CPU）算"这一帧更像哪个语义域"，
再看**旁白推导出的期望域**是否就是画面最像的域，输出 `MATCH / MISMATCH / UNKNOWN`。

**它不做什么**（授权约束）：
  · 不改选材/时间轴/旁白/BGM，不触发 redo，不写库、不写生产产物、不写 decisions/changelog；
  · **不覆盖、不删除 4-B 的结果**：4-B（`core/semantics.py`，类别式规则）仍是既有证据层，
    本模块只是**新增一层**像素级证据，两者并列保存、各自独立判定；
  · 默认关闭（`tools.multimodal.enabled=false`）：必须显式开启或显式调用只读命令才会用到模型。

**fail-closed**：模型目录缺失 / venv 缺失 / 子进程失败 / 超时 / JSON 解析失败 / 无帧 / 无旁白 /
期望域推导不出 / 相似度过低或过于接近 —— 一律 `UNKNOWN` 并给出明确错误码，**绝不编造 MATCH/MISMATCH**。

**确定性**：CLIP CPU 单线程 + 固定权重 + 固定抽帧时间点 + 相似度 6 位小数四舍五入；
同一输入两次运行结果逐字节一致（由 `tests/multimodal_test.py` 与证据脚本断言）。
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from .semantics import load_lexicon

SCHEMA = "multimodal-verifier-v1"

# 每个语义域 → 英文提示词（CLIP 文本塔只支持英文）。
# 提示词来源：4-B 词表（`core/lexicons/semantics_v1.json`）的该域语义 + 人工书写的自然句式，
# **可逐条核对**；**不含任何被测素材的名称/来源信息**（避免与 4-B 的词面匹配形成循环论证）。
DOMAIN_PROMPTS = {
    "xr_device": ["a person wearing a virtual reality headset",
                  "a virtual reality headset device",
                  "VR goggles and controllers"],
    "computing_device": ["a computer or laptop on a desk",
                         "a circuit board or computer chip",
                         "a computer keyboard and monitor"],
    "wildlife": ["a wild animal in nature", "a shark swimming in the sea",
                 "a whale or dolphin in the ocean"],
    "geography_nature": ["a mountain landscape", "an island in the ocean",
                         "a forest and a lake"],
    "architecture": ["a building or church", "a tower or a bridge", "a castle"],
    "people": ["a portrait of a person", "a crowd of people", "a worker at work"],
    "food_drink": ["a plate of food", "a cup of coffee", "bread and fruit on a table"],
    "art_culture": ["a painting or sculpture in a museum", "an art exhibition",
                    "a musical instrument"],
    "sports": ["people playing football", "an athlete running", "a basketball game"],
    "vehicle": ["a car on a road", "a train on rails", "an airplane in the sky"],
    "space_astronomy": ["a galaxy seen through a telescope", "the moon or a planet",
                        "a rocket launching into space"],
    "document_text": ["a document or a screenshot", "a chart or a diagram", "a map"],
}

MM_DEFAULTS = {
    "enabled": False,                     # **默认关闭**
    "backend": "clip_local",
    "model_dir": ("models/clip/models--openai--clip-vit-base-patch32/snapshots/"
                  "3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268"),
    "python": ".venv_tts/Scripts/python.exe",
    "timeout_s": 420,
    "frames_per_scene": 3,                # 每个镜头抽帧数（按窗口 25%/50%/75% 取样）
    "min_sim": 0.20,                      # 期望域相似度下限（低于此认为信号不足）
    "margin": 0.02,                       # 与最强"其它域"的最小差距
    "top_k": 3,                           # 证据里保留的 top-k 域
}

MM_ERRORS = ("MM_DISABLED", "MM_MODEL_MISSING", "MM_PYTHON_MISSING", "MM_BACKEND_MISSING",
             "MM_WORKER_FAILED", "MM_TIMEOUT", "MM_PARSE_FAILED", "MM_EMPTY_JOB",
             "MM_NO_FRAMES", "MM_NO_NARRATION", "MM_UNKNOWN_DOMAIN", "MM_LOW_SIGNAL",
             "MM_AMBIGUOUS")

VERDICTS = ("MATCH", "MISMATCH", "UNKNOWN")


def mm_settings(config: dict | None = None) -> dict:
    """读 `tools.multimodal`；缺省 = **关闭**。非法值回退默认（不放松阈值）。"""
    raw = ((config or {}).get("tools") or {}).get("multimodal") or {}
    s = dict(MM_DEFAULTS)
    notes = []
    for k, v in raw.items():
        if k not in MM_DEFAULTS:
            continue
        if k in ("min_sim", "margin"):
            try:
                s[k] = float(v)
            except (TypeError, ValueError):
                notes.append("参数 {}={!r} 非法，保留默认 {}".format(k, v, s[k]))
        elif k in ("timeout_s", "frames_per_scene", "top_k"):
            try:
                s[k] = int(v)
            except (TypeError, ValueError):
                notes.append("参数 {}={!r} 非法，保留默认 {}".format(k, v, s[k]))
        elif k == "enabled":
            s[k] = bool(v)
        else:
            s[k] = v
    if s["frames_per_scene"] < 1:
        s["frames_per_scene"] = MM_DEFAULTS["frames_per_scene"]
    s["_notes"] = notes
    s["_source"] = "tools.multimodal" if raw else "default(disabled)"
    return s


# ---------------- 期望域（由旁白推导，机械规则；不接入 LLM） ----------------
def _surface_forms(lex: dict) -> dict:
    """从 4-B 词表取出 {domain: {"zh": [...], "latin": [...]}}。"""
    out = {}
    for dom, forms in (lex.get("domains") or {}).items():
        out[dom] = {"zh": [str(x) for x in (forms.get("zh") or []) if x],
                    "latin": [str(x) for x in (forms.get("latin") or []) if x]}
    return out


def _retrieval_forms() -> dict:
    """4-E 检索词典（`retrieval_synonyms_v1.json`）作为**次要**期望来源（仅当 4-B 词表无命中时使用）。

    只做同样的词面命中；域标签与 4-B 对齐（12 域）。用途与来源均在报告里如实记录
    （`expected_domain_source`），**不修改 4-B 词表、不覆盖 4-B 结论**。
    """
    from .retrieval_quality import load_retrieval_lexicon
    lex = load_retrieval_lexicon()
    out: dict[str, dict] = {}
    for c in lex.get("concepts") or []:
        dom = str(c.get("domain") or c.get("id"))
        rec = out.setdefault(dom, {"zh": [], "latin": []})
        rec["zh"] += [str(x) for x in (c.get("zh") or []) if x]
        rec["latin"] += [str(x) for x in (c.get("latin") or []) if x]
    return out


def _vote(text: str, forms_by_domain: dict) -> dict:
    raw = str(text or "")
    low = raw.lower()
    votes: dict[str, list] = {}
    for dom, forms in forms_by_domain.items():
        hits = []
        for form in forms.get("zh") or []:
            if form and form in raw:
                hits.append(form)
        for form in forms.get("latin") or []:
            f = str(form).lower().strip()
            if len(f) < 2:
                continue
            if re.search(r"(?<![a-z0-9]){}(?![a-z0-9])".format(re.escape(f)), low):
                hits.append(form)
        if hits:
            votes[dom] = sorted(set(hits))
    return votes


def expected_domain_from_narration(text: str, lex: dict | None = None) -> dict:
    """从旁白文本机械推导**期望语义域**（词面命中计数，不做语义推理、不接入 LLM）。

    两级来源（都可逐条核对，报告里记录实际用的是哪一级）：
      1. **4-B 词表**（`core/lexicons/semantics_v1.json`）——语义域的权威来源；
      2. 仅当 1 无命中时，回退到 **4-E 检索词典**（`retrieval_synonyms_v1.json`）的同域表面形式。

    拉丁形式**必须按词边界命中**（`car` 不得命中 `Cardboard`；实测该缺陷曾在 S06 旁白上触发，已修正）；
    中文形式按子串命中（中文无词边界）。两级都无命中 → `domain=None`
    （调用方记 `UNKNOWN / MM_UNKNOWN_DOMAIN`，**不猜**）。
    """
    lx = lex or load_lexicon()
    votes = _vote(text, _surface_forms(lx))
    method = "lexicon_4b_surface_vote_v1"
    if not votes:
        try:
            votes = _vote(text, _retrieval_forms())
            method = "lexicon_4e_retrieval_fallback_v1"
        except Exception:                                     # noqa: BLE001
            votes = {}
    if not votes:
        return {"domain": None, "method": "lexicon_surface_vote_v1_chain", "matched": {},
                "votes": {}}
    # 机械裁决：命中词数多者胜；并列则按域名字典序（确定性，不做语义偏好）
    best = sorted(votes.items(), key=lambda kv: (-len(kv[1]), kv[0]))[0]
    return {"domain": best[0], "method": method,
            "matched": {k: v for k, v in sorted(votes.items())}, "votes": votes}


# ---------------- 抽帧计划（纯函数） ----------------
def frame_plan(scenes: list, frames_per_scene: int = 3) -> list:
    """按镜头窗口均匀取时间点（**纯函数**，便于复算）。

    返回 [{"scene_id", "start_s", "end_s", "duration_s", "times": [...]}]；
    窗口缺失/非正 → 该镜头 times 为空（调用方记 UNKNOWN，不做猜测）。
    """
    out = []
    n = max(1, int(frames_per_scene))
    for sc in scenes or []:
        try:
            a, b = float(sc.get("start_s")), float(sc.get("end_s"))
        except (TypeError, ValueError):
            a = b = None
        times: list[float] = []
        if a is not None and b is not None and b > a:
            for i in range(n):
                frac = (i + 1) / (n + 1)
                times.append(round(a + (b - a) * frac, 3))
        out.append({"scene_id": sc.get("scene_id"), "start_s": a, "end_s": b,
                    "duration_s": (round(b - a, 3) if times else None), "times": times,
                    "segment_index": sc.get("segment_index")})
    return out


# ---------------- 判定规则（纯函数） ----------------
def verdict_for_scene(scores: dict, expected_domain: str | None, settings: dict) -> dict:
    """纯函数判定：输入 = {domain: 相似度}（已按帧平均），输出 = 三态 + 依据。

    规则（显式、可复算）：
      · 期望域未知 → `UNKNOWN / MM_UNKNOWN_DOMAIN`
      · `expected_sim >= min_sim` 且 `expected_sim - best_other >= margin` → **MATCH**
      · `best_other >= min_sim` 且 `best_other - expected_sim >= margin`  → **MISMATCH**
      · 其余：`expected_sim < min_sim` → `UNKNOWN / MM_LOW_SIGNAL`；否则 `UNKNOWN / MM_AMBIGUOUS`
    """
    s = {**MM_DEFAULTS, **(settings or {})}
    min_sim, margin = float(s["min_sim"]), float(s["margin"])
    ranked = sorted((scores or {}).items(), key=lambda kv: (-kv[1], kv[0]))
    base = {"expected_domain": expected_domain, "min_sim": min_sim, "margin": margin,
            "ranked_domains": [{"domain": d, "sim": round(float(v), 6)} for d, v in ranked],
            "top_k": [{"domain": d, "sim": round(float(v), 6)}
                      for d, v in ranked[:max(1, int(s["top_k"]))]]}
    if not scores:
        return {**base, "verdict": "UNKNOWN", "code": "MM_LOW_SIGNAL",
                "reason": "没有可用的相似度（帧或标签缺失）"}
    if not expected_domain or expected_domain not in scores:
        return {**base, "verdict": "UNKNOWN", "code": "MM_UNKNOWN_DOMAIN",
                "reason": "旁白推导不出期望语义域（词表未命中），不做判定"}
    exp = float(scores[expected_domain])
    others = [(d, float(v)) for d, v in scores.items() if d != expected_domain]
    best_other = max(others, key=lambda kv: kv[1]) if others else (None, 0.0)
    base.update({"expected_sim": round(exp, 6), "best_other_domain": best_other[0],
                 "best_other_sim": round(best_other[1], 6),
                 "delta": round(exp - best_other[1], 6)})
    if exp >= min_sim and (exp - best_other[1]) >= margin:
        return {**base, "verdict": "MATCH", "code": None,
                "reason": "画面最像的语义域与旁白期望域一致（Δ={:.4f} ≥ {:.4f}）".format(
                    exp - best_other[1], margin)}
    if best_other[0] and best_other[1] >= min_sim and (best_other[1] - exp) >= margin:
        return {**base, "verdict": "MISMATCH", "code": None,
                "reason": "画面更像『{}』而不是旁白期望的『{}』（Δ={:.4f} ≥ {:.4f}）".format(
                    best_other[0], expected_domain, best_other[1] - exp, margin)}
    if exp < min_sim:
        return {**base, "verdict": "UNKNOWN", "code": "MM_LOW_SIGNAL",
                "reason": "期望域相似度 {:.4f} < 下限 {:.4f}（信号不足，不判定）".format(exp, min_sim)}
    return {**base, "verdict": "UNKNOWN", "code": "MM_AMBIGUOUS",
            "reason": "期望域与最强其它域差距 {:.4f} < 阈值 {:.4f}（歧义，不判定）".format(
                abs(exp - best_other[1]), margin)}


# ---------------- worker 调用（fail-closed） ----------------
def _sha256(p: Path) -> str | None:
    try:
        h = hashlib.sha256()
        with p.open("rb") as fh:
            for c in iter(lambda: fh.read(1 << 20), b""):
                h.update(c)
        return h.hexdigest()
    except OSError:
        return None


def run_worker(images: list, labels: list, settings: dict, *, root: Path,
               workdir: Path | None = None) -> dict:
    """调用 CLIP worker（子进程）。**任何失败都返回 ok=False + code**，绝不抛异常、绝不编造结果。"""
    s = {**MM_DEFAULTS, **(settings or {})}
    model_dir = Path(str(s["model_dir"]))
    if not model_dir.is_absolute():
        model_dir = Path(root) / model_dir
    worker = Path(root) / "src" / "video_studio" / "core" / "mm_worker_clip.py"
    py = Path(str(s["python"]))
    if not py.is_absolute():
        py = Path(root) / py
    out = {"ok": False, "code": None, "detail": None, "similarities": {}, "model": {},
           "versions": {}, "image_sha256": {}}
    if not model_dir.is_dir():
        out.update(code="MM_MODEL_MISSING", detail="模型目录不存在: {}".format(model_dir))
        return out
    if not py.is_file():
        out.update(code="MM_PYTHON_MISSING", detail="worker 解释器不存在: {}".format(py))
        return out
    if not worker.is_file():
        out.update(code="MM_WORKER_FAILED", detail="worker 脚本不存在: {}".format(worker))
        return out
    tmp = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="vs_mm_"))
    tmp.mkdir(parents=True, exist_ok=True)
    job_p, res_p = tmp / "job.json", tmp / "result.json"
    job = {"model_dir": str(model_dir), "images": images, "labels": labels}
    job_p.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
    try:
        r = subprocess.run([str(py), str(worker), "--job", str(job_p), "--out", str(res_p)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=float(s["timeout_s"]))
    except subprocess.TimeoutExpired:
        out.update(code="MM_TIMEOUT", detail="worker 超时 {:.0f}s".format(float(s["timeout_s"])))
        return out
    except OSError as exc:
        out.update(code="MM_WORKER_FAILED", detail="{}: {}".format(type(exc).__name__,
                                                                   str(exc)[:160]))
        return out
    if not res_p.is_file():
        out.update(code="MM_WORKER_FAILED",
                   detail="worker 未产出结果（rc={}；stderr 尾部 {}）".format(
                       r.returncode, (r.stderr or "")[-200:]))
        return out
    try:
        data = json.loads(res_p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        out.update(code="MM_PARSE_FAILED", detail="worker 结果不是合法 JSON")
        return out
    data.setdefault("detail", None)
    data["stderr_tail"] = (r.stderr or "")[-200:]
    return data


# ---------------- 端到端（只读输入 → 三态报告） ----------------
def validate(frames: list, labels: list, *, root: Path, settings: dict,
             workdir: Path | None = None, narration_by_scene: dict | None = None,
             film: str | None = None, sources: dict | None = None) -> dict:
    """对一批已抽好的帧做多模态判定，返回完整报告（含模型/输入指纹/逐域证据）。

    frames: [{"id","path","scene_id","time_s","sha256"}]；labels: [{"id","text","domain"}]
    """
    s = {**MM_DEFAULTS, **(settings or {})}
    rep = {"schema": SCHEMA, "enabled": bool(s.get("enabled")), "applied": False,
           "model": {}, "versions": {}, "settings": {k: v for k, v in s.items()
                                                     if not k.startswith("_")},
           "settings_source": s.get("_source"), "settings_notes": s.get("_notes") or [],
           "film": film, "sources": sources or {}, "scenes": [], "counts": {},
           "policy": {"mode": "readonly_advisory", "auto_apply": False, "auto_redo": False,
                      "writes_to_db": False, "writes_to_production": False,
                      "changes_selection": False, "changes_timeline": False,
                      "overwrites_4b_results": False, "requires_human_decision": True,
                      "note": ("多模态验证是**新增证据层**：4-B 结果原样保留、不覆盖不删除；"
                               "本报告不改选材/时间轴/旁白/BGM，不写库、不写生产产物、不触发 redo")},
           "note": "只读验证：MATCH/MISMATCH/UNKNOWN 仅供参考，任何改动都需人工决定 + 审批 + redo"}
    if not frames:
        rep["counts"] = {"MATCH": 0, "MISMATCH": 0, "UNKNOWN": len(narration_by_scene or {})}
        rep["error"] = {"code": "MM_NO_FRAMES", "detail": "没有可用的抽帧"}
        rep["scenes"] = [{"scene_id": sid, "verdict": "UNKNOWN", "code": "MM_NO_FRAMES",
                          "reason": "抽帧失败或成片缺失 → fail-closed（不伪造判定）",
                          "frames": []}
                         for sid in sorted(narration_by_scene or {})] or \
                        [{"scene_id": None, "verdict": "UNKNOWN", "code": "MM_NO_FRAMES",
                          "reason": "没有可用的抽帧", "frames": []}]
        return rep
    if not labels:
        rep["counts"] = {"MATCH": 0, "MISMATCH": 0, "UNKNOWN": 0}
        rep["error"] = {"code": "MM_LOW_SIGNAL", "detail": "没有可用的提示词标签"}
        return rep
    res = run_worker([{"id": f["id"], "path": f["path"]} for f in frames],
                     [{"id": lb["id"], "text": lb["text"]} for lb in labels],
                     s, root=root, workdir=workdir)
    rep["model"] = res.get("model") or {}
    rep["versions"] = res.get("versions") or {}
    if not res.get("ok"):
        rep["error"] = {"code": res.get("code") or "MM_WORKER_FAILED",
                        "detail": res.get("detail")}
        rep["counts"] = {"MATCH": 0, "MISMATCH": 0, "UNKNOWN": len({f["scene_id"] for f in frames})}
        by_scene: dict = {}
        for f in frames:
            by_scene.setdefault(f["scene_id"], []).append(f)
        for sid, fs in by_scene.items():
            rep["scenes"].append({
                "scene_id": sid, "verdict": "UNKNOWN", "code": res.get("code"),
                "reason": "模型不可用 → fail-closed（不伪造判定）",
                "frames": [{"id": f["id"], "time_s": f.get("time_s"), "sha256": f.get("sha256")}
                           for f in fs]})
        return rep
    sims = res.get("similarities") or {}
    label_domain = {lb["id"]: lb.get("domain") or lb["id"] for lb in labels}
    by_scene = {}
    for f in frames:
        by_scene.setdefault(f["scene_id"], []).append(f)
    counts = {"MATCH": 0, "MISMATCH": 0, "UNKNOWN": 0}
    for sid, fs in sorted(by_scene.items(), key=lambda kv: str(kv[0])):
        per_domain: dict[str, list] = {}
        for f in fs:
            for lid, v in (sims.get(f["id"]) or {}).items():
                per_domain.setdefault(label_domain.get(lid, lid), []).append(float(v))
        scores = {d: round(sum(v) / len(v), 6) for d, v in per_domain.items() if v}
        narr = (narration_by_scene or {}).get(sid) or {}
        exp = expected_domain_from_narration(narr.get("text") or "")
        v = verdict_for_scene(scores, exp.get("domain"), s)
        counts[v["verdict"]] = counts.get(v["verdict"], 0) + 1
        rep["scenes"].append({
            "scene_id": sid, "verdict": v["verdict"], "code": v.get("code"),
            "reason": v["reason"], "confidence": ("HIGH" if v["verdict"] == "MATCH"
                                                  and v.get("delta", 0) >= 2 * float(s["margin"])
                                                  else ("HIGH" if v["verdict"] == "MISMATCH"
                                                        and v.get("delta", 0) <= -2 * float(s["margin"])
                                                        else "MEDIUM")),
            "expected_domain": v["expected_domain"],
            "expected_domain_source": exp.get("method"),
            "narration_text": (narr.get("text") or "")[:200],
            "narration_sha256": (hashlib.sha256((narr.get("text") or "").encode("utf-8"))
                                 .hexdigest() if narr.get("text") else None),
            "narration_matched_forms": exp.get("matched") or {},
            "domain_scores": v["ranked_domains"], "top_k": v["top_k"],
            "expected_sim": v.get("expected_sim"), "best_other_domain": v.get("best_other_domain"),
            "best_other_sim": v.get("best_other_sim"), "delta": v.get("delta"),
            "frames": [{"id": f["id"], "time_s": f.get("time_s"), "sha256": f.get("sha256"),
                        "path": f.get("path")} for f in sorted(fs, key=lambda x: x.get("time_s") or 0)],
        })
    rep["counts"] = counts
    rep["applied"] = True
    return rep
