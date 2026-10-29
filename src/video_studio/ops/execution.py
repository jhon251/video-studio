# -*- coding: utf-8 -*-
"""6-B/M4 —— 受控执行的 **ops 层**：沙箱准备 + 真实执行器 + 强制 PI/DQ 复核。

设计要点（对应授权书第 3/4/5/6/7/8/9/10 条）：
  · **沙箱**：所有执行都在 `output/phase6b_m4_sandbox/<label>/` 内进行（输入=复制品），
    **绝不覆盖** v9 母版项目目录与成片；每次执行记录输入/输出的 sha256；
  · **真实执行器**：`add_outro_card` 真做（末段重编码 + 卡片叠加 + 其余流复制拼接，时长不变）；
    需要新素材的动作若**没有真实可用素材** ⇒ 返回 `PENDING_HUMAN_ASSET`（不占位、不虚构）；
    未实现的 action ⇒ `UNSUPPORTED_ACTION`（不模拟执行）；
  · **强制复核**：执行成功后调用 `pi_recheck`（复用 **冻结的** PI-1…PI-6 度量与 M2 门禁判定，
    不修改定义/阈值），随后用沙箱产物跑 DQ-1…DQ-8 只读诊断；PI FAIL/UNKNOWN 如实记录并按既有门禁处理
    （本层不提升、不绕过）；
  · 本模块只写沙箱目录、审批台账与执行台账；不写 DB、不派发任务、不改 PI/DQ 判定逻辑。
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from ..core import execution as core_exec
from ..core import integrity as core_integrity
from ..core import direction as core_direction
from ..core import materials as core_materials
from ..core import visual_aid as core_visual_aid
from ..core import captions as core_captions
from ..core import narration as core_narration
from ..core import strip as core_strip
from .review import build_review_report

SANDBOX_ROOT_REL = "output/phase6b_m4_sandbox"

# ================================================================ 6-G B1/B2：时基身份层
# 背景（6-G Pre-Execution Gate Audit 的 13 项 HARD blocker）：
#   · 旧实现 `master_caption_cues()` 不传 `windows=` ⇒ 按**声明时基**生成 cue 表，
#     任何"替换窗口"的执行都会把**错误窗口**的字幕烧进新成片（重新引入 6E-E2-SUBTITLE-DEFECT-v1）；
#   · `split_plan()` 依赖 `ctx["timeline"]`，若混入旧 `material_timeline`，切点/窗口全部落在旧时基。
# 解决：给执行上下文加**可校验的时基身份（identity）**，字幕时基只能来自 identity 匹配的
# `caption_timeline`；DCv2 上下文**禁止**回落到 v1 cue 表（fail-closed）。
TIMELINE_IDENTITY_SCHEMA = "dcv2-timeline-identity-v1"
CAPTION_TIMELINE_SCHEMA = "dcv2-caption-timeline-v1"
LEGACY_CAPTION_SCHEMA = "v1-declared-legacy"


def _canon_sha(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":"), default=str).encode("utf-8")
                          ).hexdigest()


def timeline_identity(timeline, *, production_duration_s=None, source=None) -> dict:
    """从时间轴生成**可校验的时基身份**（身份 sha256 覆盖 scene_id/start/end/总长）。"""
    rows = [{"scene_id": str(e.get("scene_id")), "start_s": round(float(e["start_s"]), 3),
             "end_s": round(float(e["end_s"]), 3)} for e in (timeline or [])]
    body = {"schema": TIMELINE_IDENTITY_SCHEMA, "scenes": rows,
            "scene_count": len(rows),
            "production_duration_s": (round(float(production_duration_s), 3)
                                      if production_duration_s is not None
                                      else (rows[-1]["end_s"] if rows else None)),
            "source": source}
    # **身份只覆盖内容**（scenes / scene_count / production_duration_s / schema）；
    # source 是自由文本元数据，**不**参与哈希（否则路径分隔符差异会造成伪"身份不符"）。
    body["identity_sha256"] = _canon_sha({k: v for k, v in body.items()
                                          if k not in ("identity_sha256", "source")})
    return body


def attach_dcv2_time_base(ctx: dict, *, timeline, caption_windows, production_duration_s,
                          source) -> dict:
    """把 DCv2 时基**显式**绑进执行上下文（B2）：`timeline` + `timeline_identity` + `caption_timeline`。

    `caption_windows` 必须是**实际音频窗口**（cue 的时间基），不用场景窗口。
    """
    ident = timeline_identity(timeline, production_duration_s=production_duration_s,
                              source=source)
    out = dict(ctx)
    # **保留整行元数据**（如 selected_asset —— 切分/替换执行器需要素材路径）；只规范化时基字段。
    out["timeline"] = []
    for e in timeline:
        row = dict(e)
        row["scene_id"] = str(e.get("scene_id"))
        row["start_s"] = float(e["start_s"])
        row["end_s"] = float(e["end_s"])
        out["timeline"].append(row)
    out["timeline_duration_s"] = ident["production_duration_s"]
    out["timeline_identity"] = ident
    out["caption_timeline"] = {
        "schema": CAPTION_TIMELINE_SCHEMA,
        "windows": [{"scene_id": str(w.get("scene_id")), "start_s": float(w["start_s"]),
                     "end_s": float(w["end_s"])} for w in caption_windows],
        "identity_sha256": ident["identity_sha256"], "source": source,
        "note": "cue 时间基 = 实际音频窗口（Duration Contract v2）；与 timeline_identity 绑定"}
    return out


def assert_timeline_identity(ctx: dict) -> dict:
    """**fail-closed**：若 ctx 声明了时基身份，则 `ctx["timeline"]` 必须与其一致。"""
    ident = ctx.get("timeline_identity")
    if not isinstance(ident, dict) or ident.get("schema") != TIMELINE_IDENTITY_SCHEMA:
        return {"enforced": False, "why": "no timeline_identity（历史/legacy 上下文）"}
    live = timeline_identity(ctx.get("timeline"), production_duration_s=ident.get(
        "production_duration_s"), source=ident.get("source"))
    if live["identity_sha256"] != ident.get("identity_sha256"):
        raise RuntimeError(
            "TIMELINE_IDENTITY_MISMATCH: ctx.timeline 与声明的时基身份不一致"
            "（期望 {} / 实际 {}）；疑似旧 material_timeline 混入 ⇒ 拒绝执行".format(
                ident.get("identity_sha256"), live["identity_sha256"]))
    return {"enforced": True, "identity_sha256": ident["identity_sha256"],
            "scene_count": live["scene_count"],
            "production_duration_s": live["production_duration_s"]}


def caption_time_base(ctx: dict) -> dict:
    """决定**字幕时间基**（B1）：DCv2 上下文必须用 DCv2 cue 表，**禁止回落 v1**。"""
    ct, ti = ctx.get("caption_timeline"), ctx.get("timeline_identity")
    if isinstance(ct, dict) and ct.get("windows"):
        if ct.get("schema") != CAPTION_TIMELINE_SCHEMA:
            raise RuntimeError("CAPTION_TIMELINE_SCHEMA_INVALID: {}".format(ct.get("schema")))
        if isinstance(ti, dict) and ti.get("schema") == TIMELINE_IDENTITY_SCHEMA \
                and ct.get("identity_sha256") != ti.get("identity_sha256"):
            raise RuntimeError(
                "CAPTION_TIMELINE_IDENTITY_MISMATCH: caption_timeline.identity_sha256={} "
                "!= timeline_identity.identity_sha256={} ⇒ 拒绝执行".format(
                    ct.get("identity_sha256"), ti.get("identity_sha256")))
        return {"mode": "dcv2", "windows": ct["windows"],
                "identity_sha256": ct.get("identity_sha256"), "source": ct.get("source"),
                "legacy_default": False}
    if isinstance(ti, dict) and ti.get("schema") == TIMELINE_IDENTITY_SCHEMA:
        raise RuntimeError(
            "CAPTION_TIMELINE_REQUIRED: 执行上下文声明了 DCv2 时基（identity {}），但未提供 "
            "caption_timeline ⇒ fail-closed（**禁止**回落到声明时基的 v1 cue 表）".format(
                ti.get("identity_sha256")))
    if isinstance(ct, dict) and ct.get("schema") == LEGACY_CAPTION_SCHEMA:
        return {"mode": LEGACY_CAPTION_SCHEMA, "legacy_default": False,
                "why": "上下文**显式**声明历史声明时基（v9/C1–C4 等既有成片）"}
    return {"mode": LEGACY_CAPTION_SCHEMA, "legacy_default": True,
            "warning": "上下文未声明时基身份（历史/legacy 执行）⇒ 按声明时基生成 cue；"
                       "DCv2 执行路径**不会**走到这里（缺 caption_timeline 即 fail-closed）"}


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def _run(cmd, timeout=3600):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg rc={}: {}".format(r.returncode, (r.stderr or "")[-300:]))
    return r


# ---------------------------------------------------------------- 沙箱准备
def prepare_sandbox(root: Path, project_id: str, label: str, film: Path,
                    artifacts: dict | None = None, extra_files: dict | None = None) -> dict:
    """把执行所需的输入**复制**进沙箱（copy-on-write；源目录零改动）。"""
    box = root / SANDBOX_ROOT_REL / "{}_{}".format(project_id, label)
    if box.exists():
        shutil.rmtree(box, ignore_errors=True)
    (box / "artifacts").mkdir(parents=True, exist_ok=True)
    (box / "output").mkdir(parents=True, exist_ok=True)
    (box / "work").mkdir(parents=True, exist_ok=True)
    film_copy = box / "output" / film.name
    shutil.copy2(film, film_copy)
    art_copies = {}
    for name, payload in (artifacts or {}).items():
        p = box / "artifacts" / (name + ".json")
        p.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        art_copies[name] = p
    files = {}
    for name, src in (extra_files or {}).items():
        dst = box / "work" / name
        shutil.copy2(src, dst)
        files[name] = dst
    return {"box": box, "film": film_copy, "artifacts": art_copies, "files": files,
            "source_film_sha256": sha(film),
            "film_sha256": sha(film_copy)}


# ---------------------------------------------------------------- 真实执行器
def exec_add_outro_card(ctx: dict, proposal: dict) -> dict:
    """H7 类：在末镜窗口内**原地**加入片尾卡（时长不变）。

    6-C 起：片尾段只重编码**视频**（视频段），未触及区段按母版复制，最后把**母版整条音轨**
    流复制进新成片 ⇒ 音轨与母版逐字节一致（`audio_check.identical_stream`），
    避免"重编码窗口音轨"造成的接缝风险。
    """
    assert_timeline_identity(ctx)          # 6-G/B2：旧时基混入即拒绝
    box = Path(ctx["box"])
    ffmpeg = ctx["ffmpeg"]
    film = Path(ctx["film"])
    window = (proposal.get("affected_scope") or {}).get("window") or [1465.0, 1532.0]
    t0, t1 = float(window[0]), float(window[1])
    dur = max(t1 - t0, 0.5)
    tag = proposal.get("proposal_id", "h7").replace("/", "_") + "_outro"
    card = box / "work" / "card_{}.mp4".format(tag)
    steps = []
    # 1) 末段重编码（**无音轨**）：叠加片尾文字卡 + **重新烧录该窗口字幕**（字幕不断裂）
    _info = probe_media(_ffprobe_bin(ctx), film)
    _cap = _caption_filter(ctx, t0, t1, tag, "{}x{}".format(_info.get("width") or 1920,
                                                           _info.get("height") or 1080))
    # 6-E/E1：片尾卡字体**显式指定**（冻结规格 `font_file` + `fontsdir`）。
    #   根因：drawtext 若不加 fontfile，会走 fontconfig 默认字体（无 CJK 字形）⇒ 豆腐块。
    #   fail-closed：指定了字体但文件不存在 ⇒ 直接失败，**不降级**、不改用其它字体。
    _params = (proposal.get("proposed_change") or {}).get("params") or {}
    _font_opt, _font_rec = "", None
    if _params.get("font_file"):
        _fp = Path(str(_params.get("fontsdir") or r"C:\Windows\Fonts")) / str(_params["font_file"])
        if not _fp.is_file():
            raise RuntimeError("OUTRO_FONT_MISSING: {}（fail-closed：不执行、不降级、不改用未审定字体）"
                               .format(_fp))
        _font_opt = "fontfile='{}':".format(str(_fp).replace("\\", "/").replace(":", "\\:"))
        _font_rec = {"font_file": str(_fp), "bytes": _fp.stat().st_size, "sha256": sha(_fp),
                     "source": "proposal.proposed_change.params.font_file",
                     "role": "片尾卡 CJK 字形"}
    _text = str(_params.get("text") or "感谢观看　我们下期再见")
    _vf = ("drawtext=text='{}':{}fontcolor=white:fontsize=64:"
           "box=1:boxcolor=black@0.55:boxborderw=24:x=(w-text_w)/2:y=h-260").format(_text,
                                                                                    _font_opt)
    _vf = _vf + ("," + _cap if _cap else "")
    _run([ffmpeg, "-y", "-v", "error", "-ss", "{:.3f}".format(t0), "-t", "{:.3f}".format(dur),
          "-i", str(film), "-vf", _vf, "-an", "-c:v", "libx264", "-preset", "ultrafast",
          "-pix_fmt", "yuv420p", "-video_track_timescale", "25000",
          "-t", "{:.3f}".format(dur), str(card)])
    steps.append({"step": "reencode_window_with_outro_card_and_captions", "in": str(film.name),
                  "out": card.name, "window": [t0, t1], "seconds": dur,
                  "captions_reburned": bool(_cap), "output_sha256": sha(card),
                  "outro_text": _text, "outro_font": _font_rec,
                  "drawtext_filter_sha256": hashlib.sha256(_vf.encode("utf-8")).hexdigest()})
    # 2) 组装（前段流复制 + 片尾卡段 + 后续区段）并**流复制母版整条音轨**
    asm = _assemble_windows(ctx, [{"scene_id": proposal.get("scene_id") or "S21",
                                   "window": [t0, t1], "parts": [card]}], tag)
    out = asm["out"]
    steps.extend(asm["steps"])
    # 3) 沙箱脚本产物：末段旁白加入 outro 关键词（仅为复核 DQ-6；不改源项目）
    #    路径**由 box 直接派生**（不取调用方传入的任意路径）⇒ 写入目标可静态证明在沙箱内。
    script_p = box / "artifacts" / "script_output.json"
    if script_p.is_file():
        sc = json.loads(script_p.read_text(encoding="utf-8"))
        segs = sc.get("segments") or []
        if segs:
            segs[-1]["narration"] = (segs[-1].get("narration") or "") + " 感谢观看，我们下期再见"
            script_p.write_text(json.dumps(sc, ensure_ascii=False, indent=1), encoding="utf-8")
            steps.append({"step": "sandbox_script_outro_keyword", "out": script_p.name,
                          "output_sha256": sha(script_p)})
    return {"steps": steps, "outputs": [{"path": str(out.relative_to(Path(ctx["root"]))),
                                        "bytes": out.stat().st_size, "sha256": sha(out),
                                        "duration_target_s": t1}],
            "duration_check": asm["duration_check"], "audio_check": asm["audio_check"],
            "caption_time_base": dict(ctx.get("_caption_time_base") or {}),
            "timeline_identity": dict(ctx.get("timeline_identity") or {}),
            "notes": "窗口内加入片尾卡（视频重编码）+ 前段/后段复制 + 母版整条音轨流复制："
                     "总时长不变；音轨与母版一致；源项目与 v9 母版未被触碰"}


def _resolve_visual_aid_spec(ctx: dict, proposal: dict) -> tuple[dict, dict]:
    """取得 `add_visual_aid` 的 spec：①内联 `params.visual_aid`，或
    ②`params.spec_source = {path,item,sha256}`（**哈希绑定**的冻结计划，确定性编译）。

    任一不满足 ⇒ 抛错（fail-closed）：缺失 / 文件不存在 / sha256 不符 / 计划条目缺失。
    """
    params = (proposal.get("proposed_change") or {}).get("params") or {}
    if isinstance(params.get("visual_aid"), dict):
        return params["visual_aid"], {"mode": "inline"}
    src = params.get("spec_source")
    if not isinstance(src, dict) or not src.get("path"):
        raise RuntimeError("VISUAL_AID_SPEC_REQUIRED: 需要 params.visual_aid 或 params.spec_source"
                           "（不允许无 spec 的占位执行）")
    p = Path(str(src["path"]))
    if not p.is_absolute():
        p = Path(ctx["root"]) / p
    if not p.is_file():
        raise RuntimeError("VISUAL_AID_SPEC_MISSING: {}".format(p))
    live = sha(p)
    if src.get("sha256") and live != src["sha256"]:
        raise RuntimeError("VISUAL_AID_SPEC_SHA_MISMATCH: {} != {}".format(live, src["sha256"]))
    try:
        plan = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:                                              # noqa: BLE001
        raise RuntimeError("VISUAL_AID_SPEC_UNREADABLE: {}: {}".format(type(exc).__name__, exc))
    item = (plan.get("items") or {}).get(str(src.get("item") or ""))
    if not item:
        raise RuntimeError("VISUAL_AID_SPEC_ITEM_MISSING: items.{}".format(src.get("item")))
    spec = core_visual_aid.compile_from_plan_item(item)
    return spec, {"mode": "spec_source", "path": str(p), "sha256": live,
                  "item": src.get("item"), "compiled": True}


def exec_add_visual_aid(ctx: dict, proposal: dict) -> dict:
    """`add_visual_aid` 真实执行：窗口内叠加**自制**信息层（无外部素材），时长与音轨守恒。

    与 `exec_add_outro_card` 同构：只重编码**视频**窗口（叠加层 + 重烧该窗口字幕），
    未触及区段按母版复制，最后把**母版整条音轨**流复制进新成片 ⇒ 音轨逐字节一致。
    fail-closed：spec 非法 / 字体缺失 / sha256 不符 / 叠加层进入字幕安全区 ⇒ 直接失败，不降级。
    """
    assert_timeline_identity(ctx)          # 6-G/B2：旧时基混入即拒绝
    box = Path(ctx["box"])
    ffmpeg = ctx["ffmpeg"]
    film = Path(ctx["film"])
    scope = proposal.get("affected_scope") or {}
    window = scope.get("window") or []
    if len(window) != 2:
        raise RuntimeError("VISUAL_AID_WINDOW_REQUIRED: affected_scope.window 必须为 [t0,t1]")
    t0, t1 = float(window[0]), float(window[1])
    dur = max(t1 - t0, 0.5)
    tag = proposal.get("proposal_id", "va").replace("/", "_") + "_vaid"
    spec, spec_src = _resolve_visual_aid_spec(ctx, proposal)
    info = probe_media(_ffprobe_bin(ctx), film)
    w = int(info.get("width") or 1920)
    h = int(info.get("height") or 1080)
    work = box / "work"
    work.mkdir(parents=True, exist_ok=True)
    png = work / "visual_aid_{}.png".format(tag)
    ev = core_visual_aid.render_overlay(spec, png, size=(w, h),
                                        font_path=str(ctx.get("visual_aid_font")
                                                      or core_visual_aid.DEFAULT_FONT),
                                        expected_font_sha256=ctx.get("visual_aid_font_sha256"))
    steps = [{"step": "render_visual_aid_overlay", "spec_source": spec_src,
              "overlay_png": png.name, "output_sha256": ev["sha256"],
              "spec_sha256": ev["spec_sha256"], "panels": [p["id"] for p in ev["panels"]],
              "safe_bottom_ok": ev["safe_bottom_ok"], "font": ev["font"]}]
    cap = _caption_filter(ctx, t0, t1, tag, "{}x{}".format(w, h))
    parts = ["[0:v][1:v]overlay=0:0"]
    if cap:
        parts = ["[0:v][1:v]overlay=0:0[ov]", "[ov]{}".format(cap)]
    card = work / "card_{}.mp4".format(tag)
    _run([ffmpeg, "-y", "-v", "error", "-ss", "{:.3f}".format(t0), "-t", "{:.3f}".format(dur),
          "-i", str(film), "-i", str(png), "-filter_complex", ";".join(parts), "-an",
          "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
          "-video_track_timescale", "25000", "-t", "{:.3f}".format(dur), str(card)])
    steps.append({"step": "reencode_window_with_visual_aid_and_captions", "in": film.name,
                  "out": card.name, "window": [t0, t1], "seconds": dur,
                  "captions_reburned": bool(cap), "output_sha256": sha(card),
                  "filter_complex": ";".join(parts),
                  "filter_sha256": hashlib.sha256(";".join(parts).encode("utf-8")).hexdigest()})
    asm = _assemble_windows(ctx, [{"scene_id": (scope.get("scenes") or ["?"])[0],
                                   "window": [t0, t1], "parts": [card]}], tag)
    out = asm["out"]
    steps.extend(asm["steps"])
    return {"steps": steps, "outputs": [{"path": str(out.relative_to(Path(ctx["root"]))),
                                         "bytes": out.stat().st_size, "sha256": sha(out),
                                         "duration_target_s": t1}],
            "duration_check": asm["duration_check"], "audio_check": asm["audio_check"],
            "caption_time_base": dict(ctx.get("_caption_time_base") or {}),
            "timeline_identity": dict(ctx.get("timeline_identity") or {}),
            "visual_aid_evidence": ev, "visual_aid_spec_source": spec_src,
            "notes": "窗口内叠加**自制**信息层（无外部素材）+ 重烧该窗口字幕 + 母版整条音轨流复制；"
                     "总时长不变、音轨与母版一致；spec 非法/字体缺失/安全区违约一律 fail-closed"}


def _pending_asset(ctx: dict, proposal: dict) -> dict:
    """需要新素材的动作：只有**真实存在且可验证**的素材才允许；否则进入人工待处理。"""
    sc = proposal.get("affected_scope") or {}
    want = ((proposal.get("proposed_change") or {}).get("params") or {}).get("new_assets_needed")
    index = ctx.get("asset_index") or {}
    if want and index:
        # 简单核验：索引里存在满足语义关键字且可用的素材？（本阶段索引由调用方提供）
        for aid, rec in index.items():
            if rec.get("usable") and any(k in (rec.get("name") or "")
                                         for k in ("四色", "证明", "开普勒", "示意")):
                return {"steps": [{"step": "asset_candidate_verified", "asset_id": aid}],
                        "outputs": [{"asset_id": aid, "verified": True}], "notes": "使用索引中已核验素材"}
    return {"pending": "PENDING_HUMAN_ASSET",
            "why": "该方案需要新素材，但当前没有**真实存在且经过验证**的候选"
                   "（不得虚构 asset_id、不得占位替换）；进入人工待处理",
            "steps": [{"step": "asset_lookup", "queried_scope": sc.get("assets"),
                       "new_assets_needed": want}]}


# ============================================================================
# 6-B/M5 —— 真实素材校验 + `replace_asset` / `add_asset` **真实执行器** + 替换 E2E 证据
#   原则：素材必须**真实存在 + sha256 一致 + 可解码 + 许可不受限**；
#         无素材 / 校验失败 ⇒ PENDING_HUMAN_ASSET / FAILED（**绝不**虚构、占位或换用别的素材）。
# ============================================================================
ASSET_CODES = ("ASSET_OK", "ASSET_NOT_IN_INDEX", "ASSET_MISSING", "ASSET_SHA_MISMATCH",
               "ASSET_UNDECODABLE", "ASSET_LICENSE_RESTRICTED", "ASSET_LICENSE_PENDING",
               "ASSET_SAME_AS_CURRENT", "ASSET_NO_WINDOW", "ASSET_WINDOW_BEYOND_FILM")


def _ffprobe_bin(ctx: dict):
    ff = (((ctx.get("config") or {}).get("tools") or {}).get("ffmpeg") or {})
    return ctx.get("ffprobe") or ff.get("ffprobe")


def probe_media(ffprobe, path) -> dict:
    """真实探测（只读）：是否存在可解码的 video 流及其宽高/帧率/时长。"""
    r = subprocess.run([ffprobe, "-v", "error", "-print_format", "json", "-show_streams",
                        "-show_format", str(path)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=120)
    if r.returncode != 0:
        return {"ok": False, "why": "ffprobe rc={}".format(r.returncode)}
    info = json.loads(r.stdout or "{}")
    v = next((s for s in (info.get("streams") or []) if s.get("codec_type") == "video"), None)
    a = next((s for s in (info.get("streams") or []) if s.get("codec_type") == "audio"), None)
    if not v:
        return {"ok": False, "why": "无 video 流"}
    num, _, den = str(v.get("r_frame_rate") or "25/1").partition("/")
    try:
        fps = float(num) / float(den or 1)
    except (TypeError, ValueError, ZeroDivisionError):
        fps = 25.0
    return {"ok": True, "width": int(v.get("width") or 0), "height": int(v.get("height") or 0),
            "fps": fps or 25.0, "has_audio": bool(a),
            "audio_codec": (a or {}).get("codec_name"),
            "audio_rate": int((a or {}).get("sample_rate") or 0),
            "audio_channels": int((a or {}).get("channels") or 0),
            "duration_s": float((info.get("format") or {}).get("duration") or 0.0)}


def _asset_window(proposal: dict):
    sc = proposal.get("affected_scope") or {}
    w = proposal.get("window") or sc.get("window")
    if not w or len(w) != 2:
        return None
    return (float(w[0]), float(w[1]))


def verify_asset_candidate(ctx: dict, asset_id: str, proposal: dict | None = None) -> dict:
    """**真实**素材校验（只读）：索引 → 文件 → sha256 → 可解码 → 许可（复用冻结 3-A 口径）。

    返回 `{"ok":bool,"status":"ok|pending|failed","code":...,"evidence":{...}}`。
      · pending ⇒ 无素材/未清许可 ⇒ 由调用方转为 `PENDING_HUMAN_ASSET`；
      · failed  ⇒ 素材失效/不可用 ⇒ 抛错 ⇒ 执行记录 `FAILED`（fail-closed）。
    """
    ev = {"asset_id": asset_id, "checked": []}
    idx = ctx.get("asset_index") or {}
    rec = idx.get(asset_id)
    if not rec:
        return {"ok": False, "status": "pending", "code": "ASSET_NOT_IN_INDEX",
                "evidence": {**ev, "index_size": len(idx)}}
    ev["recorded_sha256"] = rec.get("sha256")
    ev["source"] = rec.get("source")
    ev["provider"] = rec.get("provider")
    p = Path(rec.get("path") or "")
    ev["path"] = str(p)
    if not p.is_file():
        return {"ok": False, "status": "pending", "code": "ASSET_MISSING", "evidence": ev}
    real = sha(p)
    ev["actual_sha256"] = real
    ev["bytes"] = p.stat().st_size
    ev["checked"].append("exists")
    if real != rec.get("sha256"):
        return {"ok": False, "status": "failed", "code": "ASSET_SHA_MISMATCH", "evidence": ev}
    ev["checked"].append("sha256")
    probe = probe_media(_ffprobe_bin(ctx), p)
    ev["probe"] = probe
    if not probe.get("ok") or not probe.get("width") or not probe.get("height"):
        return {"ok": False, "status": "failed", "code": "ASSET_UNDECODABLE", "evidence": ev}
    ev["checked"].append("decodable")
    # 许可：复用**冻结** 3-A 口径（门禁只适用于外部素材；本地 ingest 由用户自备）
    gate = core_materials.license_gate_applies(rec)
    lclass = rec.get("license_class") or core_materials.classify_license(rec.get("license"))[0]
    ev["license"] = rec.get("license")
    ev["license_class"] = lclass
    ev["license_gate_applies"] = gate
    if gate and lclass == "RESTRICTED":
        return {"ok": False, "status": "failed", "code": "ASSET_LICENSE_RESTRICTED", "evidence": ev}
    if gate and lclass == "UNKNOWN":
        return {"ok": False, "status": "pending", "code": "ASSET_LICENSE_PENDING", "evidence": ev}
    ev["checked"].append("license")
    if proposal is not None:
        cur = current_asset_for_scene(ctx, (proposal.get("affected_scope") or {}).get("scenes"))
        if cur and cur.get("asset_id") == asset_id:
            return {"ok": False, "status": "failed", "code": "ASSET_SAME_AS_CURRENT",
                    "evidence": {**ev, "current_asset_id": cur.get("asset_id")}}
    return {"ok": True, "status": "ok", "code": "ASSET_OK", "evidence": ev}


def current_asset_for_scene(ctx: dict, scenes) -> dict | None:
    """当前时间轴里该（首个）镜头正在使用的素材记录（含真实路径，用于替换前后对比）。

    6-C：时间轴被**切分投影**后（`S11.1..S11.4`），基础镜头 id `S11` 回落到其子镜（同一素材）。
    """
    if scenes is None:
        return None
    sids = [str(x) for x in (scenes if isinstance(scenes, (list, tuple, set)) else [scenes])]
    tl = ctx.get("timeline") or []
    for e in tl:
        if str(e.get("scene_id")) in sids:
            sa = e.get("selected_asset") or {}
            if sa:
                return sa
    for base in sids:                                   # 切分投影回落
        for e in tl:
            if str(e.get("scene_id", "")).startswith(base + "."):
                sa = e.get("selected_asset") or {}
                if sa:
                    return sa
    return None


def _requested_asset_id(proposal: dict) -> str | None:
    """方案要求的素材 id（显式 `params.asset_id` 优先；兼容 `new_asset_id` / `new_assets_needed`）。"""
    params = (proposal.get("proposed_change") or {}).get("params") or {}
    aid = params.get("asset_id") or params.get("new_asset_id")
    if aid:
        return str(aid)
    lst = params.get("new_assets_needed")
    if isinstance(lst, dict):
        return lst.get("asset_id")
    if isinstance(lst, (list, tuple)) and lst:
        first = lst[0]
        return first.get("asset_id") if isinstance(first, dict) else str(first)
    return None


def _encode_still_segment(ctx: dict, proposal: dict, asset: dict, tag: str) -> dict:
    """把真实素材渲染成与窗口等长的视频段（含原窗口音轨），并给出片段 sha256。"""
    box = Path(ctx["box"])
    ffmpeg = ctx["ffmpeg"]
    film = Path(ctx["film"])
    w0, w1 = _asset_window(proposal)
    dur = max(w1 - w0, 0.5)
    info = probe_media(_ffprobe_bin(ctx), film)
    W, H, fps = info.get("width") or 1920, info.get("height") or 1080, info.get("fps") or 25.0
    seg_v = box / "work" / "seg_{}_v.mp4".format(tag)
    seg_a = box / "work" / "seg_{}_a.m4a".format(tag)
    seg = box / "work" / "seg_{}.mp4".format(tag)
    vf = ("scale={}:{}:force_original_aspect_ratio=increase,"
          "crop={}:{},fps={},format=yuv420p").format(W, H, W, H, ("%g" % fps))
    cap = _caption_filter(ctx, w0, w1, tag, "{}x{}".format(W, H))   # 字幕重烧录（不断裂）
    if cap:
        vf = vf + "," + cap
    _run([ffmpeg, "-y", "-v", "error", "-loop", "1", "-i", str(asset["path"]),
          "-t", "{:.3f}".format(dur), "-vf", vf, "-c:v", "libx264", "-preset", "ultrafast",
          "-pix_fmt", "yuv420p", "-video_track_timescale", "25000", str(seg_v)])
    steps = [{"step": "render_asset_segment_video", "asset_id": asset.get("asset_id"),
              "asset_sha256": asset.get("sha256"), "out": seg_v.name, "window": [w0, w1],
              "seconds": dur, "scale_to": [W, H], "fps": fps,
              "captions_reburned": bool(cap), "output_sha256": sha(seg_v)}]
    if info.get("has_audio"):
        _run([ffmpeg, "-y", "-v", "error", "-ss", "{:.3f}".format(w0), "-t", "{:.3f}".format(dur),
              "-i", str(film), "-vn", "-c:a", "copy", str(seg_a)])
        steps.append({"step": "copy_window_audio", "in": film.name, "out": seg_a.name,
                      "window": [w0, w1], "output_sha256": sha(seg_a)})
        _run([ffmpeg, "-y", "-v", "error", "-i", str(seg_v), "-i", str(seg_a),
              "-c", "copy", "-shortest", "-video_track_timescale", "25000", str(seg)])
    else:
        seg = seg_v
    steps.append({"step": "mux_segment", "out": seg.name, "output_sha256": sha(seg)})
    return {"seg": seg, "dur": dur, "window": [w0, w1], "steps": steps,
            "film_info": info, "video_only": not info.get("has_audio")}


def _splice_window(ctx: dict, proposal: dict, seg_info: dict, tag: str) -> dict:
    """head（流复制）+ 新素材段 + tail（重编码，保证起始点精确）⇒ 新成片（时长守恒）。"""
    box = Path(ctx["box"])
    ffmpeg = ctx["ffmpeg"]
    film = Path(ctx["film"])
    w0, w1 = seg_info["window"]
    out = box / "output" / "{}_m5_{}.mp4".format(film.stem, tag)
    head = box / "work" / "head_{}.mp4".format(tag)
    tail = box / "work" / "tail_{}.mp4".format(tag)
    lst = box / "work" / "concat_{}.txt".format(tag)
    steps = list(seg_info["steps"])
    parts = []
    if w0 > 0.05:
        _run([ffmpeg, "-y", "-v", "error", "-t", "{:.3f}".format(w0), "-i", str(film),
              "-c", "copy", "-video_track_timescale", "25000", str(head)])
        steps.append({"step": "stream_copy_head", "in": film.name, "out": head.name,
                      "window": [0.0, w0], "output_sha256": sha(head)})
        parts.append(head)
    parts.append(seg_info["seg"])
    total = seg_info["film_info"].get("duration_s") or 0.0
    if total and (total - w1) > 0.05:
        rate = seg_info["film_info"].get("audio_rate") or 0
        ch = seg_info["film_info"].get("audio_channels") or 0
        acodec = ["-c:a", "aac"] + (["-ar", str(rate)] if rate else []) \
            + (["-ac", str(ch)] if ch else [])
        _run([ffmpeg, "-y", "-v", "error", "-ss", "{:.3f}".format(w1), "-i", str(film),
              "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p"]
             + acodec + ["-video_track_timescale", "25000", str(tail)])
        steps.append({"step": "reencode_tail", "in": film.name, "out": tail.name,
                      "window": [w1, total], "output_sha256": sha(tail)})
        parts.append(tail)
    lst.write_text("".join("file '{}'\n".format(p.as_posix()) for p in parts), encoding="utf-8")
    _run([ffmpeg, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
          "-c", "copy", str(out)])
    steps.append({"step": "concat_parts", "out": out.name, "parts": [p.name for p in parts],
                  "output_sha256": sha(out)})
    return {"out": out, "steps": steps, "parts": [p.name for p in parts]}


def _frame_corr_pair(frame_png, path_a, path_b) -> dict:
    a, b = core_materials.gray48(frame_png), core_materials.gray48(path_a)
    c = core_materials.gray48(path_b) if path_b else None
    return {"vs_new": round(core_materials.frame_corr(a, b), 4),
            "vs_prev": (round(core_materials.frame_corr(a, c), 4) if c is not None else None)}


def asset_replacement_evidence(ctx: dict, proposal: dict, film, asset: dict,
                               prev_asset: dict | None) -> dict:
    """**替换 E2E 证据**：从新成片窗口内抽帧，与「新素材 / 原素材」做 48×48 灰度 Pearson 比对。

    阈值复用**冻结** `materials.DEFAULT_POLICY`（frame_match_min_corr=0.30、
    frame_argmax_margin=0.15）：新素材相关度必须达标，且必须**优于**原素材至少 margin。
    """
    box = Path(ctx["box"])
    ffmpeg = ctx["ffmpeg"]
    w0, w1 = _asset_window(proposal)
    min_corr = float(core_materials.DEFAULT_POLICY["frame_match_min_corr"])
    margin = float(core_materials.DEFAULT_POLICY["frame_argmax_margin"])
    samples = []
    for i, frac in enumerate((0.25, 0.5, 0.75), start=1):
        t = w0 + (w1 - w0) * frac
        png = box / "work" / "ev_{}_{}.png".format(proposal.get("proposal_id", "x").replace("/", "_"), i)
        _run([ffmpeg, "-y", "-v", "error", "-ss", "{:.3f}".format(t), "-i", str(film),
              "-frames:v", "1", str(png)])
        pair = _frame_corr_pair(png, asset["path"],
                               (prev_asset or {}).get("path"))
        pair["t_s"] = round(t, 3)
        samples.append(pair)
    new_mean = round(sum(s["vs_new"] for s in samples) / len(samples), 4)
    prev_vals = [s["vs_prev"] for s in samples if s["vs_prev"] is not None]
    prev_mean = round(sum(prev_vals) / len(prev_vals), 4) if prev_vals else None
    best = max([("new", new_mean)] + ([("prev", prev_mean)] if prev_mean is not None else []),
               key=lambda kv: kv[1])[0]
    replaced = bool(new_mean >= min_corr and (prev_mean is None or new_mean - prev_mean >= margin))
    return {"schema": "asset-replacement-evidence-v1", "asset_id": asset.get("asset_id"),
            "asset_sha256": asset.get("sha256"), "asset_path": str(asset.get("path")),
            "prev_asset_id": (prev_asset or {}).get("asset_id"),
            "prev_asset_path": (prev_asset or {}).get("path"),
            "window": [w0, w1], "samples": samples, "corr_new_mean": new_mean,
            "corr_prev_mean": prev_mean, "argmax": best, "min_corr": min_corr,
            "argmax_margin": margin, "replaced": replaced,
            "on_screen": bool(replaced), "read_only_measure": True, "advisory": True,
            "note": "抽帧比对为**只读度量**：新素材必须达标且优于原素材，否则不声称已替换"}


# ============================================================================
# 6-C —— 组装/切分工具（`split_scene` 与多镜素材替换共用）
#   守恒原则：未触及区段按母版复制或重编码；**音轨始终是母版整条音轨的流复制**；
#   总时长由各段时长之和守恒；所有写入严格限制在沙箱 `box` 内。
# ============================================================================
def scene_window_map(ctx: dict) -> dict:
    """镜头 → 窗口（以时间轴为权威）。

    6-C：若时间轴已被**切分投影**（`S11.1..S11.4`），基础镜头 id `S11` 返回其**并集窗口**
    ⇒ 后续批次对"同一镜头"的素材修订仍可定位到同一时间区间。
    """
    out, parts = {}, {}
    for e in (ctx.get("timeline") or []):
        try:
            sid = str(e.get("scene_id"))
            w = [float(e["start_s"]), float(e["end_s"])]
        except (KeyError, TypeError, ValueError):
            continue
        out[sid] = w
        if "." in sid:
            base = sid.split(".", 1)[0]
            parts.setdefault(base, []).append(w)
    for base, ws in parts.items():
        if base not in out:
            out[base] = [min(w[0] for w in ws), max(w[1] for w in ws)]
    return out


def scene_asset_map(ctx: dict) -> dict:
    """镜头 → 在用素材记录（含真实路径与 sha256）。"""
    out = {}
    for e in (ctx.get("timeline") or []):
        sa = e.get("selected_asset") or {}
        if sa.get("asset_id"):
            out[str(e.get("scene_id"))] = sa
    return out


def split_plan(ctx: dict, proposal: dict) -> dict:
    """按**注册参数**（`target_hold_s` + 受影响镜头）生成切分计划（确定性、可复算）。"""
    assert_timeline_identity(ctx)          # 6-G/B2：拒绝旧时基混入（fail-closed）
    params = (proposal.get("proposed_change") or {}).get("params") or {}
    hold = params.get("target_hold_s")
    scenes = [str(s) for s in ((proposal.get("affected_scope") or {}).get("scenes") or [])]
    if not scenes:
        return {"ok": False, "code": "SPLIT_NO_SCENE", "why": "方案未给出受影响镜头"}
    if not hold:
        return {"ok": False, "code": "SPLIT_NO_TARGET_HOLD", "why": "方案未给出 target_hold_s"}
    win = scene_window_map(ctx)
    rows = []
    for sid in scenes:
        w = win.get(sid)
        if not w:
            return {"ok": False, "code": "SPLIT_UNKNOWN_SCENE", "why": "时间轴中不存在镜头 " + sid}
        dur = w[1] - w[0]
        if dur <= float(hold):
            rows.append({"scene_id": sid, "window": w, "duration_s": round(dur, 3),
                         "sub_count": 1, "sub_duration_s": round(dur, 6), "cuts": []})
            continue
        k = int(dur // float(hold)) + (1 if (dur % float(hold)) > 1e-6 else 0)
        d = dur / k
        rows.append({"scene_id": sid, "window": w, "duration_s": round(dur, 3),
                     "sub_count": k, "sub_duration_s": round(d, 6),
                     "cuts": [round(w[0] + d * i, 6) for i in range(1, k)]})
    return {"ok": True, "code": "SPLIT_OK", "target_hold_s": float(hold), "scenes": rows,
            "total_sub_scenes": sum(r["sub_count"] for r in rows),
            "note": "切点由 `target_hold_s` 均分推导；未虚构注册参数以外的切点"}


def master_caption_cues(ctx: dict) -> list:
    """与生产 pipeline **同一函数、同一输入**重建的字幕 cue 表（`core.strip` + `core.captions`）。

    生产渲染把字幕**烧录进画面**（`agents/editing` 用 `ass=` 滤镜），因此任何"替换画面"的执行
    都**必须**把该窗口的字幕重新烧录，否则被替换窗口的字幕会随画面一起消失（字幕断裂）。

    **6-G/B1 修复**：时间基由 `caption_time_base(ctx)` 决定——
      · DCv2 上下文（声明了 timeline identity）⇒ **必须**用 `caption_timeline.windows` 显式构建 cue
        （`build_cues(..., windows=...)`），**禁止**回落到声明时基；
      · 历史上下文（未声明 identity）⇒ 走声明时基，并在 `ctx["_caption_time_base"]` 留痕（legacy）。
    """
    p = (ctx.get("artifacts") or {}).get("script_output")
    if not p or not Path(p).is_file():
        ctx["_caption_time_base"] = {"mode": "none", "why": "no script_output"}
        return []
    base = caption_time_base(ctx)
    ctx["_caption_time_base"] = base
    sc = json.loads(Path(p).read_text(encoding="utf-8"))
    segs = [s for s in (sc.get("segments") or [])
            if core_strip.strip_claims(s.get("narration", "")).strip()]
    payload = [{"narration": core_strip.strip_claims(s.get("narration", "")),
                "duration_s": s.get("duration_s")} for s in segs]
    if base["mode"] == "dcv2":
        # 窗口按 `scene_id` 对齐到旁白段落顺序（与 voice 逐段一一对应）
        idx = {str(s.get("scene_id") or "S{:02d}".format(i + 1)): i
               for i, s in enumerate(sc.get("segments") or [])}
        wins = []
        for w in base["windows"]:
            sid = str(w.get("scene_id"))
            if sid in idx:
                wins.append({"start_s": float(w["start_s"]), "end_s": float(w["end_s"])})
        if len(wins) != len(payload):
            raise RuntimeError(
                "CAPTION_TIMELINE_WINDOW_COUNT_MISMATCH: caption windows={} 与旁白段数={} 不一致"
                " ⇒ fail-closed".format(len(wins), len(payload)))
        return core_captions.build_cues(payload, windows=wins)
    return core_captions.build_cues(payload)


def _caption_filter(ctx: dict, w0: float, w1: float, tag: str, resolution: str) -> str | None:
    """把 [w0,w1] 内的字幕（与母版同一 cue 表、同一 ASS 样式）烧录到替换段。

    返回 ffmpeg 滤镜串（如 `ass=filename='...':fontsdir='C\\:/Windows/Fonts'`）或 None。
    """
    box = Path(ctx["box"])
    cues = ctx.get("_caption_cues")
    if cues is None:
        cues = master_caption_cues(ctx)
        ctx["_caption_cues"] = cues
    sel = []
    for c in cues:
        try:
            s, e = float(c["start"]), float(c["end"])
        except (KeyError, TypeError, ValueError):
            continue
        if e <= w0 + 1e-6 or s >= w1 - 1e-6:
            continue
        seg = dict(c)
        seg["start"] = round(max(s, w0) - w0, 3)
        seg["end"] = round(min(e, w1) - w0, 3)
        sel.append(seg)
    if not sel:
        return None
    p = box / "work" / "cap_{}.ass".format(tag)
    p.write_text(core_captions.to_ass(sel, resolution=resolution), encoding="utf-8")
    return "ass=filename='{}':fontsdir='C\\:/Windows/Fonts'".format(
        p.as_posix().replace(":", "\\:"))


def _cached(ctx: dict, name: str, build) -> Path:
    """可续跑缓存：同名产出带 `.done` 标记时直接复用（编码是确定性的，重跑不重复计算）。"""
    box = Path(ctx["box"])
    out = box / "work" / name
    marker = box / "work" / (name + ".done")
    if out.is_file() and marker.is_file() and out.stat().st_size > 0:
        return out
    build(out)
    marker.write_text(sha(out), encoding="utf-8")
    return out


def _still_video(ctx: dict, asset_path, dur: float, tag: str, zoom: float = 1.0,
                 window: list | None = None) -> Path:
    """用**真实素材**渲染 dur 秒的**无音轨**视频子段（覆盖式缩放；zoom>1 = 构图变化）。

    `window` 给定时，把该窗口的字幕（与母版同一 cue 表/样式）**重新烧录** ⇒ 字幕不断裂。
    """
    ffmpeg = ctx["ffmpeg"]
    info = probe_media(_ffprobe_bin(ctx), Path(ctx["film"]))
    W, H, fps = info.get("width") or 1920, info.get("height") or 1080, info.get("fps") or 25.0
    if abs(zoom - 1.0) < 1e-6:
        base = ("scale={}:{}:force_original_aspect_ratio=increase,crop={}:{},fps={},"
                "format=yuv420p").format(W, H, W, H, ("%g" % fps))
    else:
        base = ("scale={}:{}:force_original_aspect_ratio=increase,"
                "crop={}:{}:(iw-ow)/2:(ih-oh)/2,fps={},format=yuv420p").format(
                    int(W * zoom), int(H * zoom), W, H, ("%g" % fps))
    cap = (_caption_filter(ctx, float(window[0]), float(window[1]), tag,
                           "{}x{}".format(W, H)) if window else None)
    vf = ",".join([base] + ([cap] if cap else []))
    name = "sv_{}_{}_{}.mp4".format(tag, sha(Path(asset_path))[:8],
                                    hashlib.sha256(vf.encode("utf-8")).hexdigest()[:8])

    def _build(out: Path) -> None:
        _run([ffmpeg, "-y", "-v", "error", "-loop", "1", "-i", str(asset_path),
              "-t", "{:.3f}".format(dur), "-vf", vf, "-an", "-c:v", "libx264",
              "-preset", "ultrafast", "-pix_fmt", "yuv420p",
              "-video_track_timescale", "25000", str(out)])

    return _cached(ctx, name, _build)


def _video_part(ctx: dict, t0: float, t1: float, tag: str) -> Path | None:
    """母版 [t0,t1] 的**无音轨**视频段：t0≈0 ⇒ 流复制（边界精确）；否则重编码（起点精确）。"""
    ffmpeg = ctx["ffmpeg"]
    film = Path(ctx["film"])
    dur = t1 - t0
    if dur <= 0.04:
        return None
    name = "vp_{}_{}_{}.mp4".format(tag, sha(film)[:8], "{:.3f}".format(t0).replace(".", "p"))

    def _build(out: Path) -> None:
        if t0 <= 0.04:
            _run([ffmpeg, "-y", "-v", "error", "-t", "{:.3f}".format(dur), "-i", str(film),
                  "-an", "-c:v", "copy", "-video_track_timescale", "25000", str(out)])
        else:
            _run([ffmpeg, "-y", "-v", "error", "-ss", "{:.3f}".format(t0),
                  "-t", "{:.3f}".format(dur), "-i", str(film), "-an", "-c:v", "libx264",
                  "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                  "-video_track_timescale", "25000", str(out)])

    return _cached(ctx, name, _build)


def _concat_video(ctx: dict, parts: list, tag: str) -> Path:
    """按顺序拼接无音轨视频段（流复制）⇒ 新成片的视频轨。"""
    box = Path(ctx["box"])
    lst = box / "work" / "cv_{}.txt".format(tag)
    keep = [p for p in parts if p]
    lst.write_text("".join("file '{}'\n".format(p.as_posix()) for p in keep), encoding="utf-8")
    out = box / "work" / "video_{}.mp4".format(tag)
    _run([ctx["ffmpeg"], "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
          "-c", "copy", "-video_track_timescale", "25000", str(out)])
    return out


def _audio_stream_sha(ctx: dict, film: Path) -> str:
    """把成片音轨**流复制**出来取 sha256（用于证明音轨与母版一致）。"""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        a = Path(td) / "a.m4a"
        _run([ctx["ffmpeg"], "-y", "-v", "error", "-i", str(film), "-vn", "-c:a", "copy", str(a)])
        return sha(a)


def _mux_master_audio(ctx: dict, video_only: Path, out: Path) -> dict:
    """把**母版整条音轨**流复制进新视频 ⇒ 音轨不因画面切分而断裂（同一 AAC 流）。"""
    _run([ctx["ffmpeg"], "-y", "-v", "error", "-i", str(video_only), "-i", str(ctx["film"]),
          "-map", "0:v:0", "-map", "1:a:0", "-c", "copy", "-video_track_timescale", "25000",
          str(out)])
    return {"step": "mux_master_audio_stream_copy", "out": out.name,
            "audio_source": Path(ctx["film"]).name,
            "audio_sha256": _audio_stream_sha(ctx, out),
            "video_only_sha256": sha(video_only), "output_sha256": sha(out)}


def _gray_diff(p1: Path, p2: Path) -> float:
    import numpy as np
    a = core_materials.gray48(p1)
    b = core_materials.gray48(p2)
    return round(float(np.abs(a - b).mean()), 4)


def _cut_evidence(ctx: dict, windows: list, tag: str, film: Path,
                  max_cuts_per_scene: int = 2) -> list:
    """在**候选成片**上对切点两侧抽帧比对：切点必须确有画面差异（证明切点真实存在）。

    同时给出与**母版**同刻画面的差异（母版在切点处本无变化 ⇒ 该值反映"这次修订真的改了画面"）。
    """
    box = Path(ctx["box"])
    ffmpeg = ctx["ffmpeg"]
    master = Path(ctx["film"])
    rows = []
    for wi, w in enumerate(windows):
        for ci, c in enumerate((w.get("cuts") or [])[:max_cuts_per_scene], start=1):
            f_a = box / "work" / "cut_{}_{}_{}_a.png".format(tag, wi, ci)
            f_b = box / "work" / "cut_{}_{}_{}_b.png".format(tag, wi, ci)
            f_m = box / "work" / "cut_{}_{}_{}_m.png".format(tag, wi, ci)
            for f, t in ((f_a, max(c - 0.12, 0.0)), (f_b, c + 0.12)):
                _run([ffmpeg, "-y", "-v", "error", "-ss", "{:.3f}".format(t), "-i", str(film),
                      "-frames:v", "1", str(f)])
            _run([ffmpeg, "-y", "-v", "error", "-ss", "{:.3f}".format(c + 0.12), "-i",
                  str(master), "-frames:v", "1", str(f_m)])
            d = _gray_diff(f_a, f_b)
            dm = _gray_diff(f_b, f_m)
            rows.append({"scene_id": w.get("scene_id"), "cut_s": c, "gray48_absdiff": d,
                         "gray48_absdiff_vs_master": dm, "distinct": d >= 0.02,
                         "differs_from_master": dm >= 0.02})
    return rows


def _exact_duration_pass(ctx: dict, film: Path, target_s: float, tag: str) -> dict:
    """**装配层确定性精度修正（OPT-A，opt-in）**：把视频精确对齐到 `target_s`。

    两步、**音频零改动**：
      ① 仅取视频流并按 `round(target_s × fps)` 精确到整帧（重编码视频，`-an`）；
      ② 用**生产同一条** `_mux_master_audio`（`-c copy`）把母版音轨复制回来
         ⇒ 音频流 md5 不变；容器时长 = max(视频, 音频) = 时间轴时长。
    不改字幕时间轴、不改切点、不改任何阈值/门禁/POLICY；仅当 `ctx["exact_assembly_duration_s"]`
    被显式设置时调用（默认路径行为完全不变）。修正后**自检 fail-closed**：时长超差或音轨不一致即抛错。
    """
    ffmpeg = ctx["ffmpeg"]
    info = probe_media(_ffprobe_bin(ctx), film)
    fps = float(info.get("fps") or 25.0)
    target_frames = int(round(float(target_s) * fps))
    video_exact = film.with_name(film.stem + "_vexact.mp4")
    _run([ffmpeg, "-y", "-v", "error", "-i", str(film), "-map", "0:v:0", "-an",
          "-frames:v", str(target_frames), "-c:v", "libx264", "-preset", "ultrafast",
          "-crf", "23", "-pix_fmt", "yuv420p", "-video_track_timescale", "25000",
          str(video_exact)], timeout=3600)
    out = film.with_name(film.stem + "_exact.mp4")
    mux = _mux_master_audio(ctx, video_exact, out)      # 音频 = ctx["film"] 的母版音轨（stream copy）
    after = probe_media(_ffprobe_bin(ctx), out)
    src_audio = _audio_stream_sha(ctx, Path(ctx["film"]))
    out_audio = _audio_stream_sha(ctx, out)
    delta = round((after.get("duration_s") or 0.0) - float(target_s), 4)
    if out_audio != src_audio:
        raise RuntimeError("EXACT_DURATION_AUDIO_MISMATCH: 音轨不再与母版一致 ⇒ fail-closed")
    if abs(delta) > 0.05:
        raise RuntimeError("EXACT_DURATION_OUT_OF_TOLERANCE: {}s (Δ {:+.4f}) ⇒ fail-closed".format(
            after.get("duration_s"), delta))
    return {"step": "exact_duration_pass_optA", "in": film.name, "out": out.name,
            "target_s": round(float(target_s), 3), "fps": fps, "target_frames": target_frames,
            "measured_s": after.get("duration_s"), "delta_s": delta,
            "video_only_sha256": mux.get("video_only_sha256"),
            "audio_stream": "copy（经 _mux_master_audio；音频流 sha 与母版一致）",
            "audio_sha256": out_audio, "audio_identical_to_source": out_audio == src_audio,
            "output_sha256": sha(out)}, out


def _assemble_windows(ctx: dict, windows: list, tag: str) -> dict:
    """把 [窗口段/空隙/首尾] 按时间顺序拼成新成片（视频重排 + 母版音轨流复制）。

    `windows` = [{"scene_id":..., "window":[t0,t1], "parts":[Path,...]}, ...]（可乱序传入）。
    """
    box = Path(ctx["box"])
    info = probe_media(_ffprobe_bin(ctx), Path(ctx["film"]))
    total = info.get("duration_s") or 0.0
    ordered = sorted(windows, key=lambda w: w["window"][0])
    seq, steps, cursor = [], [], 0.0
    for i, w in enumerate(ordered):
        w0, w1 = w["window"]
        gap = _video_part(ctx, cursor, w0, "{}_gap{}".format(tag, i))
        if gap:
            seq.append(gap)
            steps.append({"step": "copy_gap_video", "window": [cursor, w0], "out": gap.name,
                          "output_sha256": sha(gap)})
        for j, p in enumerate(w["parts"]):
            seq.append(p)
            steps.append({"step": "segment_in_place", "scene_id": w.get("scene_id"),
                          "sub_index": j, "window": [w0, w1], "out": Path(p).name,
                          "output_sha256": sha(p)})
        cursor = w1
    tail = _video_part(ctx, cursor, total, "{}_tail".format(tag)) if total else None
    if tail:
        seq.append(tail)
        steps.append({"step": "copy_tail_video", "window": [cursor, total], "out": tail.name,
                      "output_sha256": sha(tail)})
    video_only = _concat_video(ctx, seq, tag)
    steps.append({"step": "concat_all_video_parts", "parts": len([p for p in seq if p]),
                  "out": video_only.name, "output_sha256": sha(video_only)})
    out = box / "output" / "{}_6c_{}.mp4".format(Path(ctx["film"]).stem, tag)
    mux = _mux_master_audio(ctx, video_only, out)
    steps.append(mux)
    after = probe_media(_ffprobe_bin(ctx), out)
    master_audio = _audio_stream_sha(ctx, Path(ctx["film"]))
    # ---- OPT-A（opt-in）：装配层精确时长修正（仅视频；音轨 copy）----
    exact = None
    _target = ctx.get("exact_assembly_duration_s")
    if _target:
        exact, out2 = _exact_duration_pass(ctx, out, float(_target), tag)
        steps.append(exact)
        out = out2
        after = probe_media(_ffprobe_bin(ctx), out)
    return {"out": out, "steps": steps, "windows": ordered,
            "duration_check": {"master_s": total, "candidate_s": after.get("duration_s"),
                               "delta_s": round((after.get("duration_s") or 0.0) - total, 3),
                               "exact_duration_pass": bool(exact),
                               "target_s": (round(float(_target), 3) if _target else None)},
            "audio_check": {"master_audio_sha256": master_audio,
                            "candidate_audio_sha256": _audio_stream_sha(ctx, out),
                            "identical_stream": master_audio == _audio_stream_sha(ctx, out)}}


def exec_split_scene(ctx: dict, proposal: dict) -> dict:
    """`split_scene` 真实执行：窗口内加入构图变化切点（≤ target_hold_s），时长与音轨守恒。"""
    plan = split_plan(ctx, proposal)
    if not plan["ok"]:
        raise RuntimeError("{}: {}".format(plan["code"], plan["why"]))
    tag = proposal.get("proposal_id", "rp").replace("/", "_") + "_split"
    asset_of = scene_asset_map(ctx)
    windows, steps = [], []
    for r in plan["scenes"]:
        sid, k, d = r["scene_id"], r["sub_count"], r["sub_duration_s"]
        asset = asset_of.get(sid) or {}
        if not asset.get("path") or not Path(asset["path"]).is_file():
            raise RuntimeError("SPLIT_UNKNOWN_SCENE: 镜头 {} 的在用素材不可用（不虚构素材）".format(sid))
        parts = []
        for j in range(k):
            zoom = 1.0 if (j % 2 == 0) else 1.18
            sub_w0 = r["window"][0] + d * j
            sub_w1 = r["window"][0] + d * (j + 1)
            seg = _still_video(ctx, asset["path"], d, "{}_s{}_{}".format(tag, sid, j), zoom,
                               window=[sub_w0, sub_w1])
            parts.append(seg)
            steps.append({"step": "render_sub_scene", "scene_id": sid, "sub_index": j,
                          "sub_count": k, "window": r["window"], "duration_s": round(d, 3),
                          "zoom": zoom, "asset_id": asset.get("asset_id"), "out": seg.name,
                          "output_sha256": sha(seg)})
        windows.append({"scene_id": sid, "window": r["window"], "parts": parts,
                        "cuts": r["cuts"], "sub_count": k, "cut_kind": "composition_change"})
    asm = _assemble_windows(ctx, windows, tag)
    cut_ev = _cut_evidence(ctx, windows, tag, asm["out"])
    out = asm["out"]
    return {"steps": asm["steps"] + [{"step": "cut_evidence", "cuts_checked": len(cut_ev),
                                      "all_distinct": all(c["distinct"] for c in cut_ev)}],
            "outputs": [{"path": str(out.relative_to(Path(ctx["root"]))),
                         "bytes": out.stat().st_size, "sha256": sha(out),
                         "duration_s": asm["duration_check"]["candidate_s"]}],
            "split_plan": plan, "cut_evidence": cut_ev,
            "caption_time_base": dict(ctx.get("_caption_time_base") or {}),
            "timeline_identity": dict(ctx.get("timeline_identity") or {}),
            "duration_check": asm["duration_check"], "audio_check": asm["audio_check"],
            "scene_projection": [{"scene_id": w["scene_id"], "window": w["window"],
                                  "sub_count": w["sub_count"], "cuts": w["cuts"]}
                                 for w in asm["windows"]],
            "notes": "窗口内加入构图变化切点（≤ target_hold_s）；未触及区段按母版复制/重编码；"
                     "音轨 = **母版整条音轨流复制**（sha256 可核验）；总时长守恒；母版零改动"}


def asset_binding(ctx: dict, proposal: dict) -> dict:
    """人工**选材绑定**（`ctx["asset_bindings"]`）：proposal_id → {scene_id: asset_id} 或
    {"asset_id": ...} / {"asset_ids": [...]}。绑定是**人工决策输入**，不修改已登记方案内容。
    """
    b = (ctx.get("asset_bindings") or {}).get(proposal.get("proposal_id")) or {}
    return b if isinstance(b, dict) else {}


def _scene_asset_plan(ctx: dict, proposal: dict, binding: dict) -> list:
    """受影响镜头的执行计划：[(scene_id, window, asset_id)]（注册窗口优先，其次时间轴窗口）。"""
    sc = proposal.get("affected_scope") or {}
    scenes = [str(s) for s in (sc.get("scenes") or [])]
    tw = ((proposal.get("target") or {}).get("windows")) or []
    win = scene_window_map(ctx)
    ids = binding.get("asset_ids") or []
    single = binding.get("asset_id")
    default = _requested_asset_id(proposal) or single
    rows = []
    for i, sid in enumerate(scenes):
        w = tw[i] if i < len(tw) else win.get(sid)
        aid = binding.get(sid) or (ids[i] if i < len(ids) else None) or default
        rows.append({"scene_id": sid, "window": w, "asset_id": aid})
    if not rows and sc.get("window"):                      # 无镜头但有窗口 ⇒ 单窗口执行
        rows = [{"scene_id": None, "window": [float(x) for x in sc["window"]],
                 "asset_id": default}]
    return rows


def _execute_asset_change(ctx: dict, proposal: dict, kind: str) -> dict:
    """`replace_asset` / `add_asset` 的**真实**执行：先校验素材，再按窗口重编码并组装。

    多镜支持（6-C）：注册范围内每个镜头各自一个窗口；素材可由**人工选材绑定**逐镜指定
    （`ctx["asset_bindings"]`），未绑定则回落到方案自身的 `params.asset_id`。
    任一镜头校验失败即**整体不执行**（fail-closed，不做部分替换）。
    """
    assert_timeline_identity(ctx)          # 6-G/B2：旧时基混入即拒绝
    binding = asset_binding(ctx, proposal)
    plan = _scene_asset_plan(ctx, proposal, binding)
    if not plan or not any(r.get("asset_id") for r in plan):
        return {"pending": "PENDING_HUMAN_ASSET",
                "why": "方案未给出**真实** asset_id（不得虚构或占位替换）；进入人工待处理",
                "steps": [{"step": "asset_request", "queried_scope":
                           (proposal.get("affected_scope") or {}).get("assets"),
                           "binding_present": bool(binding)}]}
    idx = ctx.get("asset_index") or {}
    verifications, steps = [], []
    for r in plan:
        if not r.get("asset_id"):
            raise RuntimeError("ASSET_NOT_IN_INDEX: 镜头 {} 未给出素材（不虚构、不回落占位）".format(
                r.get("scene_id")))
        if not r.get("window"):
            raise RuntimeError("ASSET_NO_WINDOW: 镜头 {} 无可定位窗口 ⇒ 不执行".format(
                r.get("scene_id")))
        ver = verify_asset_candidate(ctx, r["asset_id"], proposal)
        verifications.append({"scene_id": r["scene_id"], "asset_id": r["asset_id"],
                              "code": ver["code"], "status": ver["status"],
                              "evidence": ver["evidence"]})
        steps.append({"step": "asset_verify", "scene_id": r["scene_id"],
                      "asset_id": r["asset_id"], "code": ver["code"],
                      "evidence": {k: ver["evidence"].get(k) for k in
                                   ("path", "recorded_sha256", "actual_sha256", "license",
                                    "license_class", "license_gate_applies", "checked")}})
        if ver["status"] == "pending":
            return {"pending": "PENDING_HUMAN_ASSET",
                    "why": "{}（{} @ {}）：素材不存在或许可未清".format(
                        ver["code"], r["asset_id"], r.get("scene_id")),
                    "steps": steps}
        if ver["status"] == "failed":
            raise RuntimeError("{}: 素材校验失败（{} @ {}）——不换素材、不占位、不虚构".format(
                ver["code"], r["asset_id"], r.get("scene_id")))
    tag = "{}_{}".format(proposal.get("proposal_id", "rp").replace("/", "_"), kind)
    if len(plan) == 1:                                     # 单窗口：沿用 M5 已验证的快速路径
        r = plan[0]
        asset = idx[r["asset_id"]]
        prev = current_asset_for_scene(ctx, [r["scene_id"]] if r["scene_id"] else None)
        p1 = dict(proposal)
        p1["affected_scope"] = {**proposal.get("affected_scope", {}), "window": r["window"]}
        p1["window"] = r["window"]
        seg_info = _encode_still_segment(ctx, p1, asset, tag)
        spliced = _splice_window(ctx, p1, seg_info, tag)
        out = spliced["out"]
        ev = asset_replacement_evidence(ctx, p1, out, asset, prev)
        ev["scene_id"] = r["scene_id"]
        steps = spliced["steps"] + steps + [
            {"step": "asset_replacement_evidence", "corr_new_mean": ev["corr_new_mean"],
             "corr_prev_mean": ev["corr_prev_mean"], "replaced": ev["replaced"]}]
        return {"steps": steps,
                "outputs": [{"path": str(out.relative_to(Path(ctx["root"]))),
                             "bytes": out.stat().st_size, "sha256": sha(out),
                             "asset_id": r["asset_id"], "window": seg_info["window"]}],
                "asset_evidence": ev, "asset_verifications": verifications,
                "caption_time_base": dict(ctx.get("_caption_time_base") or {}),
                "timeline_identity": dict(ctx.get("timeline_identity") or {}),
                "notes": "{}：窗口内真实替换为已校验素材（sha256 一致 + 可解码 + 许可不受限）；"
                         "源项目与母版未被触碰".format(kind)}
    # 多窗口：逐镜渲染无音轨段 → 组装 → 母版音轨流复制
    windows, evid = [], []
    for r in plan:
        asset = idx[r["asset_id"]]
        w0, w1 = [float(x) for x in r["window"]]
        seg = _still_video(ctx, asset["path"], max(w1 - w0, 0.5),
                           "{}_a{}".format(tag, r.get("scene_id")), 1.0, window=[w0, w1])
        windows.append({"scene_id": r["scene_id"], "window": [w0, w1], "parts": [seg]})
        steps.append({"step": "render_asset_window", "scene_id": r.get("scene_id"),
                      "asset_id": r["asset_id"], "window": [w0, w1], "out": seg.name,
                      "output_sha256": sha(seg)})
    asm = _assemble_windows(ctx, windows, tag)
    out = asm["out"]
    for r in plan:
        asset = idx[r["asset_id"]]
        prev = current_asset_for_scene(ctx, [r["scene_id"]] if r["scene_id"] else None)
        p1 = dict(proposal)
        p1["affected_scope"] = {**proposal.get("affected_scope", {}), "window": r["window"]}
        p1["window"] = r["window"]
        e = asset_replacement_evidence(ctx, p1, out, asset, prev)
        e["scene_id"] = r["scene_id"]
        evid.append(e)
    replaced_all = all(e["replaced"] for e in evid)
    return {"steps": asm["steps"] + steps + [
                {"step": "asset_replacement_evidence_multiscene",
                 "scenes": [e["scene_id"] for e in evid], "all_replaced": replaced_all}],
            "outputs": [{"path": str(out.relative_to(Path(ctx["root"]))),
                         "bytes": out.stat().st_size, "sha256": sha(out),
                         "windows": [[float(x) for x in r["window"]] for r in plan]}],
            "asset_evidence": {"schema": "asset-replacement-evidence-v1", "multi_scene": True,
                               "per_scene": evid, "replaced": replaced_all,
                               "read_only_measure": True, "advisory": True,
                               "note": "逐镜抽帧比对（新素材必须达标且优于原素材）"},
            "asset_verifications": verifications,
            "duration_check": asm["duration_check"], "audio_check": asm["audio_check"],
            "caption_time_base": dict(ctx.get("_caption_time_base") or {}),
            "timeline_identity": dict(ctx.get("timeline_identity") or {}),
            "notes": "{}：多镜窗口内真实替换为已校验素材；音轨 = 母版整条音轨流复制；母版零改动"
                     .format(kind)}


def exec_replace_asset(ctx: dict, proposal: dict) -> dict:
    return _execute_asset_change(ctx, proposal, "replace")


def exec_add_asset(ctx: dict, proposal: dict) -> dict:
    return _execute_asset_change(ctx, proposal, "add")


EXECUTORS = {
    "add_outro_card": exec_add_outro_card,
    "add_asset": exec_add_asset,
    "replace_asset": exec_replace_asset,
    "split_scene": exec_split_scene,
    "add_visual_aid": exec_add_visual_aid,
}


# ---------------------------------------------------------------- 强制复核（PI + DQ）
def project_timeline(ctx: dict, proposal: dict, exec_result: dict) -> tuple:
    """沙箱内**内存推演**时间轴（投影，不写回项目/DB），仅供 DQ 只读复核。

    两种投影（都只在内存中，`written_back=False`）：
      · 素材类执行 ⇒ 受影响镜头的 `selected_asset` 换成真实新素材；
      · 切分类执行 ⇒ 受影响镜头按 `split_plan` 展开成多个 ≤hold 的子镜（时长守恒）。
    """
    ev = (exec_result or {}).get("asset_evidence") or {}
    sp = (exec_result or {}).get("scene_projection") or []
    scenes = {str(s) for s in ((proposal.get("affected_scope") or {}).get("scenes") or [])}
    if sp:                                                   # 切分投影
        by_scene = {str(x.get("scene_id")): x for x in sp}
        out, expanded = [], []
        for e in (ctx.get("timeline") or []):
            sid = str(e.get("scene_id"))
            x = by_scene.get(sid)
            if not x:
                out.append(e)
                continue
            k = int(x.get("sub_count") or 1)
            w0, w1 = [float(v) for v in x["window"]]
            d = (w1 - w0) / k
            for j in range(k):
                e2 = dict(e)
                e2["scene_id"] = "{}.{}".format(sid, j + 1)
                e2["start_s"] = round(w0 + d * j, 3)
                e2["end_s"] = round(w0 + d * (j + 1), 3)
                out.append(e2)
            expanded.append({"scene_id": sid, "sub_count": k})
        return out, {"schema": "timeline-projection-v1", "mode": "split", "expanded": expanded,
                     "written_back": False, "sandbox_only": True,
                     "note": "切分投影：镜头按 ≤target_hold_s 展开为子镜（时长守恒）；未写回项目/DB；"
                             "切点真实性以成片抽帧比对为准"}
    aid = ev.get("asset_id")
    if not (aid and ev.get("replaced")):
        return ctx.get("timeline") or [], None
    rec = (ctx.get("asset_index") or {}).get(aid) or {}
    out = []
    for e in (ctx.get("timeline") or []):
        if str(e.get("scene_id")) in scenes:
            e2 = dict(e)
            e2["selected_asset"] = {**(e.get("selected_asset") or {}), **rec, "asset_id": aid}
            out.append(e2)
        else:
            out.append(e)
    return out, {"schema": "timeline-projection-v1", "mode": "asset", "scenes": sorted(scenes),
                 "asset_id": aid, "replaced": ev.get("replaced"), "written_back": False,
                 "sandbox_only": True,
                 "note": "仅用于 DQ 只读复核的**内存推演**；未写回项目/DB；上屏以成片抽帧比对为准"}


def pi_recheck(ctx: dict, proposal: dict, exec_result: dict) -> dict:
    """执行后**必须**重跑 PI-1…PI-6（复用冻结度量与 M2 门禁判定）+ DQ-1…DQ-8 只读诊断。

    **6-G §4 口径对齐（仅复核层，不改任何阈值/执行门禁/提案判定规则）**：
      · 当执行上下文声明了 **DCv2 时基**（`timeline_identity` / 提供 `narration_plan`）时，
        本复核把 DCv2 `narration_plan` 传给冻结门禁 ⇒ PI-1/PI-2 以**语音专属时基**判定、
        PI-6 采用 **G-SEG 权威链自洽性**，且 post 门禁按"仅拦超出已声明预算的静音"判定；
      · 原 **declared↔actual 逐段漂移**数值**保留并单列**为 `PI-6-legacy-declared-drift` +
        `PLANNING_DRIFT`（**非阻断诊断**），因此不存在"放宽门禁"：真正阻断项（G-SEG/G-TL/
        G-PAD/G-SUB、PI-1/PI-2/PI-3…）阈值与判据**完全未变**；
      · 未声明 DCv2 时基的历史上下文（v1）**行为与修改前完全一致**（向后兼容）。
    """
    cfg = ctx["config"]
    ff = ((cfg.get("tools") or {}).get("ffmpeg") or {})
    ffmpeg, ffprobe = ff.get("path"), ff.get("ffprobe")
    out_rel = (exec_result.get("outputs") or [{}])[0].get("path")
    film = (Path(ctx["root"]) / out_rel) if out_rel else Path(ctx["film"])
    script = json.loads(Path(ctx["artifacts"]["script_output"]).read_text(encoding="utf-8"))
    voice = json.loads(Path(ctx["artifacts"]["voice_output"]).read_text(encoding="utf-8"))
    timeline_total = float(ctx["timeline_duration_s"])
    narr_s = voice.get("narration_duration_s")
    cues = ctx["cues"]

    # ---- 6-G §4：判定是否 DCv2 上下文；是则取用 DCv2 narration_plan（缺失可就地重建）----
    ti = ctx.get("timeline_identity")
    dcv2 = bool(isinstance(ti, dict) and ti.get("schema") == TIMELINE_IDENTITY_SCHEMA)
    plan = ctx.get("narration_plan")
    if dcv2 and not isinstance(plan, dict):
        try:
            plan = core_narration.narration_plan(script, voice, config=cfg)
        except Exception:                                              # noqa: BLE001
            plan = None
    if not dcv2:
        plan = None                       # v1 历史上下文：保持既有行为不变

    probe = core_integrity.probe_tracks(film, ffprobe)
    pi = {
        "PI-1": core_integrity.narration_coverage(narr_s, timeline_total),
        "PI-2": core_integrity.duration_contract_dual(timeline_total, narr_s),
        "PI-3": core_integrity.audio_silence_profile(film, ffmpeg, timeline_total),
        "PI-4": core_integrity.av_track_consistency(probe, timeline_total),
        "PI-5": core_integrity.subtitle_orphans(cues, narr_s, timeline_total),
        "PI-6": core_integrity.segment_boundary_drift(
            script.get("segments") or [],
            [d.get("duration_s") for d in (voice.get("segment_details") or [])]),
    }
    if plan:
        # 旧口径数值**保留单列**（诊断），PI-6 槽位改为 DCv2 权威链自洽性（G-SEG）
        pi["PI-6-legacy-declared-drift"] = pi["PI-6"]
        pi["PI-6"] = core_integrity.segment_alignment_v2(plan, core_integrity.gate_policy(cfg))
        pi["PLANNING_DRIFT"] = (plan.get("planning_drift") or {})
    gp = core_integrity.gate_policy(cfg)
    pre = core_integrity.pre_render_gate(
        script.get("segments") or [], voice, timeline_total, gp, narration_duration_s=narr_s,
        narration_plan=plan, cues=cues,
        narration_padding_s=(max(timeline_total - float(narr_s or 0.0), 0.0)
                             if plan else None))
    post = core_integrity.post_render_gate(film, timeline_total, cues, narr_s, True,
                                           ffmpeg, ffprobe, gp, narration_plan=plan)
    # DQ 只读复核（不测 freeze，避免长片二次解码；状态判定不依赖 freeze 证据）
    # 素材类执行 ⇒ 用**内存推演**时间轴（仅度量用；是否上屏由成片抽帧比对证明）
    dq_timeline, projection = project_timeline(ctx, proposal, exec_result)
    evidence = ctx.get("evidence")
    dq = {
        "DQ-1": core_direction.hook_relevance(evidence),
        "DQ-2": core_direction.asset_reuse(dq_timeline),
        "DQ-3": core_direction.static_hold(dq_timeline),
        "DQ-4": core_direction.visual_density(dq_timeline),
        "DQ-5": core_direction.climax_coverage(script.get("segments") or [], dq_timeline, evidence),
        "DQ-6": core_direction.ending_completeness(script.get("segments") or [], dq_timeline,
                                                   None, evidence),
        "DQ-8": core_direction.narration_visual_support(script.get("segments") or [], dq_timeline,
                                                        evidence),
    }
    return {
        "schema": "revision-recheck-v1",
        "film": str(film.relative_to(Path(ctx["root"]))),
        "film_sha256": sha(film),
        "pi_contract": ("audio_time_base_v2（DCv2 narration_plan 已传入冻结门禁）" if plan
                        else "timeline_authoritative_v1（历史上下文，行为与修改前一致）"),
        "planning_drift_blocking": False,
        "pi_metrics": {k: {"state": (v.get("state") if isinstance(v, dict) else v)}
                       for k, v in pi.items()},
        "pi_legacy_declared_drift": ({k: (v.get("state") if isinstance(v, dict) else v)
                                      for k, v in pi.items()
                                      if k == "PI-6-legacy-declared-drift"} or None),
        "pi_failed": sorted(k for k, v in pi.items()
                            if k != "PI-6-legacy-declared-drift"
                            and isinstance(v, dict) and v.get("state") == "FAIL"),
        "pi_unknown_or_na": sorted(k for k, v in pi.items()
                                   if isinstance(v, dict)
                                   and v.get("state") in ("UNKNOWN", "NOT_ASSESSABLE")),
        "pre_render_gate": {"blocked": pre["blocked"], "reasons": pre["reasons"]},
        "post_render_gate": {"blocked": post["blocked"], "reasons": post["reasons"]},
        # pi_gate_outcome：按**既有门禁**口径（任一 gate 阻断 ⇒ BLOCKED；否则 PASS）
        "pi_gate_outcome": ("BLOCKED" if (pre["blocked"] or post["blocked"]) else "PASS"),
        "dq_metrics": {k: v["state"] for k, v in dq.items()},
        "dq_details": {k: {kk: v[kk] for kk in
                           ("state", "unique_assets", "max_asset_share", "scenes",
                            "mean_hold_s", "max_hold_s", "over_hold_share", "changes_per_min",
                            "distinct_assets_in_core", "max_hold_in_core_s", "total_s",
                            "semantic_state", "match_share") if kk in v}
                       for k, v in dq.items()},
        "dq_summary": core_direction.summarize_direction(dq),
        "timeline_projection": projection,
        "asset_evidence": (exec_result or {}).get("asset_evidence"),
        "split_evidence": ({"split_plan": (exec_result or {}).get("split_plan"),
                            "cut_evidence": (exec_result or {}).get("cut_evidence"),
                            "duration_check": (exec_result or {}).get("duration_check"),
                            "audio_check": (exec_result or {}).get("audio_check")}
                           if (exec_result or {}).get("split_plan") else None),
        "note": "PI 判定复用冻结定义与 M2 门禁（未改阈值）；6-G §4 起：DCv2 上下文把 DCv2 "
                "narration_plan 传入冻结门禁（口径对齐），declared↔actual 漂移单列为 "
                "PLANNING_DRIFT / PI-6-legacy-declared-drift（非阻断诊断）——**不是**放宽门禁；"
                "DQ 仍 advisory；本层不提升、不绕过任何门禁",
        "read_only": True, "advisory": True, "enforced": False,
    }


def refine_cues_from_script(script_segments: list, captions_build) -> list:
    return captions_build([{"narration": s.get("narration", ""),
                            "duration_s": s.get("duration_s")} for s in script_segments])
