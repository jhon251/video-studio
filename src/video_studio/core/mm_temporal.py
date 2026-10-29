"""5.x Phase 5-D：多帧/时序多模态证据增强（**只读、默认关闭、fail-closed、平行证据层**）。

**它解决什么**：5-A 每个镜头只抽 **3 帧**（25/50/75%）后按帧平均打分，单帧噪声/视角差异会直接
影响 `MATCH/UNKNOWN` 的稳定性（5-C 实测：S06 换用侧面产品图后 `MATCH → UNKNOWN/MM_AMBIGUOUS`）。
本层**加密采样**（默认 **7 帧**）并对同一镜头做**时序一致性**分析，回答两个问题：
  1. 这个镜头在时间轴上是不是**同一个视觉状态**（静态镜头 / 镜头内是否发生了视觉切换）；
  2. 逐帧的语义域证据是否**一致**（投票分布 + 边际分布），从而让 `MATCH/MISMATCH/UNKNOWN`
     不再由单帧噪声决定。

**它不做什么**（授权约束，逐条对应）：
  · 不自动换材、不自动选材、不自动 redo、不改时间轴/旁白/BGM；
  · 不写库、不写生产产物、不写 `decisions`/`changelog`；不调用任何写入口；
  · **不改 5-A 原始结果**：5-A 的判定逻辑（`core/multimodal.py`）**一字未动**，本层只读取同一模型、
    重新抽更多帧，产出**平行证据**（报告里以 `five_a_reference` 原样引用 5-A 的判定，便于并列核对）；
  · **不改 4-B**：4-B 文本语义仍是独立证据层，本层只把它作为"期望域"的推导来源（与 5-A 同一链路）；
  · 默认关闭（`tools.multimodal_temporal.enabled=false`），必须显式调用只读命令才会用到模型。

**fail-closed**：模型/解释器缺失、worker 失败/超时/解析失败、无帧、帧数不足（< `min_frames`）、
期望域推导不出、镜头内出现视觉切换（split）、一致性不足、信号过低、投票不一致 —— 一律 `UNKNOWN`
+ 明确错误码，**绝不编造 MATCH/MISMATCH**。

**确定性**：CLIP CPU 单线程 + 固定权重 + 固定抽帧时间点 + 6 位小数四舍五入 + 域名字典序；
同一输入两次运行结果逐字节一致（由 `tests/mm_temporal_test.py` 断言）。
"""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
import tempfile
from pathlib import Path

from .multimodal import (MM_DEFAULTS, expected_domain_from_narration,  # noqa: F401
                         frame_plan)

SCHEMA = "multimodal-temporal-v1"

MMT_DEFAULTS = {
    "enabled": False,                     # **默认关闭**
    "backend": "clip_local",
    "model_dir": MM_DEFAULTS["model_dir"],          # 与 5-A 同一份本地权重（sha256 钉定）
    "python": MM_DEFAULTS["python"],               # 与 5-A 同一个 worker 解释器
    "timeout_s": 900,                     # 帧数更多 → 超时预算更大（仅等待，不放松判定）
    "frames_per_scene": 7,                # 每镜头帧数（窗口内均匀取样；5-A 用 3）
    "min_frames": 3,                      # 少于该帧数不做时序判定（INSUFFICIENT_FRAMES）
    "min_sim": 0.20,                      # 与 5-A **同值**（对齐口径，不放松）
    "margin": 0.02,                       # 与 5-A **同值**（对齐口径，不放松）
    "min_vote_frac": 0.60,                # 期望域"逐帧 argmax 投票"占比下限
    "min_stability_cos": 0.75,            # 帧间视觉一致性下限（低于此不判定 → LOW_CONSISTENCY）
    "split_cos": 0.50,                    # 帧间一致性更低 → 判定为镜头内视觉切换（TEMPORAL_SPLIT）
    "high_stability_cos": 0.90,           # 达到该一致性且边际充足 → 置信度 HIGH
    "top_k": 3,
}

MMT_ERRORS = ("MMT_DISABLED", "MM_MODEL_MISSING", "MM_PYTHON_MISSING", "MM_WORKER_FAILED",
              "MM_TIMEOUT", "MM_PARSE_FAILED", "MM_EMPTY_JOB", "MMT_NO_FRAMES",
              "MMT_UNKNOWN_DOMAIN", "MMT_INSUFFICIENT_FRAMES", "MMT_TEMPORAL_SPLIT",
              "MMT_LOW_CONSISTENCY", "MMT_INCONSISTENT", "MMT_LOW_SIGNAL", "MMT_AMBIGUOUS")

# 规则 ID（报告里逐镜头记录实际命中的规则，便于复核与回归）
TEMPORAL_RULES = (
    "T0_FAIL_CLOSED",        # 模型/帧/期望域等前置条件不成立
    "T1_TEMPORAL_SPLIT",     # 镜头内视觉状态发生变化（帧间一致性 < split_cos）
    "T2_LOW_CONSISTENCY",    # 帧间一致性不足（< min_stability_cos）但不构成 split
    "T3_CONSISTENT_MATCH",   # 多帧一致支持期望域
    "T4_CONSISTENT_MISMATCH",  # 多帧一致支持另一个域
    "T5_INCONSISTENT",       # 逐帧投票分散（帧间语义互相矛盾）
    "T6_LOW_SIGNAL",         # 期望域相似度中位数低于下限
    "T7_AMBIGUOUS",          # 期望域与最强其它域差距中位数不足
)

VERDICTS = ("MATCH", "MISMATCH", "UNKNOWN")


# ---------------- 配置 ----------------
def mmt_settings(config: dict | None = None) -> dict:
    """读 `tools.multimodal_temporal`；缺省 = **关闭**。非法值回退默认（不放松任何阈值）。"""
    raw = ((config or {}).get("tools") or {}).get("multimodal_temporal") or {}
    s = dict(MMT_DEFAULTS)
    notes = []
    for k, v in raw.items():
        if k not in MMT_DEFAULTS:
            continue
        if k in ("min_sim", "margin", "min_vote_frac", "min_stability_cos", "split_cos",
                 "high_stability_cos"):
            try:
                s[k] = float(v)
            except (TypeError, ValueError):
                notes.append("参数 {}={!r} 非法，保留默认 {}".format(k, v, s[k]))
        elif k in ("timeout_s", "frames_per_scene", "min_frames", "top_k"):
            try:
                s[k] = int(v)
            except (TypeError, ValueError):
                notes.append("参数 {}={!r} 非法，保留默认 {}".format(k, v, s[k]))
        elif k == "enabled":
            s[k] = bool(v)
        else:
            s[k] = v
    if s["frames_per_scene"] < 1:
        s["frames_per_scene"] = MMT_DEFAULTS["frames_per_scene"]
    if s["min_frames"] < 1:
        s["min_frames"] = MMT_DEFAULTS["min_frames"]
    if s["min_frames"] > s["frames_per_scene"]:
        notes.append("min_frames={} > frames_per_scene={}，min_frames 回退默认 {}".format(
            s["min_frames"], s["frames_per_scene"], MMT_DEFAULTS["min_frames"]))
        s["min_frames"] = MMT_DEFAULTS["min_frames"]
    s["_notes"] = notes
    s["_source"] = "tools.multimodal_temporal" if raw else "default(disabled)"
    return s


def labels_from_prompts(prompts: dict | None = None) -> list:
    """域 → 英文提示词展开（与 5-A 同一提示词表；确定性顺序）。"""
    from .multimodal import DOMAIN_PROMPTS
    src = prompts or DOMAIN_PROMPTS
    out = []
    for dom in sorted(src):
        for i, text in enumerate(src[dom]):
            out.append({"id": "{}#{}".format(dom, i), "text": text, "domain": dom})
    return out


# ---------------- 时序度量（纯函数） ----------------
def cosine(a: list, b: list) -> float:
    """余弦相似度（**纯函数**；长度不等/零向量 → 0.0，绝不抛异常）。"""
    try:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(float(x) * float(y) for x, y in zip(a, b))
        na = math.sqrt(sum(float(x) * float(x) for x in a))
        nb = math.sqrt(sum(float(y) * float(y) for y in b))
        if na <= 0 or nb <= 0:
            return 0.0
        return dot / (na * nb)
    except (TypeError, ValueError):
        return 0.0


def temporal_metrics(frame_records: list, expected_domain: str | None) -> dict:
    """把一个镜头的**有序逐帧证据**聚合成时序指标（纯函数，可复算）。

    frame_records: [{"id","time_s","scores":{domain:sim},"embedding":[...]}]（按时间升序）
    返回：期望相似度分布、边际分布、逐帧 argmax 投票、帧间视觉一致性、聚合后的域分数。
    """
    fr = [f for f in (frame_records or []) if isinstance(f, dict)]
    n = len(fr)
    out: dict = {"frames_used": n, "expected_domain": expected_domain,
                 "per_frame": [], "adjacent_cos": [], "vote_expected": None,
                 "argmax_votes": {}, "visual_stability_mean": None,
                 "visual_stability_min": None, "dispersion": None,
                 "expected_sim_median": None, "expected_sim_min": None,
                 "expected_sim_mean": None, "margin_median": None, "margin_min": None,
                 "domains_aggregated": {}, "temporal_split": None, "stability_class": None}
    if n == 0:
        return out
    per, votes = [], {}
    sims, margins = [], []
    for f in fr:
        sc = {str(k): float(v) for k, v in (f.get("scores") or {}).items()}
        ranked = sorted(sc.items(), key=lambda kv: (-kv[1], kv[0]))
        argmax = ranked[0][0] if ranked else None
        exp_sim = sc.get(str(expected_domain)) if expected_domain else None
        other = max((v for d, v in sc.items() if d != str(expected_domain)), default=0.0)
        margin = (exp_sim - other) if exp_sim is not None else None
        sims.append(exp_sim)
        if margin is not None:
            margins.append(margin)
        if argmax:
            votes[argmax] = votes.get(argmax, 0) + 1
        per.append({"id": f.get("id"), "time_s": f.get("time_s"),
                    "expected_sim": (round(exp_sim, 6) if exp_sim is not None else None),
                    "argmax_domain": argmax,
                    "argmax_sim": (round(ranked[0][1], 6) if ranked else None),
                    "margin": (round(margin, 6) if margin is not None else None),
                    "top_k": [{"domain": d, "sim": round(v, 6)} for d, v in ranked[:3]],
                    "sha256": f.get("sha256")})
    adj = []
    for a, b in zip(fr, fr[1:]):
        adj.append(round(cosine(a.get("embedding") or [], b.get("embedding") or []), 6))
    # 逐域聚合（帧间平均；与 5-A 同口径，便于并列比较）
    per_domain: dict[str, list] = {}
    for f in fr:
        for d, v in (f.get("scores") or {}).items():
            per_domain.setdefault(str(d), []).append(float(v))
    agg = {d: round(sum(v) / len(v), 6) for d, v in sorted(per_domain.items()) if v}
    def median(xs):
        ys = sorted(v for v in xs if v is not None)
        if not ys:
            return None
        m = len(ys) // 2
        return round((ys[m] if len(ys) % 2 else (ys[m - 1] + ys[m]) / 2.0), 6)
    stab_mean = round(sum(adj) / len(adj), 6) if adj else None
    stab_min = round(min(adj), 6) if adj else None
    valid_sims = [v for v in sims if v is not None]
    # 散布：两两余弦的 1 - 均值（帧数大时抽样以保持确定性成本）
    embs = [f.get("embedding") or [] for f in fr]
    pairs = []
    for i in range(len(embs)):
        for j in range(i + 1, len(embs)):
            if embs[i] and embs[j]:
                pairs.append(cosine(embs[i], embs[j]))
    out.update({
        "per_frame": per, "adjacent_cos": adj, "argmax_votes": {k: votes[k]
                                                                for k in sorted(votes)},
        "vote_expected": (round(votes.get(str(expected_domain), 0) / n, 6)
                          if expected_domain else None),
        "visual_stability_mean": stab_mean, "visual_stability_min": stab_min,
        "dispersion": (round(1.0 - sum(pairs) / len(pairs), 6) if pairs else None),
        "expected_sim_median": median(sims),
        "expected_sim_min": (round(min(valid_sims), 6) if valid_sims else None),
        "expected_sim_mean": (round(sum(valid_sims) / len(valid_sims), 6) if valid_sims else None),
        "margin_median": median(margins), "margin_min": (round(min(margins), 6)
                                                         if margins else None),
        "domains_aggregated": agg})
    return out


def classify_stability(metrics: dict, settings: dict) -> dict:
    """把时序指标映射成类别（纯函数）：STABLE / MODERATE / SPLIT / UNKNOWN。"""
    s = {**MMT_DEFAULTS, **(settings or {})}
    mean = metrics.get("visual_stability_mean")
    mn = metrics.get("visual_stability_min")
    if mean is None or mn is None:
        return {"stability_class": "UNKNOWN", "temporal_split": None,
                "reason": "没有帧间相似度（帧或嵌入缺失）"}
    split_cos = float(s["split_cos"])
    min_cos = float(s["min_stability_cos"])
    if mn < split_cos:
        cls, split = "SPLIT", True
    elif mean < min_cos:
        cls, split = "MODERATE", False
    else:
        cls, split = "STABLE", False
    return {"stability_class": cls, "temporal_split": split,
            "reason": "帧间一致性 mean={} min={}（split<{} / 稳定≥{}）".format(
                mean, mn, split_cos, min_cos)}


def temporal_verdict(metrics: dict, expected_domain: str | None, settings: dict,
                     *, fail_code: str | None = None, fail_detail: str | None = None) -> dict:
    """**纯函数**判定：多帧/时序指标 → 三态 + 规则 ID + 置信度 + 依据。

    规则顺序（显式、可复算；先命中先返回）：
      T0 前置失败（模型/帧/期望域）→ UNKNOWN
      T1 镜头内视觉切换（min 相邻余弦 < split_cos）→ UNKNOWN / MMT_TEMPORAL_SPLIT
      T2 帧间一致性不足（mean < min_stability_cos）→ UNKNOWN / MMT_LOW_CONSISTENCY
      T3 期望域投票占比 ≥ min_vote_frac 且 期望相似度中位数 ≥ min_sim 且 边际中位数 ≥ margin → MATCH
      T4 同一其它域投票占比 ≥ min_vote_frac 且 其相似度中位数 ≥ min_sim 且 −边际中位数 ≥ margin → MISMATCH
      T5 投票分散（无任何域达到 min_vote_frac）→ UNKNOWN / MMT_INCONSISTENT
      T6 期望相似度中位数 < min_sim → UNKNOWN / MMT_LOW_SIGNAL
      T7 其余 → UNKNOWN / MMT_AMBIGUOUS
    置信度：MATCH/MISMATCH → HIGH（一致性 ≥ high_stability_cos **且** |边际中位数| ≥ 2×margin）/ 否则 MEDIUM；
            UNKNOWN → MEDIUM（"稳定地判不出来"：一致性 ≥ high_stability_cos 且未发生 split）/ 否则 LOW。
    """
    s = {**MMT_DEFAULTS, **(settings or {})}
    min_sim, margin = float(s["min_sim"]), float(s["margin"])
    min_vote = float(s["min_vote_frac"])
    high_cos = float(s["high_stability_cos"])
    n = int(metrics.get("frames_used") or 0)
    base = {"expected_domain": expected_domain, "min_sim": min_sim, "margin": margin,
            "min_vote_frac": min_vote, "min_stability_cos": float(s["min_stability_cos"]),
            "split_cos": float(s["split_cos"]), "high_stability_cos": high_cos,
            "frames_used": n, "rule_id": None}
    stab = classify_stability(metrics, s)
    # 把全部时序/聚合指标**先行**放进 base：任何返回路径（含 T1/T2/T0 提前返回）都带完整证据
    base.update({"stability_class": stab["stability_class"],
                 "temporal_split": stab["temporal_split"],
                 "stability_reason": stab["reason"],
                 "expected_sim_median": metrics.get("expected_sim_median"),
                 "expected_sim_min": metrics.get("expected_sim_min"),
                 "expected_sim_mean": metrics.get("expected_sim_mean"),
                 "median_margin": metrics.get("margin_median"),
                 "margin_min": metrics.get("margin_min"),
                 "vote_expected": metrics.get("vote_expected"),
                 "argmax_votes": metrics.get("argmax_votes"),
                 "visual_stability_mean": metrics.get("visual_stability_mean"),
                 "visual_stability_min": metrics.get("visual_stability_min"),
                 "adjacent_cos": metrics.get("adjacent_cos"),
                 "dispersion": metrics.get("dispersion")})
    mean_cos = metrics.get("visual_stability_mean")
    if fail_code:
        return {**base, "verdict": "UNKNOWN", "code": fail_code, "rule_id": "T0_FAIL_CLOSED",
                "confidence": "LOW",
                "reason": "前置条件不成立 → fail-closed（不伪造判定）：{}".format(
                    fail_detail or fail_code)}
    if not expected_domain:
        return {**base, "verdict": "UNKNOWN", "code": "MMT_UNKNOWN_DOMAIN",
                "rule_id": "T0_FAIL_CLOSED", "confidence": "LOW",
                "reason": "旁白推导不出期望语义域（词表未命中），不做判定"}
    if n < int(s["min_frames"]):
        return {**base, "verdict": "UNKNOWN", "code": "MMT_INSUFFICIENT_FRAMES",
                "rule_id": "T0_FAIL_CLOSED", "confidence": "LOW",
                "reason": "可用帧数 {} < min_frames {}（时序证据不足，不判定）".format(
                    n, int(s["min_frames"]))}
    if stab["temporal_split"]:
        return {**base, "verdict": "UNKNOWN", "code": "MMT_TEMPORAL_SPLIT", "rule_id":
                "T1_TEMPORAL_SPLIT", "confidence": "LOW",
                "reason": "镜头内出现视觉状态变化（{}）→ 时序上不是一个稳定画面，不判定".format(
                    stab["reason"])}
    if mean_cos is not None and mean_cos < float(s["min_stability_cos"]):
        return {**base, "verdict": "UNKNOWN", "code": "MMT_LOW_CONSISTENCY",
                "rule_id": "T2_LOW_CONSISTENCY", "confidence": "LOW",
                "reason": "帧间一致性 {} < 下限 {}（画面在镜头内持续变化，语义证据不稳定）".format(
                    mean_cos, float(s["min_stability_cos"]))}
    agg = metrics.get("domains_aggregated") or {}
    ranked = sorted(agg.items(), key=lambda kv: (-kv[1], kv[0]))
    base["ranked_domains"] = [{"domain": d, "sim": round(float(v), 6)} for d, v in ranked]
    base["top_k"] = base["ranked_domains"][:max(1, int(s["top_k"]))]
    exp_med = metrics.get("expected_sim_median")
    other = [(d, float(v)) for d, v in agg.items() if d != expected_domain]
    best_other = max(other, key=lambda kv: kv[1]) if other else (None, 0.0)
    base.update({"best_other_domain": best_other[0],
                 "best_other_sim": round(best_other[1], 6)})
    vote = metrics.get("vote_expected")
    med_margin = metrics.get("margin_median")
    # 其它域的投票占比（用于 T4）
    votes = metrics.get("argmax_votes") or {}
    other_dom, other_votes = None, 0
    for d, c in sorted(votes.items(), key=lambda kv: (-kv[1], kv[0])):
        if d != expected_domain and c > other_votes:
            other_dom, other_votes = d, c
    other_frac = round(other_votes / n, 6) if n else 0.0
    base["other_vote_domain"] = other_dom
    base["other_vote_frac"] = other_frac
    high = bool(mean_cos is not None and mean_cos >= high_cos)
    if (vote is not None and vote >= min_vote and exp_med is not None and exp_med >= min_sim
            and med_margin is not None and med_margin >= margin):
        conf = "HIGH" if (high and med_margin >= 2 * margin) else "MEDIUM"
        return {**base, "verdict": "MATCH", "code": None, "rule_id": "T3_CONSISTENT_MATCH",
                "confidence": conf,
                "reason": ("多帧一致支持期望域：投票占比 {}/{}={} ≥ {}，期望相似度中位数 {} ≥ {}，"
                           "边际中位数 {} ≥ {}（帧间一致性 mean={}）").format(
                    votes.get(expected_domain, 0), n, vote, min_vote, exp_med, min_sim,
                    med_margin, margin, mean_cos)}
    if (other_frac >= min_vote and best_other[1] >= min_sim and med_margin is not None
            and -med_margin >= margin):
        conf = "HIGH" if (high and -med_margin >= 2 * margin) else "MEDIUM"
        return {**base, "verdict": "MISMATCH", "code": None, "rule_id": "T4_CONSISTENT_MISMATCH",
                "confidence": conf,
                "reason": ("多帧一致指向『{}』而不是旁白期望的『{}』：该域投票占比 {} ≥ {}，"
                           "相似度 {} ≥ {}，边际中位数 {} ≤ -{}").format(
                    other_dom, expected_domain, other_frac, min_vote, best_other[1], min_sim,
                    med_margin, margin)}
    if (vote is not None and vote < min_vote and other_frac < min_vote):
        return {**base, "verdict": "UNKNOWN", "code": "MMT_INCONSISTENT",
                "rule_id": "T5_INCONSISTENT",
                "confidence": "LOW",
                "reason": ("逐帧语义投票分散（期望域 {}，最强其它域 {} 占比 {}），帧间结论互相矛盾 → "
                           "不判定；逐帧 argmax={}").format(vote, other_dom, other_frac,
                                                          metrics.get("argmax_votes"))}
    if exp_med is not None and exp_med < min_sim:
        conf = "MEDIUM" if high and not stab["temporal_split"] else "LOW"
        return {**base, "verdict": "UNKNOWN", "code": "MMT_LOW_SIGNAL",
                "rule_id": "T6_LOW_SIGNAL", "confidence": conf,
                "reason": "期望域相似度中位数 {} < 下限 {}（信号不足，不判定）".format(exp_med,
                                                                            min_sim)}
    conf = "MEDIUM" if high and not stab["temporal_split"] else "LOW"
    return {**base, "verdict": "UNKNOWN", "code": "MMT_AMBIGUOUS", "rule_id": "T7_AMBIGUOUS",
            "confidence": conf,
            "reason": ("期望域与最强其它域『{}』的边际中位数 {} 不足 {}（稳定地判不出来）").format(
                best_other[0], med_margin, margin)}


# ---------------- worker（与 5-A 同一个 worker 脚本，追加"返回嵌入"选项） ----------------
def _sha256(p: Path) -> str | None:
    try:
        h = hashlib.sha256()
        with p.open("rb") as fh:
            for c in iter(lambda: fh.read(1 << 20), b""):
                h.update(c)
        return h.hexdigest()
    except OSError:
        return None


def run_temporal_worker(images: list, labels: list, settings: dict, *, root: Path,
                        workdir: Path | None = None) -> dict:
    """调用 CLIP worker（`return_embeddings=true`）。**任何失败都返回 ok=False + code**。"""
    s = {**MMT_DEFAULTS, **(settings or {})}
    model_dir = Path(str(s["model_dir"]))
    if not model_dir.is_absolute():
        model_dir = Path(root) / model_dir
    worker = Path(root) / "src" / "video_studio" / "core" / "mm_worker_clip.py"
    py = Path(str(s["python"]))
    if not py.is_absolute():
        py = Path(root) / py
    out = {"ok": False, "code": None, "detail": None, "similarities": {}, "embeddings": {},
           "model": {}, "versions": {}, "image_sha256": {}}
    if not images:
        out.update(code="MMT_NO_FRAMES", detail="没有可用的抽帧")
        return out
    if not model_dir.is_dir():
        out.update(code="MM_MODEL_MISSING", detail="模型目录不存在: {}".format(model_dir))
        return out
    if not py.is_file():
        out.update(code="MM_PYTHON_MISSING", detail="worker 解释器不存在: {}".format(py))
        return out
    if not worker.is_file():
        out.update(code="MM_WORKER_FAILED", detail="worker 脚本不存在: {}".format(worker))
        return out
    tmp = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="vs_mmt_"))
    tmp.mkdir(parents=True, exist_ok=True)
    job_p, res_p = tmp / "job_temporal.json", tmp / "result_temporal.json"
    job = {"model_dir": str(model_dir), "images": images, "labels": labels,
           "return_embeddings": True}
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


# ---------------- 端到端（只读输入 → 时序三态报告） ----------------
def validate_temporal(frames: list, labels: list, *, root: Path, settings: dict,
                      workdir: Path | None = None, narration_by_scene: dict | None = None,
                      film: str | None = None, sources: dict | None = None,
                      five_a_reference: dict | None = None) -> dict:
    """对已抽好的多帧做**时序**判定，返回完整报告（逐帧证据 + 聚合规则 + 三态 + 置信度）。

    frames: [{"id","path","scene_id","time_s","sha256"}]（同一镜头内按 time_s 升序）
    """
    s = {**MMT_DEFAULTS, **(settings or {})}
    rep = {"schema": SCHEMA, "enabled": bool(s.get("enabled")), "applied": False,
           "model": {}, "versions": {}, "settings": {k: v for k, v in s.items()
                                                     if not k.startswith("_")},
           "settings_source": s.get("_source"), "settings_notes": s.get("_notes") or [],
           "rules": list(TEMPORAL_RULES), "film": film, "sources": sources or {},
           "five_a_reference": five_a_reference or {}, "scenes": [], "counts": {},
           "policy": {"mode": "readonly_advisory", "auto_apply": False, "auto_redo": False,
                      "auto_select": False, "auto_replace": False, "writes_to_db": False,
                      "writes_to_production": False, "changes_selection": False,
                      "changes_timeline": False, "overwrites_4b_results": False,
                      "overwrites_5a_results": False, "requires_human_decision": True,
                      "note": ("多帧/时序层是**平行证据层**：4-B 与 5-A 的结果原样保留、不覆盖不删除；"
                               "本报告不改选材/时间轴/旁白/BGM，不写库、不写生产产物、不触发 redo")},
           "note": "只读时序验证：MATCH/MISMATCH/UNKNOWN 仅供参考，任何改动都需人工决定 + 审批 + redo"}
    by_scene: dict = {}
    for f in frames or []:
        by_scene.setdefault(f["scene_id"], []).append(f)
    if not frames:
        rep["counts"] = {"MATCH": 0, "MISMATCH": 0, "UNKNOWN": len(narration_by_scene or {})}
        rep["error"] = {"code": "MMT_NO_FRAMES", "detail": "没有可用的抽帧"}
        rep["scenes"] = [{"scene_id": sid, "verdict": "UNKNOWN", "code": "MMT_NO_FRAMES",
                          "rule_id": "T0_FAIL_CLOSED", "confidence": "LOW",
                          "reason": "抽帧失败或成片缺失 → fail-closed（不伪造判定）", "frames": []}
                         for sid in sorted(narration_by_scene or {})] or \
                        [{"scene_id": None, "verdict": "UNKNOWN", "code": "MMT_NO_FRAMES",
                          "rule_id": "T0_FAIL_CLOSED", "confidence": "LOW",
                          "reason": "没有可用的抽帧", "frames": []}]
        return rep
    if not labels:
        rep["counts"] = {"MATCH": 0, "MISMATCH": 0, "UNKNOWN": 0}
        rep["error"] = {"code": "MMT_LOW_SIGNAL", "detail": "没有可用的提示词标签"}
        return rep
    res = run_temporal_worker([{"id": f["id"], "path": f["path"]} for f in frames],
                              [{"id": lb["id"], "text": lb["text"]} for lb in labels],
                              s, root=root, workdir=workdir)
    rep["model"] = res.get("model") or {}
    rep["versions"] = res.get("versions") or {}
    if not res.get("ok"):
        code = res.get("code") or "MM_WORKER_FAILED"
        rep["error"] = {"code": code, "detail": res.get("detail")}
        rep["counts"] = {"MATCH": 0, "MISMATCH": 0, "UNKNOWN": len(by_scene)}
        for sid, fs in sorted(by_scene.items(), key=lambda kv: str(kv[0])):
            rep["scenes"].append({
                "scene_id": sid, "verdict": "UNKNOWN", "code": code,
                "rule_id": "T0_FAIL_CLOSED", "confidence": "LOW",
                "reason": "模型/环境不可用 → fail-closed（不伪造判定）",
                "frames": [{"id": f["id"], "time_s": f.get("time_s"), "sha256": f.get("sha256")}
                           for f in sorted(fs, key=lambda x: x.get("time_s") or 0)]})
        return rep
    sims = res.get("similarities") or {}
    embs = res.get("embeddings") or {}
    label_domain = {lb["id"]: lb.get("domain") or lb["id"] for lb in labels}
    emb_meta = {"embeddings_returned": bool(embs),
                "embedding_dim": (len(next(iter(embs.values()))) if embs else None)}
    counts = {"MATCH": 0, "MISMATCH": 0, "UNKNOWN": 0}
    for sid, fs in sorted(by_scene.items(), key=lambda kv: str(kv[0])):
        ordered = sorted(fs, key=lambda x: x.get("time_s") or 0)
        records = []
        for f in ordered:
            by_domain: dict[str, list] = {}
            for lid, v in (sims.get(f["id"]) or {}).items():
                d = label_domain.get(lid, lid)
                by_domain.setdefault(d, []).append(float(v))
            # 同域多提示词取**均值**（与 5-A 的逐域口径一致，保证两层可比）
            scores = {d: sum(vs) / len(vs) for d, vs in by_domain.items() if vs}
            records.append({"id": f["id"], "time_s": f.get("time_s"), "sha256": f.get("sha256"),
                            "scores": scores, "embedding": embs.get(f["id"]) or []})
        narr = (narration_by_scene or {}).get(sid) or {}
        exp = expected_domain_from_narration(narr.get("text") or "")
        metrics = temporal_metrics(records, exp.get("domain"))
        v = temporal_verdict(metrics, exp.get("domain"), s)
        counts[v["verdict"]] = counts.get(v["verdict"], 0) + 1
        ref = {x.get("scene_id"): x for x in ((five_a_reference or {}).get("scenes") or [])
               if isinstance(x, dict)}
        rep["scenes"].append({
            "scene_id": sid, "verdict": v["verdict"], "code": v.get("code"),
            "rule_id": v.get("rule_id"), "confidence": v.get("confidence"),
            "reason": v.get("reason"),
            "expected_domain": v["expected_domain"],
            "expected_domain_source": exp.get("method"),
            "narration_sha256": (hashlib.sha256((narr.get("text") or "").encode("utf-8"))
                                 .hexdigest() if narr.get("text") else None),
            "narration_text": (narr.get("text") or "")[:200],
            "narration_matched_forms": exp.get("matched") or {},
            "frame_count": len(records), **emb_meta,
            "stability": {"class": v.get("stability_class"), "split": v.get("temporal_split"),
                          "visual_stability_mean": v.get("visual_stability_mean"),
                          "visual_stability_min": v.get("visual_stability_min"),
                          "adjacent_cos": metrics.get("adjacent_cos"),
                          "dispersion": v.get("dispersion")},
            "aggregate": {"expected_sim_median": v.get("expected_sim_median"),
                          "expected_sim_min": v.get("expected_sim_min"),
                          "expected_sim_mean": v.get("expected_sim_mean"),
                          "median_margin": v.get("median_margin"),
                          "margin_min": v.get("margin_min"),
                          "vote_expected": v.get("vote_expected"),
                          "argmax_votes": v.get("argmax_votes"),
                          "other_vote_domain": v.get("other_vote_domain"),
                          "other_vote_frac": v.get("other_vote_frac"),
                          "best_other_domain": v.get("best_other_domain"),
                          "best_other_sim": v.get("best_other_sim"),
                          "domains_aggregated": metrics.get("domains_aggregated"),
                          "top_k": v.get("top_k")},
            "frames": metrics.get("per_frame"),
            "five_a_verdict": (ref.get(sid) or {}).get("verdict"),
            "five_a_code": (ref.get(sid) or {}).get("code"),
            "five_a_expected_sim": (ref.get(sid) or {}).get("expected_sim"),
            "five_a_delta": (ref.get(sid) or {}).get("delta"),
            "five_a_frames": (ref.get(sid) or {}).get("frames_per_scene"),
        })
    rep["counts"] = counts
    rep["applied"] = True
    return rep
