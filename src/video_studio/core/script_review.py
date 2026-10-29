# -*- coding: utf-8 -*-
"""人工审稿：把 script_output 导出成可编辑稿，再把改好的稿子回填成新版本。

## 为什么需要（2026-10-20）

工程内的"梗/人味"没有来源：`src/` 全量检索 `梗/幽默/joke/humor/punchline`
只命中两处平台画像注释，没有生成器、没有梗库、没有密度指标。实测定稿的
`retention.emotion_beats` 在缺 v3 元数据时直接 `NOT_ASSESSABLE`（等于不评）。
**结论：人的判断必须能进入流程，否则永远只有"LLM 概率涌现"的那两成好句子。**

## 设计（三件事，互不耦合）

1. **导出**（`build_review` / `render_markdown`）：只读。把 `script_output.segments`
   摊成"一行一段"的 markdown（`@@S01 正文`），带字数/预估时长/情绪节拍/预算，
   人只改那一行，其余随便写批注。
2. **回填**（`parse_markdown` / `apply_review`）：纯函数 + 一次落盘
   （`<项目>/media/script_review.json`）。校验：段数、空段、字数漂移、
   节拍名泄漏、AI 味词、红线（事实句带梗）。
3. **消费**（`load_review`）：`ScriptAgent.run` 若发现该文件存在 ⇒ **不再调 LLM**，
   直接以人工稿落产物（`source=human_review`），因此 `redo` 会稳定复现人改的稿。

**为什么不直接改 DB 里的 artifact**：artifact 是 append-only；直接改会破坏
可追溯性。这里走"新文件 + 新版本任务"的既有链路。
"""
from __future__ import annotations

import json
import pathlib
import re
import time

SCHEMA = "script-review-v1"
REVIEW_REL = pathlib.Path("media") / "script_review.json"
REVIEW_MD_REL = pathlib.Path("media") / "script_review.md"

#: 中文口播折算（实测本仓库成片：2330 字 / 460s ≈ 5.07 字/秒）
CHARS_PER_SEC = 5.0
#: 单段字数允许漂移
SEG_TOL = 0.30
#: 全片字数允许漂移（超过就要显式 `--allow-drift`，因为时长/素材/字幕全会变）
FILM_TOL = 0.05

#: 审稿行标记：`@@S01 正文…`（人只改这一行，其余为批注，解析时忽略）
MARK_RE = re.compile(r"^\s*@@S(\d{1,3})\s+(.*\S)\s*$", re.M)

EMOTION_BEATS = ("curiosity", "tension", "payoff", "calm", "surprise")
#: 节拍名/字段名不得出现在正文（与 ScriptAgent 提示词纪律一致）
LEAK_TOKENS = EMOTION_BEATS + ("retention_device", "emotion_beat", "cta_plan", "hook_map",
                               "hook_structure", "信息增量点", "悬念", "兑现")
#: AI 味/公文腔（命中即建议改写；不阻断，只警告）
AI_FLAVOR = ("综上所述", "值得注意的是", "不难发现", "具有重要意义", "在当今时代",
             "随着", "众所周知", "显而易见", "总而言之", "一定程度上")

#: 审稿 5 问（与 config/humor_pack.md §七 一致）
CHECKLIST = (
    ("concrete_person", "有没有一个具体的人？（有名字/身份/处境，不是「人们」）"),
    ("screenshot_line", "有没有一句能被截图的话？（≤20 字、有态度）"),
    ("counterintuitive", "有没有一个反常识？（与常见认知相反且站得住）"),
    ("analogy", "有没有一个世俗类比？（用生活物件解释抽象机制）"),
    ("callback", "结尾回扣了开头吗？"),
)


# ---------------------------------------------------------------- 读
def find_script_artifact(project_dir, project_id: str | None = None,
                         db_path=None) -> tuple[pathlib.Path | None, dict | None]:
    """取该项目**最新的 script_output** 产物（只读）。

    优先走 DB 的 `artifacts.type='script_output'`（精确）；DB 不可用时回退到
    "按 mtime 找最新且含 segments[narration] 的 json"（启发式）。
    """
    adir = pathlib.Path(project_dir) / "artifacts"
    if db_path and project_id:
        try:
            import sqlite3
            con = sqlite3.connect(str(db_path))
            row = con.execute(
                "select artifact_id, path from artifacts where project_id=? and "
                "type='script_output' order by rowid desc limit 1", (project_id,)).fetchone()
            con.close()
            if row:
                cand = pathlib.Path(row[1])
                if not cand.is_file():
                    cand = adir / "{}.json".format(row[0])
                if cand.is_file():
                    d = json.loads(cand.read_text(encoding="utf-8"))
                    if isinstance(d, dict) and isinstance(d.get("segments"), list):
                        return cand, d
        except Exception:                                   # noqa: BLE001
            pass
    if not adir.is_dir():
        return None, None
    cands = []
    for p in adir.glob("*.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(d, dict) and isinstance(d.get("segments"), list) and d["segments"]:
            if all(isinstance(s, dict) and "narration" in s for s in d["segments"]):
                # 更像 script_output 的优先（有标题/CTA/钩子等脚本字段）
                bonus = 1 if any(k in d for k in
                                 ("titles", "cta_plan", "hook_map", "narrative_route",
                                  "topic_understanding")) else 0
                cands.append((bonus, p.stat().st_mtime, p, d))
    if not cands:
        return None, None
    cands.sort(key=lambda x: (x[0], x[1], x[2].name))
    _, _, path, payload = cands[-1]
    return path, payload


def est_seconds(text: str) -> float:
    return round(len(_norm_text(text)) / CHARS_PER_SEC, 1)


def _norm_text(t: str) -> str:
    return re.sub(r"\s+", "", str(t or ""))


# ---------------------------------------------------------------- 导出
def build_review(project_dir, project_id: str | None = None, db_path=None) -> dict:
    path, payload = find_script_artifact(project_dir, project_id=project_id, db_path=db_path)
    if payload is None:
        return {"schema": SCHEMA, "found": False, "reason": "no_script_output"}
    segs = []
    total = 0
    for i, s in enumerate(payload.get("segments") or []):
        n = str(s.get("narration") or "")
        n_chars = len(_norm_text(n))
        total += n_chars
        segs.append({
            "index": i,
            "mark": "@@S{:02d}".format(i + 1),
            "chapter": str(s.get("chapter") or ""),
            "narration": n,
            "chars": n_chars,
            "est_s": est_seconds(n),
            "declared_s": s.get("duration_s"),
            "emotion_beat": s.get("emotion_beat"),
            "retention_device": s.get("retention_device"),
            "visual_hint": str(s.get("visual_hint") or ""),
        })
    return {
        "schema": SCHEMA, "found": True,
        "base_artifact": str(path),
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "segments": segs,
        "total_chars": total,
        "total_est_s": round(total / CHARS_PER_SEC, 1),
        "summary": payload.get("summary"),
        "titles": payload.get("titles") or [],
    }


def render_markdown(review: dict, humor_hint: bool = True) -> str:
    if not review.get("found"):
        return "# 审稿稿\n\n未找到 script_output 产物（{}）。\n".format(
            review.get("reason"))
    L = []
    L.append("# 审稿稿 · {} 段 / {} 字 / 约 {}s".format(
        len(review["segments"]), review["total_chars"], review["total_est_s"]))
    L.append("")
    L.append("> **只改 `@@Sxx` 开头的那一行**，其余（说明/批注/空行）随便写，解析时忽略。")
    L.append("> 改完执行：`run.py script-apply <项目ID> --file <本文件> --checklist 11111`")
    if humor_hint:
        L.append("> 弹药库：`config/humor_pack.md`（句式模板 / 世俗类比 / 数字人话 / 口语连接）")
    L.append("> 事实句、数字、时间、人名**不许加梗**；梗只加在解释层。")
    L.append("")
    L.append("| 段 | 章节 | 字数 | 预估 | 预算(±30%) | 节拍 | 留存装置 |")
    L.append("|---|---|---|---|---|---|---|")
    for s in review["segments"]:
        lo = max(1, int(s["chars"] * (1 - SEG_TOL)))
        hi = int(s["chars"] * (1 + SEG_TOL))
        L.append("| S{:02d} | {} | {} | {}s | {}-{} 字 | {} | {} |".format(
            s["index"] + 1, s["chapter"] or "-", s["chars"], s["est_s"], lo, hi,
            s["emotion_beat"] or "-", s["retention_device"] or "-"))
    L.append("")
    L.append("---")
    L.append("")
    for s in review["segments"]:
        L.append("### S{:02d} · {} · {} · {} 字".format(
            s["index"] + 1, s["chapter"] or "-", s["est_s"], s["chars"]))
        if s.get("visual_hint"):
            L.append("<!-- 画面提示：{} -->".format(s["visual_hint"]))
        L.append("{} {}".format(s["mark"], s["narration"]))
        L.append("")
    L.append("---")
    L.append("")
    L.append("## 审稿 5 问（apply 时用 `--checklist` 回答，1=是 0=否）")
    L.append("")
    for k, q in CHECKLIST:
        L.append("- `{}` {}".format(k, q))
    L.append("")
    L.append("## 本稿欠账（apply 时用 `--notes` 写，会存进审稿台账）")
    L.append("")
    L.append("- ")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- 解析/校验
def parse_markdown(text: str) -> dict:
    """从审稿 md 里抽 `@@Sxx 正文`。返回 {index0_based: narration}。"""
    out: dict[int, str] = {}
    for m in MARK_RE.finditer(text or ""):
        idx = int(m.group(1)) - 1
        body = m.group(2).strip()
        if idx >= 0 and body:
            out[idx] = body
    return out


def check_narration(text: str) -> list[str]:
    """单段文本体检：节拍名泄漏 + AI 味词。"""
    warnings = []
    for tok in LEAK_TOKENS:
        if tok and tok in text:
            warnings.append("节拍名/字段名泄漏：{}".format(tok))
    for tok in AI_FLAVOR:
        if tok in text:
            warnings.append("AI 味/公文腔：{}".format(tok))
    return warnings


def apply_review(base_payload: dict, new_map: dict, *, checklist: dict | None = None,
                 notes: str = "", allow_drift: bool = False) -> dict:
    """校验并把新稿合并回 payload。返回 {ok, errors, warnings, payload, stats}。"""
    errors: list[str] = []
    warnings: list[str] = []
    base_segs = list(base_payload.get("segments") or [])
    if not base_segs:
        return {"ok": False, "errors": ["base_payload 无 segments"], "warnings": [], "payload": None}
    if not new_map:
        return {"ok": False, "errors": ["没有解析到任何 @@Sxx 行"], "warnings": [], "payload": None}
    missing = [i for i in range(len(base_segs)) if i not in new_map]
    if missing:
        errors.append("缺少段：{}".format(", ".join("S{:02d}".format(i + 1) for i in missing)))
    extra = [i for i in new_map if i >= len(base_segs)]
    if extra:
        errors.append("多出段：{}（段数不可增删；要拆段请先改结构闸门）".format(
            ", ".join("S{:02d}".format(i + 1) for i in extra)))

    old_chars = sum(len(_norm_text(s.get("narration") or "")) for s in base_segs)
    new_chars = 0
    merged = []
    for i, s in enumerate(base_segs):
        seg = dict(s)
        if i in new_map:
            n = new_map[i]
            # 只有**真的改了文本**才重估时长：未改动的段保留原 `duration_s`
            # （原值可能来自真实 TTS 实测窗口，用字数估会覆盖掉权威时长）
            if _norm_text(n) != _norm_text(s.get("narration") or ""):
                seg["narration"] = n
                seg["duration_s"] = est_seconds(n)
            n_chars = len(_norm_text(seg.get("narration") or ""))
            new_chars += n_chars
            old_n = len(_norm_text(s.get("narration") or ""))
            if old_n >= 12 and abs(n_chars - old_n) > old_n * SEG_TOL:
                warnings.append("S{:02d} 字数漂移 {:+.0%}（{}→{} 字），会改变配音时长".format(
                    i + 1, (n_chars - old_n) / old_n, old_n, n_chars))
            for w in check_narration(str(seg.get("narration") or "")):
                warnings.append("S{:02d} {}".format(i + 1, w))
        else:
            new_chars += len(_norm_text(s.get("narration") or ""))
        merged.append(seg)

    ratio = ((new_chars - old_chars) / old_chars) if old_chars else 0.0
    stats = {"old_chars": old_chars, "new_chars": new_chars, "delta_ratio": round(ratio, 4),
             "old_est_s": round(old_chars / CHARS_PER_SEC, 1),
             "new_est_s": round(new_chars / CHARS_PER_SEC, 1)}
    if abs(ratio) > FILM_TOL and not allow_drift:
        errors.append("全片字数漂移 {:+.1%} 超过 ±{:.0%}：时长/素材窗口/字幕都会变；"
                      "确认要重排请加 --allow-drift".format(ratio, FILM_TOL))
    if checklist is not None:
        unanswered = [k for k, _ in CHECKLIST if k not in checklist]
        if unanswered:
            warnings.append("5 问未全部回答：{}（不阻断，但会进台账）".format(
                ", ".join(unanswered)))
    payload = dict(base_payload)
    payload["segments"] = merged
    payload["source"] = "human_review"
    payload["human_review"] = {
        "schema": SCHEMA, "reviewed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "checklist": checklist or {}, "notes": notes,
        "stats": stats, "source": "human_review",
    }
    return {"ok": not errors, "errors": errors, "warnings": warnings,
            "payload": payload, "stats": stats}


# ---------------------------------------------------------------- 落盘/消费
def save_review(project_dir, payload: dict) -> pathlib.Path:
    p = pathlib.Path(project_dir) / REVIEW_REL
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


def load_review(project_dir) -> dict | None:
    """供 ScriptAgent 消费：存在则返回人工稿 payload，否则 None。"""
    p = pathlib.Path(project_dir) / REVIEW_REL
    if not p.is_file():
        return None
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not (isinstance(d, dict) and isinstance(d.get("segments"), list) and d["segments"]):
        return None
    return d


def parse_checklist(raw: str) -> dict:
    """解析 `--checklist`：支持 `11110`（按 CHECKLIST 顺序）或 `key=1,key2=0`。"""
    s = (raw or "").strip()
    out: dict = {}
    if not s:
        return out
    if re.fullmatch(r"[01]+", s):
        for i, ch in enumerate(s[:len(CHECKLIST)]):
            out[CHECKLIST[i][0]] = (ch == "1")
        return out
    for part in re.split(r"[,;\s]+", s):
        if not part or "=" not in part:
            continue
        k, v = part.split("=", 1)
        if k.strip() in dict(CHECKLIST):
            out[k.strip()] = v.strip() in ("1", "true", "True", "yes", "y", "是")
    return out


def build_payload_from_review(review: dict, base: dict | None = None) -> dict:
    payload = dict(base or {})
    payload.update({k: review[k] for k in
                    ("topic_understanding", "core_viewpoint", "narrative_route",
                     "titles", "opening_alternatives", "fact_risks", "cta_plan",
                     "hook_map", "recommended_title", "recommended_opening")
                    if k in review})
    payload["segments"] = review["segments"]
    payload["summary"] = str((review.get("human_review") or {}).get("notes")
                             or payload.get("summary") or "人工审稿稿")[:200]
    payload["source"] = "human_review"
    return payload
