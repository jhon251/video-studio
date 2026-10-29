# -*- coding: utf-8 -*-
"""Pipeline Duration Contract Audit（只读；不执行 ffmpeg、不改任何既有文件、不生成候选）。

目标：定位"脚本声明旁白时长 ≠ 实际 TTS 时长"的根因，并设计唯一可信的时长权威链。
本脚本只做**读取 + 计算 + 产出 1 个新证据文件**。
"""
import json
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
from video_studio.core import captions as core_captions             # noqa: E402
from video_studio.core import strip as core_strip                   # noqa: E402
from video_studio.core import narration as core_narration           # noqa: E402

LOGS = ROOT / "docs" / "regression_2x" / "logs"
DB = ROOT / "projects" / "video_studio.db"
OUT = LOGS / "phase6e_duration_contract_audit.json"
SYNC2 = LOGS / "phase6e_e2_subtitle_audio_sync2.json"
DEFECT = LOGS / "phase6e_e2_subtitle_defect.json"

con = sqlite3.connect("file:{}?mode=ro".format(DB.as_posix()), uri=True)
con.row_factory = sqlite3.Row
con.execute("PRAGMA query_only=ON")
rows = [dict(r) for r in con.execute(
    "select artifact_id, task_id, type, path, created_at from artifacts "
    "where project_id='p_96efdc03e1aa' order by created_at")]
con.close()


def load(p):
    q = Path(p)
    q = q if q.is_absolute() else ROOT / q
    return json.loads(q.read_text(encoding="utf-8"))


def latest(t, task=None):
    lst = [r for r in rows if r["type"] == t]
    x = next((y for y in lst if task and y["task_id"] == task), lst[-1] if lst else None)
    return (load(x["path"]), x) if x else ({}, None)


script, s_rec = latest("script_output")
voice, v_rec = latest("voice_output")
render, r_rec = latest("render_output", "t_d0a54bdf1810")
segs = script.get("segments") or []
vsegs = voice.get("segments") or []
timeline = render.get("material_timeline") or []
cues = core_captions.build_cues([{"narration": core_strip.strip_claims(s.get("narration", "")),
                                  "duration_s": s.get("duration_s")} for s in segs])

# ---------------- 21 段审计表 ----------------
declared_total = core_narration.script_time_base_s(script)
table, cd, ca, drift_max, first_gt = [], 0.0, 0.0, 0.0, {}
for i, s in enumerate(segs):
    d = float(s.get("duration_s") or 0.0)
    a = float((vsegs[i] if i < len(vsegs) else {}).get("duration_s") or 0.0)
    cd_s, ca_s = cd, ca
    cd += d
    ca += a
    drift = round(cd_s - ca_s, 3)                     # 段起始处的累计漂移
    drift_end = round(cd - ca, 3)
    drift_max = max(drift_max, abs(drift_end))
    for thr in (2, 10, 30, 60):
        if thr not in first_gt and abs(drift_end) > thr:
            first_gt[thr] = s.get("scene_id") or i
    tw = timeline[i] if i < len(timeline) else {}
    seg_cues = [c for c in cues if c["start"] >= cd_s - 1e-6 and c["start"] < cd - 1e-6]
    table.append({
        "i": i, "scene": s.get("scene_id"),
        "declared_duration_s": round(d, 3),
        "actual_tts_duration_s": round(a, 3),
        "delta_s": round(d - a, 3),
        "cum_declared_start_s": round(cd_s, 3), "cum_actual_start_s": round(ca_s, 3),
        "cumulative_drift_s": drift, "cumulative_drift_end_s": drift_end,
        "timeline_window_s": [tw.get("start_s"), tw.get("end_s")],
        "subtitle_cues": {"count": len(seg_cues),
                          "first": (seg_cues[0]["start"] if seg_cues else None),
                          "last_end": (seg_cues[-1]["end"] if seg_cues else None)},
        "text_head": core_strip.strip_claims(s.get("narration", ""))[:28],
    })

# 孤儿字幕时长（有字幕但无语音）与未被字幕覆盖的语音时长
blocks = json.loads(SYNC2.read_text(encoding="utf-8"))["blocks_60s"]
orphan_cue_s = round(sum((b["cue_frac"] or 0) * (1 - (b["speech_frac"] or 0)) * 60 for b in blocks), 1)
speech_no_cue_s = round(sum((1 - (b["cue_frac"] or 0)) * (b["speech_frac"] or 0) * 60
                            for b in blocks), 1)

audit = {
    "schema": "pipeline-duration-contract-audit-v1", "stage": "6-E",
    "note": "只读审计：未执行 ffmpeg、未修改任何既有文件、未生成候选、未执行 E2–E5。",
    "subject": {"project_id": "p_96efdc03e1aa", "film_task": "t_d0a54bdf1810",
                "script_artifact": s_rec["artifact_id"] if s_rec else None,
                "voice_artifact": v_rec["artifact_id"] if v_rec else None,
                "render_artifact": r_rec["artifact_id"] if r_rec else None},

    # 1) 数据流
    "duration_dataflow": [
        {"stage": "script（LLM 规划）", "producer": "agents/script/agent.py",
         "field": "segments[].duration_s", "nature": "**声明/规划值**（估计，未测量）",
         "code": "agents/script/agent.py:37 required duration_s"},
        {"stage": "脚本时基（时间轴权威）", "producer": "core/narration.py:53-55 `script_time_base_s`",
         "field": "Σ max(duration_s,3)+TRAILING_PAD_S",
         "nature": "**把声明值提升为时间轴权威**", "value": round(declared_total, 3),
         "code": "core/narration.py:55"},
        {"stage": "TTS 合成", "producer": "agents/voice/agent.py + tools/tts_tool.py",
         "field": "segments[].duration_s（实际音频）", "nature": "**实测值**",
         "value": round(sum(float(v.get('duration_s') or 0) for v in vsegs), 3)},
        {"stage": "voice_output 时长契约", "producer": "agents/voice/agent.py:114-117",
         "field": "duration_contract{narration_duration_s,shortfall_s,within_tolerance,...}",
         "nature": "**记录**不一致（不阻断）",
         "recorded": voice.get("duration_contract")},
        {"stage": "旁白音轨拼接", "producer": "agents/voice/agent.py:106 ffmpeg op=concat",
         "field": "narration_path", "nature": "拼接后实测 = 961.656 s",
         "value": voice.get("narration_duration_s")},
        {"stage": "时间轴构建", "producer": "agents/editing/agent.py:553/1231-1241",
         "field": "material_timeline[].start_s/end_s",
         "nature": "**用声明时基**生成镜头窗口（与真实音频无关）"},
        {"stage": "字幕 cue 构建", "producer": "agents/subtitle/agent.py:38 + core/captions.py:148",
         "field": "cues[].start/end", "nature": "**用声明时基**按文本长度分摊 ⇒ 与音频失同步"},
        {"stage": "混音/渲染", "producer": "agents/editing/agent.py:1373-1374、core/bgm.py:389-400",
         "field": "apad（静音补齐到时间轴）", "nature": "**把 570.3 s 缺口吸收成尾部静音**"},
        {"stage": "PI 门禁（6-A/M2，后置）", "producer": "core/integrity.pre_render_gate + ops/integrity.py",
         "field": "PI-1/PI-2/PI-3/PI-6",
         "nature": "能测出本缺陷；但 **v9 渲染时尚不存在**（render_output 无 pre_render_gate 字段）"},
    ],

    # 2) 根因链
    "root_cause_chain": [
        "① 脚本给出 per-segment `duration_s`（规划估计，21 段合计 1530.0 s）",
        "② `core/narration.script_time_base_s()` 把该估计值变成**时间轴权威**（+2 s 收尾 = 1532.0 s）",
        "③ TTS 实际只产出 961.656 s（每段都短 9–29 s）——真实语音长度从未成为权威",
        "④ `duration_contract()` 已测出 `within_tolerance=false / shortfall=570.344 s`，但**只记录不阻断**；"
        "当时的阻断条件只有 `excess_s > 0`（旁白**过长**才拦），**短缺侧无硬门**",
        "⑤ 字幕按声明时基分摊 ⇒ cue 表铺到 1530 s，而语音在 ~961 s 结束 ⇒ 漂移线性增长到 568 s，"
        "960 s 之后为『无旁白的字幕』",
        "⑥ `apad` 把旁白补齐到时间轴（voice.render 均记 `audio_padded_to_timeline: true`）⇒ "
        "成片音轨长度『看起来正确』，**缺口被静音掩盖**",
        "⑦ 6-A/M2 `pre_render_gate` 上线后可拦住该片（PI-1 0.6277<0.90、PI-2 短缺 570>30 s、PI-3 静音、PI-6 漂移），"
        "但 v9 早于该门禁（render_output 无 `pre_render_gate`）⇒ 缺陷被固化进 v9 及全部后裔候选",
    ],

    "measurements": {
        "timeline_total_s": 1532.0, "declared_total_s": round(declared_total, 3),
        "actual_tts_total_s": voice.get("narration_duration_s"),
        "shortfall_s": round(1532.0 - float(voice.get("narration_duration_s") or 0), 3),
        "recorded_voice_contract": voice.get("duration_contract"),
        "recorded_render_contract": render.get("duration_contract"),
        "v9_render_has_pre_render_gate_field": "pre_render_gate" in render,
        "max_cumulative_drift_s": round(drift_max, 3),
        "drift_thresholds_crossed": first_gt,
        "cue_last_end_s": (max(c["end"] for c in cues) if cues else None),
        "audio_ends_at_s": voice.get("narration_duration_s"),
        "orphan_cue_seconds": orphan_cue_s, "speech_without_cue_seconds": speech_no_cue_s,
    },
    "audit_table_21_segments": table,

    # 3) 权威时长应该给谁
    "authority_recommendation": {
        "verdict": "**实际 TTS duration 必须成为旁白/字幕的时间权威**（脚本声明时长降级为"
                   "『规划意图 + 允许的段间停顿预算』）。理由：音频是唯一的物理事实；"
                   "字幕必须贴音频；时间轴必须由音频推导，否则必然再现本次缺陷。",
        "proposed_authority_chain": "script(规划) → TTS(实测) → **audio_time_base = Σ actual + Σ pause_budget + trailing_pad**"
                                    " → timeline（由 audio_time_base 推导） → cues（贴 actual 语音区间） → render",
        "knock_on_effects": {
            "素材/materials": "素材本身无需更换；但镜头窗口变化 ⇒ 素材的 in/out、Ken Burns 运动、"
                              "切分点、时长占比全部需重新布局（auto）。",
            "分镜/scene": "镜头数可不变，但每个场景时长改为按实际旁白长度重排；"
                          "若总长从 1532 s 降到 ~964 s，内容覆盖需要人工确认（可能需扩写旁白或保留更多素材）。",
            "字幕/captions": "cue 表由实际段时长 + 语音活动区间生成 ⇒ 与音频对齐；"
                             "需重新烧录（属重新渲染）。",
            "BGM": "`core/bgm.py:114-135` 已按 **voice 段实际时长** 生成 ducking 窗口（方向正确）；"
                   "时间轴缩短后 BGM 截断/补静音逻辑需按新总长重算。",
            "timeline": "时间轴变为**派生量**（audio-derived）；任何『声明时长』不再能独立决定镜头窗口。",
            "PI/DQ": "PI-1/PI-2/PI-3/PI-6 将自然转 PASS（不再有 570 s 静音）；DQ-3/DQ-4 等镜头统计会随之改变。",
        },
    },

    # 4) 三方案比较
    "options": {
        "A_rebuild_time_base_from_actual": {
            "desc": "以真实 TTS 时长重建时间基（+显式段间停顿预算），时间轴/字幕/镜头窗口全部由音频推导",
            "technical_feasibility": "高——`script_time_base_s` 是唯一权威入口（core/narration.py:55），"
                                     "替换为 `audio_time_base_s` 即可；voice agent 已持有实测值",
            "audio_naturalness": "**不变**（音频不动，是权威）",
            "visual_timing_impact": "**大**：全片时长 1532 s → ≈964 s（−37%）；所有镜头窗口/切分/素材 in-out 重排",
            "data_consistency_risk": "低（单一权威）；但需重建 timeline 与 cues，"
                                     "历史 proposal 的窗口（如 E2 的 S05 [245,300]）**失效**需重新定位",
            "verdict": "**推荐（唯一能同时修好字幕与静音缺口的方案）**",
        },
        "B_force_tts_to_declared": {
            "desc": "强制 TTS 适配声明时长（atempo 变速 / 拉长停顿 / 扩写文本）",
            "technical_feasibility": "中：atempo 需 1532/961.7 = **1.59×** 放慢 ⇒ 远超自然区间（可用上限约 1.1–1.15×），"
                                     "只能靠**扩写旁白**（+570 s 文本）或**加长停顿**；前者要重写脚本与事实核对，"
                                     "后者等价于现在的静音缺口",
            "audio_naturalness": "**风险高**（变速失真；长停顿使节奏崩坏）",
            "visual_timing_impact": "**无**（时间轴不动）",
            "data_consistency_risk": "低（声明=实际）但内容风险高（扩写 570 s 需重新事实核查/证据链）",
            "verdict": "不推荐（除非人工决定把片子扩写 57%）",
        },
        "C_realtime_subtitles_only": {
            "desc": "只重排字幕到实际音频（不动时间轴/镜头）",
            "technical_feasibility": "**最高**（改 cue 生成 + 重烧字幕即可）",
            "audio_naturalness": "不变",
            "visual_timing_impact": "无",
            "data_consistency_risk": "**高**：形成双时基（timeline=声明 vs cues=实测），"
                                     "且不解决末尾 **~570 s 无旁白**（PI-1/PI-3 仍 FAIL）；"
                                     "需重新渲染字幕（全片刻录）",
            "verdict": "只作为**过渡**（让现有片子可读），不能作为修复终点",
        },
    },

    # 5) 被 padding/fallback 掩盖的同类问题
    "masking_audit": [
        {"where": "agents/editing/agent.py:1373-1374",
         "what": "「时长契约 = 时间轴权威。旁白较短时用 `apad` 静音补齐到 `total`，去掉 `-shortest`」",
         "masking": "**已确认**：把 570.3 s 旁白缺口变成尾部静音，成片长度『正确』",
         "evidence": "voice/render `duration_contract.audio_padded_to_timeline=true`"},
        {"where": "core/bgm.py:389-400（mix_filters）",
         "what": "`[narr]apad` + BGM `atrim`/`apad` + `amix(duration=first)`",
         "masking": "第二层 padding：即使旁白短，混音后仍与时间轴等长 ⇒ 更难察觉",
         "evidence": "代码路径 + 成片 PI-3 最长静音 570.869 s"},
        {"where": "core/narration.py:6-15（历史注释）",
         "what": "曾因 `-t total -shortest` 把 438 s 时间轴截成 238.5 s",
         "masking": "**反向缺陷的修复引入了本次掩盖**：为防截短改成『时间轴权威 + apad』⇒ 短缺侧失去告警",
         "evidence": "文件头注释"},
        {"where": "stage32b/assemble.py:154-158",
         "what": "无音轨时用 `anullsrc` + `-shortest` 兜底",
         "masking": "可能把『缺音轨』变成『静音成片』",
         "evidence": "代码路径（本片未走该分支，但同类风险存在）"},
        {"where": "stage32b/render.py:88-118",
         "what": "字幕时间边界按 concat 实测时长**钳制**（只动时间边界）",
         "masking": "可把字幕溢出静默裁掉 ⇒ 掩盖字幕/媒体时长不一致",
         "evidence": "代码注释"},
        {"where": "agents/editing/agent.py:568-571",
         "what": "阻断条件仅 `excess_s > 0 and not within_tolerance`（旁白**过长**）",
         "masking": "**短缺侧无阻断**（本次缺陷的直接原因）",
         "evidence": "代码"},
    ],

    # 6) 新硬门禁设计
    "new_hard_gates": [
        {"id": "G1", "name": "TTS actual vs declared/narration duration",
         "rule": "|Σactual − Σdeclared| ≤ max(3.0 s, 1%)；且 **双侧**（shortfall 与 excess 同权）",
         "where": "agents/voice/agent.py（写 voice_output **之前**）+ agents/editing/agent.py 预渲染",
         "fail": "BLOCKED（不产出 voice_output.complete=true、不调用 ffmpeg 渲染）",
         "reuse": "扩展现有 `core/narration.duration_contract`（把 shortfall 也纳入阻断）"},
        {"id": "G2", "name": "segment-level drift",
         "rule": "每段 |declared_i − actual_i| ≤ max(1.0 s, 10%)",
         "where": "voice agent（逐段）", "fail": "BLOCKED + 列出越界段",
         "reuse": "新增 `core/narration.segment_drift()`（纯计算，可单测）"},
        {"id": "G3", "name": "cumulative drift",
         "rule": "任意段起始处 |cum_declared − cum_actual| ≤ 2.0 s（字幕同步容差）",
         "where": "voice agent + editing 预渲染", "fail": "BLOCKED",
         "reuse": "新增 `core/narration.cumulative_drift()`"},
        {"id": "G4", "name": "subtitle-to-TTS alignment",
         "rule": "① cue 展示时间中 ≥98% 必须落在语音活动区间；② 语音活动时间 ≥95% 被 cue 覆盖；"
                 "③ 末条 cue.end ≤ 音频结束 + 1.0 s",
         "where": "editing 预渲染（cue 表已生成）+ post_render（实测）",
         "fail": "BLOCKED", "reuse": "扩展 `core/integrity.subtitle_orphans`（现为只读诊断）为阻断门"},
        {"id": "G5", "name": "final audio silence",
         "rule": "内部静音 ≤8 s；尾部静音 ≤5 s；静音总占比 ≤5%",
         "where": "post_render_gate（已有 PI-3）", "fail": "BLOCKED 且**禁止 promote**",
         "reuse": "PI-3 现行实现"},
        {"id": "G6", "name": "timeline/audio consistency",
         "rule": "timeline_total == audio_time_base（Σ actual + Σ pause_budget + trailing）± 0.5 s；"
                 "且 **禁止 `apad` 超过 pause_budget**（>5 s 的补齐必须 fail-closed）",
         "where": "editing 预渲染 + core/bgm.mix_filters 前置检查", "fail": "BLOCKED",
         "reuse": "新增；并把 §masking_audit 中的 apad 用法改为『受预算约束的显式停顿』"},
    ],

    # 7) 受影响模块与最小修改范围
    "affected_modules": [
        {"file": "core/narration.py", "role": "权威时基与契约",
         "change": "新增 `audio_time_base_s()`/`segment_drift()`/`cumulative_drift()`；"
                   "`duration_contract` 双侧阻断；`script_time_base_s` 改名语义为『规划时基（仅供规划）』"},
        {"file": "agents/voice/agent.py", "role": "实测时长产生者",
         "change": "合成后立即跑 G1/G2/G3；越界 ⇒ 不写 complete、不拼接音轨（fail-closed）"},
        {"file": "agents/editing/agent.py", "role": "时间轴/混音/渲染",
         "change": "时间轴改用 audio_time_base；apad 受 pause_budget 约束；预渲染跑 G1/G4/G6"},
        {"file": "agents/subtitle/agent.py", "role": "cue 生成",
         "change": "cue 由实际段时长 + 语音活动区间生成（贴音频）"},
        {"file": "core/captions.py", "role": "cue 构造", "change": "支持传入实测区间（保持向后兼容）"},
        {"file": "core/integrity.py", "role": "门禁实现",
         "change": "新增 G4/G6；把 G1/G2/G3 纳入 pre_render_gate；PI-3 在 promote 路径改为阻断"},
        {"file": "core/bgm.py", "role": "混音", "change": "按新总长重算 atrim/apad；禁止用 apad 掩盖旁白缺口"},
        {"file": "ops/*", "role": "只读执行层", "change": "**不改**（保持只读语义）"},
    ],
    "minimal_change_scope": "4 个生产模块（core/narration.py、agents/voice、agents/editing、agents/subtitle）"
                            "+ 2 个门禁模块（core/integrity.py、core/bgm.py 的 apad 预算检查）；"
                            "ops/* 与执行契约不动。",
    "recommended_fix_order": [
        "1) 先加**纯计算门禁**与单测（不改行为）：segment_drift / cumulative_drift / audio_time_base（可对历史数据回放验证：应能标出 v9）",
        "2) 在 voice agent 侧把 G1/G2/G3 设为**阻断**（fail-closed），保证不再产出新的失同步 voice_output",
        "3) 把时间轴权威从 `script_time_base_s` 切到 `audio_time_base_s`（editing agent），同步更新字幕 cue 生成",
        "4) 加 G4/G6 预渲染门 + G5 promote 阻断；`apad` 改为 pause_budget 约束",
        "5) 先在**新项目**上端到端验证（不要动 v9），通过后再决定是否重制 v9 相关交付物",
        "6) 最后再讨论 E1–E5 的重制与 baseline 重切（需人工单独授权）",
    ],

    # 8) 可沿用 / 必须重新生成
    "reuse_vs_regenerate": {
        "must_regenerate": [
            "v9 母版成片（音轨 570.3 s 静音 + 字幕漂移）——**不能作为可信基准继续使用**（可保留为历史）",
            "6-C 候选 C1–C4（全部派生自 v9，继承同一缺陷）",
            "6-E E1 候选（片尾字体修复有效，但成片继承缺陷）",
            "6-E E2 候选（叠加层设计有效，但成片继承缺陷；且其窗口 [245,300] 定义在被修正前的时基上）",
            "任何以 v9 时基计算的字幕/时间轴产物（cues、material_timeline、ducking 窗口）",
        ],
        "usable_unchanged": [
            "素材与素材许可/署名台账（无需重下）",
            "旁白 TTS 音频（961.656 s）——它才是事实来源，**不需要重录**",
            "脚本正文与事实核查证据链（除非选择方案 B 扩写旁白）",
            "E1 的字体修复与 E2 的叠加层**设计/代码/证据**（可移植到重制后的母版）",
            "历史 baseline ZIP 与 manifest（作为历史记录保留，但需标注『含本缺陷』）",
        ],
        "needs_human_decision": [
            "总时长策略：接受 ~964 s（方案 A）还是扩写旁白到 1532 s（方案 B 变体）",
            "是否重切 baseline / 是否需要新 tag（**未授权前不做**）",
            "E1–E5 的重制顺序与是否需要重新审批新 proposal（窗口变化会导致 E2 等方案需重新定位/重审）",
        ],
    },
    "to_be_rendered_again": [
        "全片渲染（成片 MP4）：必须重制（时间轴/字幕/音轨任一处改变都需要重渲）",
        "字幕烧录：必须重制（cue 表改变）",
        "音轨混音：必须重制（不再需要 570 s 静音补齐；BGM ducking 窗口改变）",
        "镜头/素材布局：若采用方案 A 则必须重排（不需要重新下载素材）",
    ],
    "not_to_be_rendered_again": [
        "TTS 旁白音频本身（可复用）",
        "素材文件与许可记录",
    ],
}
audit["audit_sha256"] = __import__("hashlib").sha256(
    json.dumps({k: v for k, v in audit.items() if k != "audit_sha256"}, sort_keys=True,
               ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
OUT.write_text(json.dumps(audit, ensure_ascii=False, indent=1), encoding="utf-8")

print("== 时长数据流根因 ==")
print("时间轴权威 1532.0s（= 声明 1530.0 + 收尾 2s） | 实际 TTS 961.656s | 缺口 570.344s")
print("v9 render_output 含 pre_render_gate 字段:", audit["measurements"]["v9_render_has_pre_render_gate_field"])
print("记录在案的契约:", json.dumps(voice.get("duration_contract"), ensure_ascii=False))
print("\n== 21 段审计（前 12 行）==")
print("{:>2} {:>4} {:>8} {:>8} {:>8} {:>10} {:>9}".format("i", "scn", "declared", "actual",
                                                          "delta", "cum_drift", "timeline"))
for r in table[:12]:
    print("{:>2} {:>4} {:>8.2f} {:>8.2f} {:>8.2f} {:>10.2f} {:>9}".format(
        r["i"], str(r["scene"]), r["declared_duration_s"], r["actual_tts_duration_s"],
        r["delta_s"], r["cumulative_drift_end_s"],
        str(r["timeline_window_s"][1])))
print("...（全表见 JSON）")
print("\n末端: 累计漂移 {:.1f}s | 末条 cue end={} | 音频结束={}".format(
    table[-1]["cumulative_drift_end_s"], audit["measurements"]["cue_last_end_s"],
    audit["measurements"]["audio_ends_at_s"]))
print("孤儿字幕时长 {:.1f}s（有字幕无语音） | 未被字幕覆盖的语音 {:.1f}s".format(
    orphan_cue_s, speech_no_cue_s))
print("audit ->", OUT)
