"""Editing Agent：剪辑规划（LLM）+ 剪辑执行（FFmpeg 工具，确定性）。

- task_type=editing_plan：产出时间线方案（JSON），人工可审。
- task_type=render：按剪辑方案调用 FFmpeg 工具装配成片（V1 演示：无素材时生成测试片段）。
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

from ..base import Agent, register
from ...core.motion import MOTION_FALLBACK_CODE as MOTION_FALLBACK_CODE
from ...core.motion import resolve_config as _motion_resolve

ROOT = Path(__file__).resolve().parents[4]
from ...core.narration import (NarrationIncompleteError, VIDEO_DURATION_TOLERANCE_S,
                               check_narration_padding, duration_contract, evaluate_narration,
                               incomplete_message, narration_plan, probe_duration_s,
                               script_time_base_s, tolerance_ratio)
from ...core import audio as core_audio
from ...core import bgm as core_bgm
from ...core import captions as core_captions
from ...core import integrity as core_integrity
from ...core.materials import (MaterialInsufficientError, assembly_class, frame_corr, gray48,
                               insufficient_message, is_external_candidate, license_gate_applies,
                               policy_from_config)
from ...core.selection_review import (latest_selections_from_conn, selection_projection,
                                      validate_choice)
from ...tools.material_provider import classify_license, license_block_reason

PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "timeline": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "track": {"type": "string"},
                    "start_s": {"type": "number"},
                    "duration_s": {"type": "number"},
                    "source": {"type": "string"},
                    "transition": {"type": "string"},
                    "note": {"type": "string"},
                },
                "required": ["track", "start_s", "duration_s", "source"],
            },
        },
        "render_params": {
            "type": "object",
            "properties": {
                "resolution": {"type": "string"},
                "fps": {"type": "number"},
                "codec": {"type": "string"},
                "format": {"type": "string"},
            },
        },
        "summary": {"type": "string"},
        "confidence": {"type": "number"},
        "note": {"type": "string"},
    },
    "required": ["timeline", "summary"],
}


class MaterialTimeline(list):
    """素材时间轴：**行为等同 `list`**（既有调用方零改动），另可携带 `.allocation` 证据。

    为什么需要（实测踩坑）：`list` **没有 `__dict__`**，`scenes.allocation = alloc` 会抛
    `AttributeError`；若用 `try/except` 吞掉，证据会**静默丢失**（正是 P28 §0 明令禁止的
    "静默回落"）。改用 `list` 子类 ⇒ 既保持返回类型兼容（`isinstance(x, list)` 仍为真），
    又能稳定携带分配纪律证据。
    """

    __slots__ = ("allocation",)


# ---- P58-2：**视频条素材**（media_type=video）辅助 ----
VIDEO_EXTS = (".mp4", ".webm", ".mov")


def _pins_file_for(project_id) -> pathlib.Path:
    """P59-6：**项目级 pins 开关**（加法式泛化，P56-2 机制不变）。

    优先 `logs/pins_<project_id>.json`（本工程专用钉定）；缺省回落既有
    `logs/p56_2_f9_pins.json`（第二期及历史渲染行为**逐字节不变**）。
    """
    if project_id:
        cand = ROOT / "docs" / "regression_2x" / "logs" / (
            "pins_{}.json".format(str(project_id)))
        if cand.is_file():
            return cand
    return ROOT / "docs" / "regression_2x" / "logs" / "p56_2_f9_pins.json"



def _ffprobe_exe(config: dict | None = None) -> str | None:
    """ffprobe 解析：`core_audio.resolve_ffmpeg` 同目录 → 仓库冻结工具链 `bin/` → PATH。"""
    try:
        from ...core import audio as _ca
        ff = _ca.resolve_ffmpeg(config)
        if ff:
            for name in ("ffprobe.exe", "ffprobe"):
                cand = Path(ff).with_name(name)
                if cand.is_file():
                    return str(cand)
    except Exception:                                                           # noqa: BLE001
        pass
    for name in ("ffprobe.exe", "ffprobe"):
        cand = ROOT / "bin" / name
        if cand.is_file():
            return str(cand)
    import shutil
    return shutil.which("ffprobe")


def _probe_video_usable(p: Path, ffprobe: str | None) -> tuple:
    """视频条可用性探测（fail-closed）：`(usable, why, w, h, duration_s)`。

    ffprobe 不可达 / 流缺失 / 解析失败 ⇒ `(False, 原因, None, None, None)`。
    """
    if not ffprobe:
        return False, "VIDEO_PROBE_UNAVAILABLE: ffprobe 不可解析", None, None, None
    try:
        import subprocess as _sp
        r = _sp.run([ffprobe, "-v", "error", "-select_streams", "v:0",
                     "-show_entries", "stream=width,height:format=duration",
                     "-of", "json", str(p)],
                    capture_output=True, text=True, encoding="utf-8",
                    errors="replace", timeout=60)
        if r.returncode != 0:
            return False, "VIDEO_PROBE_FAILED: {}".format((r.stderr or "")[:100]), \
                None, None, None
        j = json.loads(r.stdout or "{}")
        st = (j.get("streams") or [{}])[0]
        w, h = st.get("width"), st.get("height")
        dur = float(j.get("format", {}).get("duration") or 0) or None
        if not w or not h:
            return False, "VIDEO_NO_STREAM", None, None, dur
        return True, None, int(w), int(h), dur
    except Exception as exc:                                                    # noqa: BLE001
        return False, "VIDEO_PROBE_FAILED: {}: {}".format(type(exc).__name__,
                                                          str(exc)[:80]), None, None, None


@register
class EditingAgent(Agent):
    role = "editing"
    tier = "M"
    description = "剪辑规划（时间线方案）+ 剪辑执行（FFmpeg）。最终创意判断属于人。"
    system_prompt = (
        "你是视频剪辑规划师。根据脚本、镜头清单与候选素材制定剪辑执行计划："
        "时间线结构（轨道/起止/素材/转场）与渲染参数。你只做施工图，最终创意判断属于人类。"
        "输出严格 JSON。"
    )
    output_schema = PLAN_SCHEMA

    def run(self, engine, task: dict) -> None:
        if task["task_type"] == "render":
            self._render(engine, task)
        else:
            super().run(engine, task)

    @staticmethod
    def _kw_tokens(text: str) -> set:
        """镜头↔素材匹配关键词：CJK 二元组（权重 2）+ 单字（权重 1）+ 拉丁词（权重 2）。"""
        t = re.sub(r"[\s\W_]+", "", str(text or ""))
        grams = {t[i:i + 2] for i in range(len(t) - 1)} if len(t) > 1 else set()
        chars = set(t) if t else set()
        latin = {w.lower() for w in re.findall(r"[A-Za-z]{3,}", str(text or ""))}
        return grams | chars | latin

    @staticmethod
    def _match_score(query_tokens: set, name: str) -> tuple[int, list]:
        """混合打分：二元组命中×2 + 单字命中×1 + 拉丁词×2（返回分数与命中样例）。

        纯二元组匹配过于严格：本地素材名与旁白用词常有差异（实测「脑电头环」对
        「脑机接口/电极」零命中），导致素材被静默丢弃。改为混合打分仍属**词面匹配**，
        不伪造任何候选；命中样例一并记录，便于 Phase 2-D 追溯。
        """
        hay = str(name or "").lower()
        grams = [t for t in query_tokens if len(t) == 2]
        chars = [t for t in query_tokens if len(t) == 1]
        latin = [t for t in query_tokens if len(t) > 2]
        hit_g = sorted(t for t in grams if t.lower() in hay)
        hit_c = sorted(t for t in chars if t.lower() in hay)
        hit_l = sorted(t for t in latin if t.lower() in hay)
        score = 2 * len(hit_g) + 1 * len(hit_c) + 2 * len(hit_l)
        return score, (hit_g + hit_l + hit_c)[:8]

    @classmethod
    def _build_material_timeline(cls, script: dict, shots: list, asset_pool: list,
                                 policy: dict | None = None,
                                 material_provided: bool = True,
                                 excluded_pool: list | None = None,
                                 provider_requested: bool = False,
                                 human_selections: dict | None = None,
                                 engine=None, task: dict | None = None,
                                 segment_durations: list | None = None,
                                 pause_budget_s: float | None = None,
                                 trailing_pad_s: float | None = None) -> list:
        """Phase 2-A/B + 2-C：把脚本段落切成镜头，为每个镜头做**分类化**素材决策，产出素材时间轴。

        每镜头记录：场景窗口、原始需求、候选与分数、最终选择、fallback 分类/原因、
        needs_hitl、allowed_in_final_render（完整可追溯，见 `core/materials.py`）。

        规则（确定性、可审计）：
          · 查询文本 = 该段旁白 + 对应镜头的 description/gen_prompt
          · 候选 = 素材池中 match_score > 0 者；不可用素材（解码失败/尺寸不合格）不参与选择
          · 诊断：NO_CANDIDATE / LOW_MATCH / ASSET_UNUSABLE / ASSET_CONFLICT / ASSET_EXHAUSTED / NONE
          · 动作：LOCAL_INGEST（正常命中）/ THEME_FALLBACK（同主题降级，明确标注）/
                  SOLID_COLOR_CARD（安全占位，selected_asset=null）/ BLOCKED_FOR_HUMAN
        """
        from ...core.strip import strip_claims
        from ...core.materials import classify_scene, extract_constraints, policy_from_config
        pol = policy or policy_from_config(None)
        # P34-1/P33-2：**运行期开关**（分配纪律 + 具名绑定）。
        # 为何在此读取（实测踩坑两次）：`core/materials.py` 被 5.x 基线 manifest **逐字节钉定**
        # （`tests/maintenance_fixes_test.py::M8a` 的 "thresholds" 组）⇒ 不得在其
        # `DEFAULT_POLICY`/`policy_from_config` 中加键；且**生产链是带着 `policy=mat_policy`
        # 调用本函数**的，故不能以 `policy is None` 作为读取条件（首版即因此从未生效）。
        # 统一从 `engine.config["editing"]` 透传；缺省 ⇒ 不写入 ⇒ 既有行为逐字不变。
        _raw_cfg = ((getattr(engine, "config", None) or {}).get("editing") or {})
        for _k in ("max_scenes_per_asset", "forbid_adjacent_same_asset", "min_scene_gap"):
            if _k in _raw_cfg:
                pol[_k] = _raw_cfg[_k]
        # P34-1：**具名绑定**（owner-approved explicit binding）。
        # 动机（授权书 §1(a)）：关键词匹配对"为抽象解说配示意"的场景**结构上必然落空**
        # （池内无可字面命名之物）⇒ 合法地落到纯色卡 ⇒ 形成"有旁白 + 无画面"。
        # 处置：允许运维/监理**具名**指定素材（带 `approval_document`），**绕过匹配分阈值**
        # （语义相关性由人工判断，不由阈值伪造），并**完整留痕**在 `selection_reason`。
        _explicit_bind = dict(_raw_cfg.get("explicit_bindings") or {})
        # ---- P42-1：**片级内容排除**（content-level asset ban）----
        # 动机（Phase 42 监理帧验证）：P41-1 的「螺壳段必须换出」只在 **ID 层**兑现
        # （`cfae038f` 换成 `2442c39e`），**画面家族没换** —— 该素材仍出现 3 次。
        # 处置：按**素材身份（sha256 / asset_id）**在本片**全部景的候选域中排除**，
        # 走**既有 decisions 通道**的外部开关文件（`config/content_exclusions.json`，
        # `config.json` 零改动）。**排除后若某景空域 ⇒ 如实登记，不硬造候选。**
        _ban: set = set()
        _exclusion_evidence = []
        _exclusion_error = None
        try:
            _cef = ROOT / "config" / "content_exclusions.json"
            if _cef.is_file():
                _cej = json.loads(_cef.read_text(encoding="utf-8"))
                _ce = (_cej.get("content_exclusions") or {})
                if _ce.get("enabled", True):
                    for _x in (_ce.get("excluded") or []):
                        if _x.get("asset_id"):
                            _ban.add(str(_x["asset_id"]))
                        if _x.get("sha256_prefix"):
                            _ban.add(str(_x["sha256_prefix"]))
                    _exclusion_evidence = [
                        {"asset_id": _x.get("asset_id"), "name": _x.get("name"),
                         "reason": _x.get("reason"),
                         "approved_by": _x.get("approved_by"),
                         "approval_document": _x.get("approval_document")}
                        for _x in (_ce.get("excluded") or [])]
                    # ---- P46-2：**技术性排除**（与内容排除分开记账，同样出候选域）----
                    _tex = (_ce.get("technical_exclusions") or {})
                    if _tex.get("enabled", True):
                        for _x in (_tex.get("excluded") or []):
                            if _x.get("asset_id"):
                                _ban.add(str(_x["asset_id"]))
                            if _x.get("sha256_prefix"):
                                _ban.add(str(_x["sha256_prefix"]))
                            _exclusion_evidence.append(
                                {"asset_id": _x.get("asset_id"),
                                 "name": _x.get("name"), "reason": _x.get("reason"),
                                 "kind": "technical",
                                 "approved_by": _x.get("approved_by"),
                                 "approval_document": _x.get("approval_document")})
                else:
                    _exclusion_evidence = []
            else:
                _exclusion_evidence = []
        except Exception as _exc:                                               # noqa: BLE001
            _ban, _exclusion_evidence = set(), []
            _exclusion_error = "{}: {}".format(type(_exc).__name__, str(_exc)[:120])
        # ---- P47-3：**asset_id 归一化**（家族/锚定/排除都按 asset_id 匹配）----
        # **踩坑（P47 实测）**：检索池里**12 张历史素材的 `asset_id` 为 `None`**
        # （只有 `sha256`）。后果很隐蔽：`_family_of(None, …)` 恒返回 `None`
        # ⇒ 这些素材**完全绕过家族约束**（F5/F6 报的家族份额其实只统计了有 id 的那部分！
        # 实测 F7 家族计数出现 `"null": 24` 才暴露）。此处按同款命名补齐
        # `asset_<sha12>`，使家族/锚定/排除的匹配**覆盖全池**。
        _norm = 0
        for _a in (asset_pool or []):
            if not _a.get("asset_id"):
                _sh = str(_a.get("sha256") or "")
                if _sh:
                    _a["asset_id"] = "asset_{}".format(_sh[:12])
                    _norm += 1
        _norm_asset_ids = _norm
        # P47-3：生成批次账本（抽象景优先 G；见下方 _gen_pref）
        R_GEN_BATCH = ROOT / "docs" / "regression_2x" / "logs" / "p47_2_gen_batch.json"
        if _ban:
            def _banned(a) -> bool:
                aid = str((a or {}).get("asset_id") or "")
                sh = str((a or {}).get("sha256") or "")
                return any((b and (b in aid or b in sh)) for b in _ban)
            asset_pool = [a for a in (asset_pool or []) if not _banned(a)]
        # ---- P44-1：**语义锚定表**（监理 36/36 逐景裁决）----
        # 语义：被锚定素材**只允许**出现在其 `allowed_scenes`，其余景**禁入**。
        # 这修的是「词法匹配泛化」——例如螺壳/球堆/棋照被分到无语义关联的抽象段。
        _anchor: dict = {}
        try:
            _cef2 = ROOT / "config" / "content_exclusions.json"
            if _cef2.is_file():
                _sap = (json.loads(_cef2.read_text(encoding="utf-8"))
                        .get("content_exclusions", {}).get("scene_asset_policy") or {})
                if _sap.get("enabled", True):
                    for _pfx, _spec in (_sap.get("anchored") or {}).items():
                        _anchor[_pfx] = set(_sap and _spec.get("allowed_scenes") or [])
        except Exception:                                                       # noqa: BLE001
            _anchor = {}

        # P46-1：**具名绑定景集合**（owner-approved ⇒ 豁免锚定守卫；见 `_anchor_ok`）
        _bound_scenes = {str(k) for k in (_explicit_bind or {})}

        def _anchor_ok(asset, scene_id) -> bool:
            """锚定素材是否**允许**出现在该景（未锚定的素材恒 True）。

            **踩坑修正**：检索池的 `asset_id` 可能是 `None`（只有 `sha256` 有值），
            故前缀匹配必须**同时**看 `sha256` 与 `asset_id`（首版只看 asset_id ⇒
            锚定用 `asset_<sha12>` 形如 `asset_1e9d2ab4e64e`，而池里 sha 是
            `1e9d2ab4e64ef982…` ⇒ 前缀能命中；但 asset_id 为 None 时整条匹配失效）。
            """
            if not _anchor:
                return True
            # ---- P46-1：**owner-approved 具名绑定景豁免锚定守卫** ----
            # 授权书 §1 语义：**具名绑定 > 锚定守卫 > 回退**。具名绑定是 owner 的
            # 直接决定，锚定表是监理的场景级建议 ⇒ 冲突时以 owner 为准。
            # （Phase 45 实测：P02_2 具名绑定因锚定被拒 ⇒ 回退到未上屏素材 ⇒
            #  `ASSET_INSUFFICIENT` 阻断渲染。）
            _sid = str(scene_id)
            if _sid in _bound_scenes:
                return True
            aid = str((asset or {}).get("asset_id") or "")
            sh = str((asset or {}).get("sha256") or "")
            for pfx, allowed in _anchor.items():
                if pfx and (pfx in aid or pfx in sh):
                    return str(scene_id) in allowed
            return True
        segs = [s for s in (script or {}).get("segments", [])
                if strip_claims(s.get("narration", "")).strip()]
        # Duration Contract v2：窗口时长来自**实际 TTS 时长**（+ 显式 pause budget），
        # 而不是脚本声明时长；`segment_durations=None` 时退回 v1 声明时基（规划/兼容路径）。
        _pause = (0.0 if pause_budget_s is None else float(pause_budget_s))
        _trail = (2.0 if trailing_pad_s is None else float(trailing_pad_s))
        scenes, cursor, used = [], 0.0, {}
        #: P28-1：父景 id → 已解析绑定（供派生段回退；**只在内存里**，不动 DB 写入路径）
        parent_asset: dict = {}
        #: P41-1：父景 id → **候选列表**（供派生段**候选传播**；同样只在内存里）
        parent_candidates: dict = {}
        for i, seg in enumerate(segs):
            if segment_durations and i < len(segment_durations) and segment_durations[i]:
                dur = max(float(segment_durations[i]), 3.0)
                dur = dur + (_pause if i < len(segs) - 1 else _trail)
            else:
                dur = max(float(seg.get("duration_s") or 0), 3.0)
            shot = shots[i] if i < len(shots) else {}
            # 匹配查询保持 Phase 2-A/B 口径（旁白 + description + gen_prompt）；
            # style_constraint 只用于**约束冲突**判定（extract_constraints），不参与打分，
            # 避免把风格词混进内容匹配而改变既有分配结果。
            shot_text = "{} {}".format(shot.get("description") or "",
                                       shot.get("gen_prompt") or "")
            query = "{} {}".format(strip_claims(seg.get("narration", "")).strip(), shot_text).strip()
            toks = cls._kw_tokens(query)
            cands = []
            for a in asset_pool:
                s, matched = cls._match_score(toks, "{} {}".format(
                    a["name"], a.get("relative_path") or ""))
                if s > 0:
                    cands.append({**a, "match_score": s, "matched_tokens": matched})
            scene_id = "S{:02d}".format(i + 1)
            # ---- P28-1：**保留脚本自带的 scene_id / parent_scene_id** ----
            # 旧实现只用**序号合成**的 `S{i+1}`，把派生脚本的 `S02p1` 之类的 id **丢掉**了呢
            # ⇒ 闸门按派生 id 查绑定必然落空（Phase 27 实测 40 段中仅 2 景有 expected_asset_id）。
            # 这里保留真实 id；**裁决用的 scene_id 仍是合成 id**（保持既有选材/分类语义逐字不变），
            # 真实 id 只用于**绑定回退**与**下游核验**。
            script_scene_id = str(seg.get("scene_id") or "").strip()
            parent_scene_id = str(seg.get("parent_scene_id") or "").strip()
            bind_scene_id = script_scene_id or scene_id
            requirement = {
                "text": query[:300],
                "narration_chars": len(strip_claims(seg.get("narration", ""))),
                "shot_index": shot.get("index"),
                "shot_description": (shot.get("description") or "")[:200],
                "shot_gen_prompt": (shot.get("gen_prompt") or "")[:200],
                "style_constraint": (shot.get("style_constraint") or "")[:200],
                "constraints": extract_constraints(shot, query),
                "min_match_score": pol["min_match_score"],
                "reuse_policy": pol["asset_reuse_policy"],
                "expected_kind": "image",
            }
            decision = classify_scene(scene_id=scene_id, requirement=requirement, candidates=cands,
                                      used_asset_ids=set(used), policy=pol,
                                      material_provided=material_provided,
                                      provider_requested=provider_requested,
                                      excluded_candidates=cls._excluded_matches(
                                          excluded_pool, toks, scene_id))
            pick = decision.get("selected_asset")
            # ---- 4.x Phase 4-C：人审候选替换（**人工选定优先**；校验不过即 fail-closed）----
            # 只读消费 `decisions` 表里最新一条已批准的人工选定（node=selection_override）；
            # **不自动改选材**：没有人工决定时行为与 3.x 完全一致。
            hs = (human_selections or {}).get(scene_id)
            if hs:
                before_auto = pick
                _ok, _code, _detail = validate_choice(decision["candidates"], hs["asset_id"],
                                                      scene_id)
                if not _ok:
                    if engine is not None and task is not None:
                        engine.emit(task["project_id"], "TASK_BLOCKED", "editing",
                                    task["task_id"],
                                    {"error": "[{}] 人工选定素材不可用：{}".format(_code, _detail),
                                     "human_selection": hs}, human_visible=True)
                    raise MaterialInsufficientError(
                        "[{}] 人工选定素材不可用（{}）：{}".format(_code, scene_id, _detail))
                pick = next(c for c in decision["candidates"]
                            if c.get("asset_id") == hs["asset_id"])
                decision["selected_asset"] = selection_projection(pick)
                decision["selection_source"] = "human_review"
                decision["human_selection"] = {"decision_id": hs["decision_id"],
                                               "decided_by": hs["decided_by"],
                                               "reason": hs["reason"],
                                               "decided_at": hs["decided_at"]}
                decision["selection_reason"] = (
                    "**人工复核选定**（{} 于 {}）：{}；素材分={}（同镜头自动选材为 {}）".format(
                        hs["decided_by"], hs["decided_at"], hs["reason"], pick.get("match_score"),
                        (before_auto or {}).get("name") or "-"))
                decision["insufficiency_class"] = "NONE"
                decision["fallback_state"] = "LOCAL_INGEST"
                decision["fallback_action"] = "人工选定"
                decision["fallback_reason"] = "人工复核替换（decision {}）".format(
                    hs["decision_id"])
                decision["needs_hitl"] = False
                decision["allowed_in_final_render"] = True
            # ---- P34-1：具名绑定（owner-approved）**优先于**自动选材结果 ----
            # 只在自动选材**未命中**（纯色卡）时介入；命中时不动，避免覆盖既有语义。
            _eb = _explicit_bind.get(bind_scene_id) or _explicit_bind.get(script_scene_id)
            if _eb and not (decision.get("selected_asset") or {}).get("asset_id"):
                _eb_sha = _eb.get("sha256") if isinstance(_eb, dict) else str(_eb)
                _hit = next((c for c in cands if c.get("sha256") == _eb_sha), None)
                if _hit is None:
                    _hit = next((a for a in asset_pool if a.get("sha256") == _eb_sha), None)
                if _hit is not None and not _anchor_ok(_hit, bind_scene_id):
                    # P44-1：**具名绑定也不得越界锚定**。踩坑：绑定优先级高于锚定
                    # ⇒ 实测 4 处越界（P02_3 / P03_4 / P05_1 / P05_3）。越界 ⇒ 拒绝。
                    decision["anchor_rejected"] = (
                        (decision.get("anchor_rejected") or 0) + 1)
                    decision["fallback_reason"] = (
                        "P44-1：具名绑定目标 {} **越出语义锚定** ⇒ 拒绝绑定".format(
                            str(_eb_sha)[:12]))
                    _hit = None
                if _hit is not None:
                    pick = _hit
                    decision["selected_asset"] = selection_projection(_hit)
                    decision["insufficiency_class"] = "NONE"
                    decision["fallback_state"] = "LOCAL_INGEST"
                    decision["fallback_action"] = "具名绑定（owner-approved）"
                    decision["fallback_reason"] = (
                        "P34-1：该景自动选材无候选（抽象解说无字面可命名素材）⇒ 按 "
                        "{} 具名绑定 `{}`；**绕过匹配分阈值**（语义相关性由人工判定，"
                        "非由阈值伪造）".format(
                            _eb.get("approval_document") if isinstance(_eb, dict) else "-",
                            str(_eb_sha)[:12]))
                    decision["selection_reason"] = decision["fallback_reason"]
                    decision["needs_hitl"] = False
                    decision["allowed_in_final_render"] = True
                    decision["selection_source"] = "explicit_binding"
                else:
                    decision["fallback_reason"] = (
                        "{}（P34-1 具名绑定的 sha256={} **不在池内** ⇒ 保持纯色卡并登记）".format(
                            decision.get("fallback_reason") or "", str(_eb_sha)[:12]))
            if pick is not None:
                aid = pick["asset_id"]
                used.setdefault(aid, []).append(scene_id)
                for c in cands:                     # 记录"被哪些镜头占用"（可追溯）
                    if c["asset_id"] == aid:
                        c["used_by_scenes"] = list(used[aid])
                decision["selected_asset"]["retrieval_match_score"] = pick.get(
                    "retrieval_match_score")
            # ---- P41-1：**派生景候选传播**（取代 P28-1 的「硬继承单一素材」）----
            # 裁定（Phase 41 §0，方案 a）：派生景**继承父景的候选列表**，而不是硬继承父景
            # 已选的那**一个**素材，改由分配器在全局约束（cap/间距/相邻/DQ-3e）下选派。
            # 理由：父景 `candidates` 本已通过**相关度 + 许可**双门；派生景文本 = 父景文本的
            # 子集 ⇒ 语义可传递。**不引入未审素材、不改检索逻辑、不加网络**。
            # 风险边界：若父景条目**携带候选**则传播；否则退化为「仅父景已选素材」
            # （域=1）⇒ 由 `STRUCTURAL_SINGLETON` 如实登记，**不硬造候选**。
            binding_source = "direct"
            if not (decision.get("selected_asset") or {}).get("asset_id") and parent_scene_id:
                pa = parent_asset.get(parent_scene_id)
                pc = parent_candidates.get(parent_scene_id)
                if pc:
                    # **fail-closed**：仅传播**许可/完整性状态可继承**的候选；
                    # 任何不可继承者（许可未清、标记不可用、缺 path）一律**不入围**。
                    _ok = []
                    for _c in pc:
                        if not _c.get("asset_id") or not _c.get("path"):
                            continue
                        if _c.get("usable") is False:
                            continue
                        if _c.get("license_cleared") is False:
                            continue
                        _ok.append(dict(_c))
                    if not _ok:
                        decision["fallback_reason"] = (
                            "P41-1 fail-closed：父景 {} 的候选**许可/完整性不可继承** ⇒ "
                            "无候选入围（保持纯色卡并登记）".format(parent_scene_id))
                        pc = None
                    else:
                        pc = _ok
                if pc:
                    # **传播候选**（逐项携带既有许可/完整性状态，禁止改写这些字段）
                    decision["candidates"] = [dict(c) for c in pc]
                    decision["candidates_total"] = len(decision["candidates"])
                    decision["candidates_propagated_from"] = parent_scene_id
                    decision["candidates_propagation_filtered"] = (
                        "fail-closed：仅许可/完整性可继承者入围")
                    decision["selected_asset"] = selection_projection(
                        decision["candidates"][0])
                    decision["fallback_state"] = (
                        decision.get("fallback_state") or "LOCAL_INGEST")
                    decision["fallback_reason"] = (
                        "P41-1 父景**候选传播**（派生段 {} ← 父景 {}，{} 个候选；"
                        "由分配器在全局约束下选派）".format(
                            bind_scene_id, parent_scene_id,
                            len(decision["candidates"])))
                    decision["allowed_in_final_render"] = True
                    binding_source = "parent_candidates"
                elif pa:
                    # 父景仅**单一已选素材**（无候选列表）⇒ 域=1，如实登记为结构性单例
                    decision["selected_asset"] = pa
                    decision["fallback_state"] = (
                        decision.get("fallback_state") or "LOCAL_INGEST")
                    decision["fallback_reason"] = (
                        "P41-1 STRUCTURAL_SINGLETON：父景 {} 无可传播候选 ⇒ "
                        "回退父景已选素材（域=1，分配器无法改派）".format(parent_scene_id))
                    decision["allowed_in_final_render"] = True
                    binding_source = "parent_fallback_singleton"
            # 记录绑定 + **候选**，供后续派生段传播
            _sa = decision.get("selected_asset")
            if (_sa or {}).get("asset_id"):
                if parent_scene_id:
                    parent_asset.setdefault(parent_scene_id, _sa)
                parent_asset.setdefault(bind_scene_id, _sa)
            if decision.get("candidates"):
                if parent_scene_id:
                    parent_candidates.setdefault(parent_scene_id,
                                                 decision["candidates"])
                parent_candidates.setdefault(bind_scene_id, decision["candidates"])
            # ---- P42-1：**候选域内容排除** + P44-1：**语义锚定过滤**（逐景）----
            if (decision.get("candidates") or []) and (_ban or _anchor):
                _cb = len(decision["candidates"])
                _kept, _rej_ban, _rej_anchor = [], 0, 0
                for c in decision["candidates"]:
                    if _ban and _banned(c):
                        _rej_ban += 1
                        continue
                    if not _anchor_ok(c, bind_scene_id):
                        _rej_anchor += 1
                        continue
                    _kept.append(c)
                decision["candidates"] = _kept
                _ca = len(_kept)
                if _ca != _cb:
                    decision["content_excluded_candidates"] = _rej_ban
                    if _rej_anchor:
                        decision["anchor_rejected"] = _rej_anchor
                    decision["candidates_total"] = _ca
                    if not _ca:
                        decision["selected_asset"] = None
                        decision["content_exclusion_note"] = (
                            "P42-1/P44-1：该景全部候选被**内容排除/语义锚定**过滤 ⇒ "
                            "空域（如实登记，不硬造）")
            scenes.append({
                "scene_id": bind_scene_id,
                "scene_id_synthetic": scene_id,
                "parent_scene_id": (parent_scene_id or None),
                "binding_source": binding_source,
                "segment_index": i,
                "chapter": seg.get("chapter") or "",
                "narration_chars": len(strip_claims(seg.get("narration", ""))),
                "start_s": round(cursor, 3),
                "end_s": round(cursor + dur, 3),
                "retrieval_query": query[:300],
                "matched_tokens": decision["candidates"][0]["matched_tokens"]
                if decision["candidates"] else [],
                # ---- Phase 2-C：分类 + 降级 + 完整追溯 ----
                **{k: decision[k] for k in
                   ("original_requirement", "candidates", "candidates_total",
                    "insufficiency_class", "fallback_state", "fallback_action",
                    "fallback_reason", "selected_asset", "selection_reason", "needs_hitl",
                    "allowed_in_final_render", "excluded_candidates", "license_pending")},
                # ---- 4.x Phase 4-C：选材来源与人工决定证据（无人工决定时分别为 automatic/None）----
                "selection_source": decision.get("selection_source", "automatic"),
                "human_selection": decision.get("human_selection"),
                # 兼容 Phase 2-A/B 字段（selected_asset 同构）
                "entered_timeline": decision["allowed_in_final_render"],
            })
            cursor += dur
        # ---- P33-2：**分配纪律**（授权书）----
        #  · 每素材上屏景数 ≤ `max_scenes_per_asset`（默认 None ⇒ 不限制，既有行为逐字不变）；
        #  · 相邻景禁用同一素材（`forbid_adjacent_same_asset`，默认关闭）。
        # 纪律在**自动选材之后**施加：超限/相邻冲突的景改选「该景候选中、当前用量最少」的素材；
        # **无可用替代 ⇒ 保留原分配**（不造假、不静默丢弃），并把事实记入 `allocation` 供审计。
        _cap = pol.get("max_scenes_per_asset")
        _no_adj = bool(pol.get("forbid_adjacent_same_asset"))
        # P35-3：**同素材最小间距 ≥ N 景**（升级自「禁相邻」）。
        # `min_scene_gap = 3` ⇒ 同素材两次上屏之间至少隔 3 个景（i 与 [i-N, i+N] 内不得同素材）。
        # 默认 None/0 ⇒ 不生效（既有行为逐字不变）。
        try:
            _gap = int(pol.get("min_scene_gap") or 0)
        except (TypeError, ValueError):
            _gap = 0
        alloc = {"cap": _cap, "forbid_adjacent": _no_adj, "min_scene_gap": _gap or None,
                 "content_exclusions": {"banned": sorted(_ban),
                                        "evidence": _exclusion_evidence,
                                        "error": _exclusion_error},
                 "reassigned": [], "unresolved": [], "final_counts": {},
                 "enabled": bool(_cap or _no_adj or _gap)}
        if (_cap or _no_adj or _gap) and scenes:
            # ---- P44-1：**锚定守卫**（最终防线）----
            # 任何来源（自动选材 / 具名绑定 / 求解器改派）落在**越界**的锚定素材上，
            # 都在此处**清空该景素材**（回落纯色卡并如实登记），而不是让它进片。
            def _aid(s):
                return ((s.get("selected_asset") or {}).get("asset_id"))

            def _too_close(i, cid, span):
                """景 i 与 [i-span, i+span] 内其它景是否同素材（间距约束）。"""
                if not span:
                    return False
                lo, hi = max(0, i - span), min(len(scenes) - 1, i + span)
                for j in range(lo, hi + 1):
                    if j != i and _aid(scenes[j]) == cid:
                        return True
                return False

            counts = {}
            for s in scenes:
                a = _aid(s)
                if a:
                    counts[a] = counts.get(a, 0) + 1
            for idx, s in enumerate(scenes):
                a = _aid(s)
                if not a:
                    continue
                over = bool(_cap) and counts.get(a, 0) > int(_cap)
                adj = (_no_adj and idx > 0 and _aid(scenes[idx - 1]) == a)
                gap_bad = _too_close(idx, a, _gap)
                if not (over or adj or gap_bad):
                    continue
                # 该景候选中择优改选。两级偏好（**逐级放宽，且每级都如实记账**）：
                #   ① 严格级：未超限 **且** 满足相邻/间距约束 ⇒ 取当前用量最少者；
                #   ② 放宽级：只要求未超限（允许违反相邻/间距，仅当严格级无解）。
                # 两级皆无解 ⇒ 记 `unresolved` 并**保留原分配**（不造假、不静默丢弃）。
                def _pick(strict: bool):
                    best, best_n = None, None
                    for c in (s.get("candidates") or []):
                        cid = c.get("asset_id")
                        if not cid or cid == a or c.get("usable") is False:
                            continue
                        if _cap and counts.get(cid, 0) >= int(_cap):
                            continue
                        if strict:
                            if _no_adj and idx > 0 and _aid(scenes[idx - 1]) == cid:
                                continue
                            if _no_adj and idx + 1 < len(scenes) and _aid(scenes[idx + 1]) == cid:
                                continue
                            if _gap and _too_close(idx, cid, _gap):
                                continue
                        n = counts.get(cid, 0)
                        if best is None or n < best_n:
                            best, best_n = c, n
                    return best

                best = _pick(strict=True) if (_no_adj or _gap) else _pick(strict=False)
                _level = "strict"
                if best is None:
                    best = _pick(strict=False)
                    _level = "relaxed_adjacency"
                if best is None:
                    alloc["unresolved"].append({"scene_id": s.get("scene_id"),
                                                "asset": a,
                                                "why": ("over_cap" if over else
                                                        ("adjacent_same" if adj
                                                         else "gap_too_close")),
                                                "note": "候选中无未超限的替代素材"})
                    continue
                counts[a] = counts.get(a, 0) - 1
                counts[best["asset_id"]] = counts.get(best["asset_id"], 0) + 1
                s["selected_asset"] = selection_projection(best)
                s["allocation_reassigned_from"] = a
                s["allocation_reason"] = ("P35-3 分配纪律（{}）：{}".format(
                    _level, "超每素材上限" if over else
                    ("相邻景同素材" if adj else "同素材间距不足")))
                alloc["reassigned"].append({"scene_id": s.get("scene_id"), "from": a,
                                            "to": best["asset_id"],
                                            "level": _level,
                                            "why": ("over_cap" if over else
                                                    ("adjacent_same" if adj
                                                     else "gap_too_close"))})
            alloc["final_counts"] = counts

            # ---- P56-2：**钉定分配回灌**（单变量对照的强制手段）----
            # 授权书 §2：F10.1 = **F9 的 assignment 钉定** + F10 的新字幕
            # ⇒ 与 F9 的**唯一差异 = 字幕层**，使终审「字幕跟嘴」不被画面变化污染。
            # 外部开关 `logs/p56_2_f9_pins.json`（存在即生效）：把 F9 逐景已选素材
            # **强制写回** `selected_asset`（在锚定守卫**之前**，故锚定仍可兜底）。
            # ---- P57-1 **缺陷修复（silent-kill）**：本块引用 `_AL` 计算指纹，但
            # `from ...core import allocation as _AL` 在其后（P40-1 块）才执行
            # ⇒ UnboundLocalError 被 except 吞成 `pinned_assignment_error` 字段
            # ⇒ **写回虽已完成、记账与指纹全丢**，且自 P56-2 起该机制**从未真正
            # 生效过**（F10.1 的 36/36 一致实为确定性求解器复现，非 pins 功劳）。
            # 修法：`_AL` 在块内显式导入；写回结果必须留痕（applied/missing）。
            _pins_applied, _pins_missing = 0, []
            try:
                from ...core import allocation as _AL
                _pf = _pins_file_for(task.get("project_id"))
                if _pf.is_file():
                    _pins = (json.loads(_pf.read_text(encoding="utf-8"))
                             .get("pins") or {})
                    _pool_by_sha = {}
                    for _a in (asset_pool or []):
                        _sh = str(_a.get("sha256") or "")
                        if _sh:
                            _pool_by_sha[_sh[:12]] = _a
                    for _s in scenes:
                        _sid = _s.get("scene_id")
                        _want = str(_pins.get(_sid) or "")[:12]
                        if not _want:
                            continue
                        _hit = _pool_by_sha.get(_want)
                        if _hit is None:
                            _pins_missing.append({"scene_id": _sid, "sha12": _want})
                            continue
                        _s["selected_asset"] = selection_projection(_hit)
                        _s["pinned_from"] = "F9 (p56_2_f9_pins.json)"
                        _pins_applied += 1
                    alloc["pinned_assignment"] = {
                        "source": "F9", "applied": _pins_applied,
                        "missing": _pins_missing,
                        "fingerprint": _AL.assignment_fingerprint(
                            {s.get("scene_id"): str(
                                (s.get("selected_asset") or {}).get("sha256") or "")[:12]
                             for s in scenes})}
            except Exception as _pe:                                            # noqa: BLE001
                alloc["pinned_assignment_error"] = "{}: {}".format(
                    type(_pe).__name__, str(_pe)[:120])

            # ---- P44-1：**锚定守卫**（最终清剿）----
            # 任何来源（自动选材 / 具名绑定 / 父景回退 / 求解器改派）若把**越界的
            # 锚定素材**放到某景，都在此处清空该景素材（回落纯色卡并**如实登记**），
            # 而不是让它进片。踩坑：绑定与自动选材都绕过过锚定过滤（实测 4 处越界）。
            _anchor_cleared = []
            for _s in scenes:
                _a = (_s.get("selected_asset") or {})
                if _a.get("asset_id") and not _anchor_ok(_a, _s.get("scene_id")):
                    _anchor_cleared.append({"scene_id": _s.get("scene_id"),
                                            "asset": _a.get("asset_id")})
                    _s["selected_asset"] = None
                    _s["anchor_rejected"] = (_s.get("anchor_rejected") or 0) + 1
                    _s["selection_reason"] = (
                        "P44-1 锚定守卫：素材越出语义锚定 ⇒ 清空（回落纯色卡）")
            alloc["anchor_cleared"] = _anchor_cleared

            # ---- P40-1：**全局约束满足后处理**（替代单步贪心）----
            # 根因（实测）：上面这套「单步贪心」遇到冲突时只试**一次**替代，无解即记
            # `unresolved` 并**保留违反分配**；且**父景绑定回退**会把同一素材强绑给同父段的
            # 多个派生景 ⇒ 与「间距 ≥3」**结构性冲突**。实盘结果：cap 4>3、间距违例 10。
            # 处置：改用 `core.allocation.satisfy` 做**最小冲突局部搜索**（固定 seed），
            # 硬约束全部编码为代价；**不可行时返回最小违例解 + 违例清单**（不静默违反）。
            try:
                from ...core import allocation as _AL
                _ids = [s.get("scene_id") for s in scenes]
                # P47-3：抽象景 → 其生成素材（家族 G，优先取用）
                _gen_pref = {}
                try:
                    _gb = json.loads((R_GEN_BATCH).read_text(encoding="utf-8")) \
                        if R_GEN_BATCH.is_file() else {}
                    for _it in (_gb.get("items") or []):
                        if _it.get("ok") and _it.get("sha256"):
                            _gen_pref[str(_it["scene_id"])] = "asset_{}".format(
                                str(_it["sha256"])[:12])
                except Exception:                                               # noqa: BLE001
                    _gen_pref = {}
                _opts = {}
                for _s in scenes:
                    _cur = (s_a := ((_s.get("selected_asset") or {}).get("asset_id")))
                    _cs = [c.get("asset_id") for c in (_s.get("candidates") or [])
                           if c.get("asset_id") and c.get("usable", True) is not False]
                    # ---- P44-1：**锚定过滤必须在求解前生效** ----
                    # 踩坑：首版只在求解**后**用「锚定守卫」清空越界结果 ⇒ 求解器
                    # 在**含越界项的选项空间**里优化 ⇒ 得解后再被清空 ⇒ 大量景塌到
                    # 同一素材（cap 7、家族份额 58%）。正确做法是**先把越界项从选项
                    # 空间剔除**，让求解器在**合法空间**内求最优。
                    _all_by_id = {c.get("asset_id"): c for c in (_s.get("candidates") or [])}
                    if not _anchor_ok({"asset_id": _cur}, _s.get("scene_id")):
                        _cur = None
                    _cs = [a for a in _cs
                           if _anchor_ok(_all_by_id.get(a) or {"asset_id": a},
                                         _s.get("scene_id"))]
                    # ---- P47-3：**抽象景优先 G 家族**（生成概念插图）----
                    # 授权书 §3 要求「抽象景优先 G」。**不**用硬绑定表达——实测 15 条
                    # 硬绑定会把 G 顶到 **41.7%**，与「G ≤33%」门**数学上冲突**
                    # （15/36 = 41.7% > 33%）。改为**候选择序**：把该景对应的生成素材
                    # 置首，由分配器在满足 cap/间距/家族门的前提下**按优先级取用**。
                    if _gen_pref and _s.get("scene_id") in _gen_pref:
                        _g = _gen_pref[_s["scene_id"]]
                        _cs = [_g] + [a for a in _cs if a != _g]
                    if _cur and _cur not in _cs:
                        _cs = [_cur] + _cs
                    # ---- P47-3：**空候选域回填**（踩坑修复）----
                    # 实测：锚定/内容过滤后部分景候选为空 ⇒ 该景**不进 `_opts`** ⇒
                    # 求解器把它当「固定空」，无解可挑 ⇒ 可用面被压缩，G 反而被推到 72%。
                    # 处置：候选为空时**回填全池**（仍过锚定/排除过滤），给求解器自由度。
                    if not _cs:
                        _cs = [a.get("asset_id") for a in (asset_pool or [])
                               if a.get("asset_id")
                               and _anchor_ok(a, _s.get("scene_id"))]
                        if _s.get("scene_id") in _gen_pref:
                            _g0 = _gen_pref[_s["scene_id"]]
                            _cs = [_g0] + [a for a in _cs if a != _g0]
                    if _cs:
                        _opts[_s.get("scene_id")] = _cs
                _init = {s.get("scene_id"): ((s.get("selected_asset") or {}).get("asset_id"))
                         for s in scenes}
                # 动机：16 张素材中 8 张同属「纸面符号」家族 ⇒ **ID 级约束无法对冲观感轮番**。
                _fam_map, _fam_share = None, None
                _fam_share_by, _sub_map, _no_sub_adj = None, None, False
                try:
                    _fmf = ROOT / "config" / "family_map.json"
                    if _fmf.is_file():
                        _fm = (json.loads(_fmf.read_text(encoding="utf-8"))
                               .get("family_map") or {})
                        if _fm.get("enabled", True):
                            _fam_map = dict(_fm.get("families") or {})
                            _fam_share = float(_fm.get("max_family_share") or 0.33)
                            # ---- P46-2 **双轨门**：按家族分别设上限 ----
                            _fam_share_by = dict(_fm.get("max_share_by_family") or {})
                            # ---- P46-2 **子族**（E1/E2）+ 相邻禁同子族 ----
                            _sub_map = dict(_fm.get("sub_families") or {})
                            _sub_map.pop("_note", None)
                            _no_sub_adj = bool(_fm.get("forbid_adjacent_same_sub_family"))
                except Exception:                                               # noqa: BLE001
                    _fam_map, _fam_share = None, None
                # ---- P56-1 **废除「越界弃种」**（授权书 §1）----
                # **背景**：P47-3 我加过「种子若已违反份额门 ⇒ 丢弃种子」。
                # 后果：种子是否被丢**取决于输入状态**，于是**同一输入两次运行的解不同**
                # ⇒ **分配不可复现**（P55 实测：F10 与 F9 画面仅 4/36 景一致，
                # 使「单变量字幕验证」失效）。监理已把**分配不可复现升格为正确性缺陷**。
                # **处置**：**保留 `initial` 种子**（不弃种）；若份额越门，
                # **求解后如实报告**，让**门的裁决权在门** —— 求解器不自我审查。
                # 另：固定 `seed` 与搜索预算，保证同输入 ⇒ 同解。
                _seed = dict(_init)
                _SOLVER_SEED = 20261002          # 与 `core.allocation.SEED` 同源、显式钉定
                _SOLVER_RESTARTS, _SOLVER_ITERS = 40, 1500
                # ---- P56-1 **确定性自检**：同输入连跑两次，assignment 必须逐景一致 ----
                if _fam_map is not None or True:
                    _kw = dict(cap=int(_cap or 3), gap=int(_gap or 3),
                               fam_map=_fam_map, max_family_share=_fam_share,
                               max_share_by_family=_fam_share_by,
                               sub_map=_sub_map,
                               forbid_adjacent_same_sub=_no_sub_adj,
                               restarts=_SOLVER_RESTARTS, iters=_SOLVER_ITERS,
                               seed=_SOLVER_SEED)
                    _a1 = _AL.satisfy(_ids, _opts, initial=_seed, **_kw)
                    _a2 = _AL.satisfy(_ids, _opts, initial=_seed, **_kw)
                    _f1 = _AL.assignment_fingerprint(_a1.get("assignment") or {})
                    _f2 = _AL.assignment_fingerprint(_a2.get("assignment") or {})
                    alloc["determinism"] = {
                        "run1_fingerprint": _f1, "run2_fingerprint": _f2,
                        "deterministic": _f1 == _f2,
                        "seed_used": bool(_seed), "solver_seed": _SOLVER_SEED,
                        "restarts": _SOLVER_RESTARTS, "iters": _SOLVER_ITERS}
                    if _f1 != _f2:
                        raise RuntimeError(
                            "P56-1 分配确定性自检失败（fail-closed）："
                            "同输入两次求解 assignment 指纹不一致 {} vs {}".format(
                                _f1[:16], _f2[:16]))
                _res = _a1
                # 门自行裁决（不弃种、不静默）：份额越门照实留档
                if (_res.get("report") or {}).get("family_share_violations"):
                    alloc["share_gate_verdict"] = {
                        "violations": _res["report"]["family_share_violations"],
                        "note": ("P56-1：**不弃种、不静默** —— 门的裁决权在门，"
                                 "不在求解器的自我审查")}
                # ---- P48-1：**生产路径输入转储**（供与独立路径逐字段 diff）----
                try:
                    import sys as _sys
                    _dd = ROOT / "docs" / "regression_2x"
                    if str(_dd) not in _sys.path:
                        _sys.path.insert(0, str(_dd))
                    from solver_input_dump import dump_solver_input as _dump
                    alloc["solver_input_dump"] = _dump(
                        ROOT / "output" / "p40_probe" / "solver_input_production.json",
                        source="production", ids=_ids, options=_opts,
                        cap=int(_cap or 3), gap=int(_gap or 3),
                        fam_map=_fam_map, max_family_share=_fam_share,
                        max_share_by_family=_fam_share_by, sub_map=_sub_map,
                        forbid_adjacent_same_sub=_no_sub_adj,
                        initial=_seed, restarts=40, iters=1500, seed=None,
                        anchor_map=_anchor,
                        extra={"asset_pool_size": len(asset_pool or []),
                               "gen_pref": _gen_pref,
                               "seed_rejected": bool(alloc.get("seed_rejected")),
                               "solver_report": _res.get("report")})["input_fingerprint"]
                except Exception as _de:                                        # noqa: BLE001
                    alloc["solver_input_dump_error"] = "{}: {}".format(
                        type(_de).__name__, str(_de)[:140])
                _by_id = {c.get("asset_id"): c for _s in scenes
                          for c in (_s.get("candidates") or []) if c.get("asset_id")}
                _changed = 0
                for _s in scenes:
                    _sid = _s.get("scene_id")
                    _new = _res["assignment"].get(_sid)
                    _old = (_s.get("selected_asset") or {}).get("asset_id")
                    if _new and _new != _old:
                        _src = _by_id.get(_new)
                        if _src is not None:
                            _s["selected_asset"] = selection_projection(_src)
                        _s["allocation_reassigned_from"] = _old
                        _s["allocation_reason"] = "P40-1 全局约束满足（cap/gap/相邻）"
                        alloc["reassigned"].append({"scene_id": _sid, "from": _old,
                                                    "to": _new, "level": "global_satisfy",
                                                    "why": "约束满足"})
                        _changed += 1
                alloc["global_satisfy"] = {
                    "method": "min-conflicts local search (core.allocation.satisfy)",
                    "pass": _res["pass"], "changed": _changed,
                    **{k: v for k, v in _res["report"].items()},
                }
                alloc["final_counts"] = _res["usage"]
                alloc["unresolved"] = [
                    {"scene_id": k, "asset": v, "why": "over_cap_after_satisfy"}
                    for k, v in (_res["report"]["cap_violations"] or {}).items()]
            except Exception as _exc:                                            # noqa: BLE001
                alloc["global_satisfy_error"] = "{}: {}".format(
                    type(_exc).__name__, str(_exc)[:160])

            # ---- P57-2 **pins 终局强制**（「分配零改动」的硬保证）----
            # P56-2 的 pins 写回在 P40-1 求解器**之前**，而求解器可能把已钉定的景
            # **再次改派**（实测 2026-10-11 14:38 渲染：applied=36 仍被改走 26 景；
            # 求解器跨进程行为受 PYTHONHASHSEED 影响——P56-1 的确定性自检只覆盖
            # 同进程两次求解）。P56-2 的登记语义是「**强制**写回」，故在求解器
            # 之后按同一 pins 文件**再强制一次**，并对**全部景**复跑锚定守卫
            # （与上方 679 同规则）；`pinned_final` 留痕。
            try:
                _pf2 = _pins_file_for(task.get("project_id"))
                if _pf2.is_file():
                    _pins2 = (json.loads(_pf2.read_text(encoding="utf-8"))
                              .get("pins") or {})
                    _by_sha2 = {str(_a.get("sha256") or "")[:12]: _a
                                for _a in (asset_pool or [])}
                    _re_pin, _re_missing = 0, []
                    for _s in scenes:
                        _want2 = str(_pins2.get(_s.get("scene_id")) or "")[:12]
                        if not _want2:
                            continue
                        _hit2 = _by_sha2.get(_want2)
                        if _hit2 is None:
                            _re_missing.append({"scene_id": _s.get("scene_id"),
                                                "sha12": _want2})
                            continue
                        _cur2 = str(((_s.get("selected_asset") or {}).get("sha256"))
                                    or "")
                        if _cur2[:12] == _want2:
                            continue
                        _s["selected_asset"] = selection_projection(_hit2)
                        _s["pinned_final"] = "P57-2 pins 终局强制（覆盖求解器改派）"
                        _re_pin += 1
                    _re_clear = []
                    for _s in scenes:
                        _a2 = (_s.get("selected_asset") or {})
                        if _a2.get("asset_id") and not _anchor_ok(_a2,
                                                                  _s.get("scene_id")):
                            _re_clear.append({"scene_id": _s.get("scene_id"),
                                              "asset": _a2.get("asset_id")})
                            _s["selected_asset"] = None
                            _s["selection_reason"] = (
                                "P44-1 锚定守卫（pins 终局后复跑）：素材越出语义锚定"
                                " ⇒ 清空（回落纯色卡）")
                    alloc["pinned_final"] = {"re_pinned": _re_pin,
                                             "missing": _re_missing,
                                             "anchor_cleared": _re_clear}
            except Exception as _pe2:                                            # noqa: BLE001
                alloc["pinned_final_error"] = "{}: {}".format(
                    type(_pe2).__name__, str(_pe2)[:120])
        if scenes:
            # 末尾 2s 收尾（与既有 total 约定一致）：把最后一个镜头延长到全片结束
            scenes[-1]["end_s"] = round(max(scenes[-1]["end_s"], cursor + 2.0), 3)
        # P33-2：分配纪律证据**以 `.allocation` 携带**（`MaterialTimeline` 是 `list` 子类 ⇒
        # 既有调用方零改动；且**不再用 try/except 吞异常**，避免证据静默丢失）。
        tl_out = MaterialTimeline(scenes)
        tl_out.allocation = alloc
        return tl_out

    @staticmethod
    def _sanitize_params(params: dict) -> dict:
        """归一化 LLM 给出的 render_params（3.x Phase 1 修复）。

        实测缺陷：真实 LLM 会写出人类可读的编码器描述
        `"H.264 (libx264, High profile, CRF 18, yuv420p)"`，直接传给 `-c:v` 会
        `Unknown encoder` → render 任务失败（在 C 组真实运行中复现）。
        ffmpeg 只接受编码器 id，因此做白名单归一化；分辨率/帧率同样做格式校验。
        """
        p = dict(params or {})
        codec = str(p.get("codec") or "").strip().lower()
        known = (("libx264", "libx264"), ("h.264", "libx264"), ("h264", "libx264"),
                 ("avc", "libx264"), ("x264", "libx264"),
                 ("libx265", "libx265"), ("h.265", "libx265"), ("h265", "libx265"),
                 ("hevc", "libx265"), ("x265", "libx265"))
        picked = next((v for k, v in known if k in codec), None)
        p["codec"] = picked or "libx264"
        res = str(p.get("resolution") or "").strip()
        if not re.match(r"^\d{2,5}x\d{2,5}$", res):
            p["resolution"] = "1920x1080"
        try:
            fps = int(float(p.get("fps") or 30))
        except (TypeError, ValueError):
            fps = 30
        p["fps"] = max(1, min(60, fps))
        p["format"] = "mp4"
        return p

    def _render(self, engine, task: dict) -> None:
        from ...tools.ffmpeg_tool import FFmpegTool
        from ...tools.base import ToolContext, ToolError

        # 收集剪辑方案产物
        plan = None
        for dep in task.get("dependencies", []):
            dep_task = engine.db.get_task(dep)
            for art_id in dep_task.get("artifacts", [])[::-1]:
                art = engine.db.get_artifact(art_id)
                if art["type"] in ("editing_plan_output", "editing_plan"):
                    with open(art["path"], encoding="utf-8") as fh:
                        plan = json.load(fh)
                    break
            if plan is not None:
                break
        params = (plan or {}).get("render_params", {}) if plan else {}
        params_raw = dict(params or {})
        params = self._sanitize_params(params_raw)
        resolution = params.get("resolution", "1280x720")
        fps = params.get("fps", 30)
        out_rel = f"output/{task['task_id']}_draft.mp4"

        # 沿依赖图回溯寻找脚本产物（BFS），用于烧录真实旁白字幕
        script = None
        queue = list(task.get("dependencies", []))
        seen = set()
        while queue:
            dep = queue.pop(0)
            if dep in seen:
                continue
            seen.add(dep)
            dep_task = engine.db.get_task(dep)
            if dep_task is None:
                continue
            for art_id in dep_task.get("artifacts", [])[::-1]:
                art = engine.db.get_artifact(art_id)
                if art["type"] == "script_output":
                    with open(art["path"], encoding="utf-8") as fh:
                        script = json.load(fh)
                    break
            if script is not None:
                break
            queue.extend(dep_task.get("dependencies", []))

        ctx = ToolContext(role="editing", project_id=task["project_id"],
                          project_dir=engine.project_dir(task["project_id"]),
                          db=engine.db, config=engine.config)
        tool = FFmpegTool()

        # 沿依赖图回溯寻找配音产物（BFS），存在则用真实旁白音轨
        # 3.x Phase 2-B.1：同时保留**完整 voice 产物**（逐段状态/时长契约）供渲染前闸门使用
        narration_audio, narration_payload = None, None
        queue2 = list(task.get("dependencies", []))
        seen2 = set()
        while queue2:
            dep = queue2.pop(0)
            if dep in seen2:
                continue
            seen2.add(dep)
            dep_task = engine.db.get_task(dep)
            if dep_task is None:
                continue
            for art_id in dep_task.get("artifacts", [])[::-1]:
                art = engine.db.get_artifact(art_id)
                if art["type"] == "voice_output":
                    with open(art["path"], encoding="utf-8") as fh:
                        narration_payload = json.load(fh)
                    narration_audio = narration_payload.get("audio")
                    break
            if narration_payload is not None:
                break
            queue2.extend(dep_task.get("dependencies", []))

        # ---- Duration Contract v2：**audio_time_base 是 narration/timeline 权威** ----
        # `declared duration_s` 只作规划估计；场景窗口/字幕/混音/门禁全部由实际 TTS 时长推导。
        # **兼容开关**：仅当 voice 产物带 v2 权威字段（udio_time_base_s）时启用 v2；
        # 历史 v1 产物 / 合成 fixture 保持 v1 语义（**不追溯破坏**已产出的旧链路）。
        v2_plan, v2_windows, v2_time_base = None, [], None
        if narration_payload is not None and narration_payload.get("audio_time_base_s"):
            v2_plan = narration_plan(script, narration_payload,
                                     config=getattr(engine, "config", None))
            v2_windows = v2_plan.get("segments") or []
            v2_time_base = v2_plan.get("audio_time_base_s")

        # 3.x Phase 1 Part B：先解析 retrieval 命中的**本地 ingest 素材**（图片），供渲染使用
        mat_mode, mat_n, cands = "unknown", 0, []
        q3 = list(task.get("dependencies", []))
        seen3 = set()
        retr_payload = {}
        while q3:
            d3 = q3.pop(0)
            if d3 in seen3:
                continue
            seen3.add(d3)
            d3t = engine.db.get_task(d3)
            if d3t is None:
                continue
            for aid in d3t.get("artifacts", [])[::-1]:
                a3 = engine.db.get_artifact(aid)
                if a3["type"] == "retrieval_candidates":
                    with open(a3["path"], encoding="utf-8") as fh:
                        r3 = json.load(fh)
                    mat_mode = r3.get("material_mode", "unknown")
                    cands = r3.get("candidates") or []
                    mat_n = int(r3.get("candidates_total") or len(cands))
                    retr_payload = r3
                    break
            if mat_mode != "unknown":
                break
            q3.extend(d3t.get("dependencies", []))

        import hashlib as _hashlib
        media_dir = engine.project_dir(task["project_id"]) / "media"
        mat_policy = policy_from_config(engine.config)

        # 3.x Phase 2-A/B：镜头级素材池（每个素材带稳定标识：asset_id/source/sha256/path/score）
        # 3.x Phase 2-C：同时判定**可用性**（解码/尺寸/字节）——不可用素材绝不进入渲染
        # 3.x Phase 2-D：外部候选带 provider/source/license；被 provider 层拒收的候选单列（含许可证未明）
        excluded_pool = []
        for c in (retr_payload.get("external_rejected") or []):
            excluded_pool.append({
                "name": c.get("name"), "ext": c.get("ext"), "provider": c.get("provider"),
                "source_id": c.get("source_id"), "source_url": c.get("source_url"),
                "license": c.get("license"), "error_code": c.get("error_code"),
                "error_detail": c.get("error_detail"), "needs_hitl": c.get("needs_hitl"),
            })
        asset_pool = []
        licence_blocked = []            # Phase 3-A：因许可原因不得入片的候选（纵深防御留痕）
        _ffprobe = _ffprobe_exe(getattr(engine, "config", None))
        for c in cands:                       # 已按 match_score 降序
            rel = str(c.get("path") or "")
            p = (media_dir / rel).resolve()
            # ---- P58-2：**视频条候选**（media_type=video 显式声明才收；媒体池向后兼容）----
            _is_video = str(c.get("media_type") or "").lower() == "video"
            _img_ok = p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")
            _vid_ok = _is_video and p.suffix.lower() in (".mp4", ".webm", ".mov")
            if not (p.is_file() and (_img_ok or _vid_ok)):
                continue
            sha = _hashlib.sha256(p.read_bytes()).hexdigest()
            usable, why, w, h = True, None, None, None
            _vdur = None
            # Phase 3-A 门禁①：外部素材中 RESTRICTED/UNKNOWN 许可**不得入片**
            # （provider 层已拒收，这里再查一次；本地自带素材不在此门禁范围内）
            lic_block = (license_block_reason(c, require_license=bool(mat_policy.get(
                "license_required", True)))
                if license_gate_applies(c, require_license=bool(mat_policy.get(
                    "license_required", True))) else None)
            if lic_block:
                usable, why = False, lic_block
                licence_blocked.append({"name": c.get("name"), "provider": c.get("provider"),
                                        "source_id": c.get("source_id"),
                                        "license": c.get("license"),
                                        "license_class": c.get("license_class"),
                                        "error_code": lic_block})
            if _vid_ok:
                # P58-2：视频可用性 = **ffprobe**（宽度/高度/时长 ≥3s；可解码）。
                # PIL 不认视频 ⇒ 走独立探测分支；探测失败 fail-closed（usable=False）。
                usable, why, w, h, _vdur = _probe_video_usable(p, _ffprobe)
                if usable and _vdur is not None and _vdur < 3.0:
                    usable, why = False, "VIDEO_TOO_SHORT: {:.2f}s < 3.0s".format(_vdur)
            else:
                try:
                    from PIL import Image as _Image
                    with _Image.open(p) as im:
                        w, h = im.size
                        im.verify()
                except Exception as exc:                   # noqa: BLE001 —— 记录原因，不猜
                    usable, why = False, "ASSET_DECODE_FAILED: {}: {}".format(
                        type(exc).__name__, str(exc)[:80])
            if usable and p.stat().st_size <= 0:
                usable, why = False, "ASSET_EMPTY_FILE"
            if usable and (w is None or h is None or w < int(mat_policy["min_asset_width"])
                           or h < int(mat_policy["min_asset_height"])):
                usable = False
                why = "ASSET_TOO_SMALL: {}x{} < {}x{}".format(
                    w, h, mat_policy["min_asset_width"], mat_policy["min_asset_height"])
            asset_pool.append({
                "asset_id": "asset_" + sha[:12],
                "name": c.get("name") or p.name,
                "source": "local_ingest" if c.get("provider") in (None, "", "local_ingest")
                else "external",
                "sha256": sha,
                "path": str(p),
                "relative_path": rel,
                "bytes": p.stat().st_size,
                "license": c.get("license"),
                "retrieval_match_score": c.get("match_score"),
                "usable": usable,
                "unusable_reason": why,
                "width": w,
                "height": h,
                "media_type": ("video" if _vid_ok else "image"),
                "duration_s": _vdur,
                "used_by_scenes": [],
                # ---- Phase 2-D：来源与许可（逐镜头可追溯）----
                "provider": c.get("provider") or "local_ingest",
                "source_id": c.get("source_id"),
                "source_url": c.get("source_url"),
                "attribution": c.get("attribution"),
                "usage_restrictions": c.get("usage_restrictions"),
                "license_cleared": c.get("license_cleared"),
                # Phase 3-A：许可类别（纵深防御 + 交付物）——优先用 provider 给的类别，否则按声明值机械分类
                "license_class": c.get("license_class") or classify_license(c.get("license"))[0],
                "needs_hitl": bool(c.get("needs_hitl")),
                "media_type": c.get("media_type"),
                "verified": bool(c.get("verified", True)),
            })
        # 兼容字段（Phase 1 语义）：单素材路径仍记录首个可用素材
        img = (media_dir / asset_pool[0]["relative_path"]) if asset_pool else None
        mat_used = ({k: asset_pool[0][k] for k in
                     ("asset_id", "name", "path", "relative_path", "sha256", "bytes",
                      "retrieval_match_score")} if asset_pool else None)

        # 视觉计划（用于镜头级匹配的补充查询文本）
        shots, q5 = [], list(task.get("dependencies", []))
        seen5 = set()
        while q5:
            d5 = q5.pop(0)
            if d5 in seen5:
                continue
            seen5.add(d5)
            d5t = engine.db.get_task(d5)
            if d5t is None:
                continue
            for aid in d5t.get("artifacts", [])[::-1]:
                a5 = engine.db.get_artifact(aid)
                if a5["type"] == "visual_plan_output":
                    with open(a5["path"], encoding="utf-8") as fh:
                        shots = (json.load(fh).get("shots") or [])
                    break
            if shots:
                break
            q5.extend(d5t.get("dependencies", []))

        # Phase 2-D：外部 provider 提供过候选（即便全部被拒）同样算"提供过素材"
        material_provided = (bool(retr_payload.get("material_provided"))
                             or mat_mode in ("local_ingest", "external", "mixed"))
        # ---- 4.x Phase 4-C：读取人工选定（只读；无决定则行为与 3.x 完全一致）----
        human_sel: dict = {}
        try:
            human_sel = latest_selections_from_conn(engine.db.conn, task["project_id"])
        except Exception as exc:                          # noqa: BLE001 —— 读不到就按"无人工决定"处理
            human_sel = {}
            engine.emit(task["project_id"], "HUMAN_SELECTION_READ_FAILED", "editing",
                        task["task_id"], {"error": "{}: {}".format(type(exc).__name__,
                                                                   str(exc)[:120])})
        timeline = self._build_material_timeline(
            script, shots, asset_pool, policy=mat_policy,
            material_provided=material_provided,
            provider_requested=bool(retr_payload.get("external_requested")),
            excluded_pool=excluded_pool, human_selections=human_sel,
            engine=engine, task=task,
            segment_durations=([w["actual_s"] for w in v2_windows] if v2_windows else None),
            pause_budget_s=((v2_plan or {}).get("pause_budget_s") if v2_plan else None),
            trailing_pad_s=((v2_plan or {}).get("trailing_pad_s") if v2_plan else None),
        ) if script else []
        scenes_with_asset = [s for s in timeline if s.get("selected_asset")]
        normal_scenes = [s for s in timeline if s.get("fallback_state") == "LOCAL_INGEST"]
        insuff = assembly_class(timeline, material_provided=material_provided,
                                policy=mat_policy)
        if insuff["assembly_class"] == "ASSEMBLY_BLOCKED":
            assembly_state = "BLOCKED"
        elif timeline and len(normal_scenes) == len(timeline):
            assembly_state = "SUCCEEDED"          # 全部镜头正常命中
        elif scenes_with_asset:
            assembly_state = "PARTIAL"            # 有素材上屏但存在降级/占位镜头
        else:
            assembly_state = "PENDING"            # 无任何素材上屏（纯占位）

        # ---- 3.x Phase 2-C：素材不足闸门（在调用 ffmpeg 之前阻断）----
        # 已提供素材却无法完成装配 → 不产出一部"看起来成功"的成片；等待人工补充素材。
        if timeline:
            engine.emit(task["project_id"], "MATERIAL_TIMELINE", "editing", task["task_id"], {
                "scene_count": len(timeline),
                "scenes_with_asset": len(scenes_with_asset),
                "assets_used": sorted({s["selected_asset"]["asset_id"] for s in scenes_with_asset}),
                "fallback_scenes": [s["scene_id"] for s in timeline
                                    if s.get("fallback_state") != "LOCAL_INGEST"],
                # Phase 2-C 附加（纯新增字段，事件类型不变）
                "insufficiency_classes": {s["scene_id"]: s["insufficiency_class"]
                                          for s in timeline},
                "fallback_states": {s["scene_id"]: s["fallback_state"] for s in timeline},
                "assembly_class": insuff["assembly_class"],
                "material_assembly": assembly_state,
                # P33-2：分配纪律证据（每素材景数 / 改选 / 未解决）
                "material_allocation": (getattr(timeline, "allocation", None)
                                        or {"cap": None, "reassignments": 0}),
                "decisions": [{k: s[k] for k in
                               ("scene_id", "insufficiency_class", "fallback_state",
                                "fallback_reason", "selected_asset", "selection_reason",
                                "needs_hitl", "allowed_in_final_render")} for s in timeline],
            })
        if insuff["assembly_class"] == "ASSEMBLY_BLOCKED":
            detail = {"assembly_class": insuff["assembly_class"],
                      "assembly_reason": insuff["assembly_reason"],
                      "class_counts": insuff["class_counts"],
                      "degraded_scenes": insuff["degraded_scenes"],
                      "blocked_scenes": insuff["blocked_scenes"],
                      "material_mode": mat_mode,
                      "candidates_total": mat_n,
                      "policy": {k: mat_policy[k] for k in
                                 ("min_match_score", "low_match_policy", "asset_reuse_policy",
                                  "block_when_all_degraded")},
                      "scenes": [{"scene_id": s["scene_id"],
                                  "insufficiency_class": s["insufficiency_class"],
                                  "fallback_state": s["fallback_state"],
                                  "fallback_reason": s["fallback_reason"]} for s in timeline]}
            engine.emit(task["project_id"], "TASK_BLOCKED", "editing", task["task_id"],
                        {"error": insufficient_message(detail)[:500]}, human_visible=True)
            raise MaterialInsufficientError(insufficient_message(detail))

        # ---- 3.x Phase 2-B.1：渲染前旁白完整性闸门 + 时长契约（timeline 权威）----
        # 存在 voice_output（= 真的合成过旁白）时必须完整；不完整则在**调用 ffmpeg 之前**阻断，
        # 绝不产出一个"成功但被截短"的成片。无 voice_output（provider=none 计划模式）时保持原占位音行为。
        project_dir = engine.project_dir(task["project_id"])
        # Duration Contract v2：**audio_time_base 权威**（有 voice 产物时）；否则规划时基。
        timeline_total = (v2_time_base if v2_time_base
                          else (float(timeline[-1]["end_s"]) if timeline
                                else script_time_base_s(script)))
        tol = tolerance_ratio(engine.config)
        narration_state, narration_eval, dcontract = "ABSENT_PLAN_ONLY", None, None
        gate_report = None          # 6-A/M2：渲染前硬门报告（plan-only 路径保持 None）
        if narration_payload is not None:
            narration_state = "COMPLETE" if narration_payload.get("complete") else "INCOMPLETE"
            narration_eval = evaluate_narration(script, narration_payload)
            narr_dur = (probe_duration_s(ctx, project_dir / narration_audio)
                        if narration_audio else None)
            dcontract = duration_contract(timeline_total, narr_dur, tol)
            if v2_time_base:
                # v2：契约的 "timeline" 就是 audio_time_base ⇒ 不再有"短缺被 apad 掩盖"的语义
                dcontract["policy"] = "audio_time_base_v2"
                dcontract["planned_time_base_s"] = script_time_base_s(script)
                dcontract["audio_time_base_s"] = v2_time_base
                dcontract["audio_padded_to_timeline"] = False
                dcontract["padding_budget_s"] = (v2_plan.get("padding_policy") or {}
                                                 ).get("apad_allowed_s")
                dcontract["planning_drift"] = (v2_plan.get("planning_drift") or {}).get("delta_s")
            blocks = []
            if not narration_eval["complete"]:
                blocks.append("voice 产物不完整：" + "；".join(narration_eval["reasons"]))
            if narr_dur is None:
                blocks.append("旁白音轨时长不可探测（文件缺失/为空/ffprobe 失败）")
            if narr_dur is not None and dcontract["excess_s"] > 0 \
                    and not dcontract["within_tolerance"]:
                blocks.append("旁白 {:.1f}s 超过时间轴 {:.1f}s 且超出容差 {:.0%}（口播会被截断）".format(
                    dcontract["narration_duration_s"], dcontract["timeline_duration_s"], tol))
            # v2：旁白补齐（apad）只允许覆盖显式 pause budget —— 超出即 fail-closed（不再掩盖短缺）
            if v2_plan is not None and narr_dur is not None:
                _pad = max(float(v2_time_base or 0) - float(narr_dur), 0.0)
                _padchk = check_narration_padding(_pad, v2_plan)
                if not _padchk["ok"]:
                    blocks.append("旁白补齐 {:.1f}s 超出授权 pause budget {:.1f}s（{}）".format(
                        _padchk["padding_s"], _padchk["allowed_s"], _padchk["code"]))
            # ---- 6-A/M2：Production Integrity **渲染前硬门**（PI-1 覆盖率 / PI-2 双侧时长契约 / PI-6 边界漂移）----
            # 目的：**短旁白不得再被默认为合法完成**——`apad` 仍是合法音频处理，但不得掩盖"旁白覆盖不足"。
            # 仅在存在 voice 产物时启用（plan-only 无旁白路径保持既有行为）。
            # 传入**实测**旁白时长（与既有闸门同一来源：对 narration 音轨 ffprobe），
            # 避免与 voice 产物自报字段口径不一致；实测不可得时才回退到产物字段。
            _gate_cues = None
            if v2_plan is not None:
                from ...core.strip import strip_claims as _sc
                _gate_cues = core_captions.build_cues(
                    [{"narration": _sc(s.get("narration", "")), "duration_s": s.get("duration_s")}
                     for s in (script.get("segments") or [])
                     if _sc(s.get("narration", "")).strip()],
                    windows=(v2_windows or None))
            _int_gate = core_integrity.pre_render_gate(
                script.get("segments") or [], narration_payload, timeline_total,
                core_integrity.gate_policy(getattr(engine, "config", None)),
                narration_duration_s=narr_dur,
                narration_plan=v2_plan, cues=_gate_cues,
                narration_padding_s=(max(float(v2_time_base or 0) - float(narr_dur), 0.0)
                                     if (v2_time_base and narr_dur) else None))
            gate_report = _int_gate
            if _int_gate["blocked"]:
                detail = {"reasons": blocks + list(_int_gate["reasons"]),
                          "expected_segments": narration_eval["expected_segments"],
                          "successful_segments": narration_eval["successful_segments"],
                          "failed_segments": narration_eval["failed_indexes"],
                          "timeline_duration_s": dcontract["timeline_duration_s"],
                          "narration_duration_s": dcontract["narration_duration_s"],
                          "tolerance_ratio": tol,
                          "integrity_gate": _int_gate["detail"],
                          "policy": "timeline_authoritative + production_integrity_gate_v1"}
                engine.emit(task["project_id"], "TASK_BLOCKED", "editing", task["task_id"],
                            {"error": incomplete_message("render 前闸门", detail)[:1200]},
                            human_visible=True)
                raise NarrationIncompleteError(incomplete_message("render 前闸门", detail))
            if blocks:
                detail = {"reasons": blocks,
                          "expected_segments": narration_eval["expected_segments"],
                          "successful_segments": narration_eval["successful_segments"],
                          "failed_segments": narration_eval["failed_indexes"],
                          "timeline_duration_s": dcontract["timeline_duration_s"],
                          "narration_duration_s": dcontract["narration_duration_s"],
                          "tolerance_ratio": tol,
                          "policy": "timeline_authoritative"}
                engine.emit(task["project_id"], "TASK_BLOCKED", "editing", task["task_id"],
                            {"error": incomplete_message("render 前闸门", detail)[:500]},
                            human_visible=True)
                raise NarrationIncompleteError(incomplete_message("render 前闸门", detail))

        # ---- 4.x Phase 4-F：可选 BGM（**默认关闭**）+ 旁白 ducking ----
        # 关闭时：不解析、不校验、不产生任何滤镜/输入 → 既有输出行为逐字不变。
        # 开启时：**先校验后渲染**；校验失败即 fail-closed（BLOCKED，不产出"未声明地没有 BGM"的成片）。
        bgm_evidence = {"enabled": False, "applied": False,
                        "settings_source": "default(disabled)",
                        "rule": "BGM 关闭：既有音频链保持不变（未新增输入/滤镜）"}
        bgm_ctx = None
        _bgm_settings = core_bgm.bgm_settings(getattr(engine, "config", None))
        if _bgm_settings.get("enabled"):
            _src = _bgm_settings.get("source")
            _p = Path(str(_src)) if _src else None
            if _p is not None and not _p.is_absolute():
                _p = project_dir / _p
            _v = core_bgm.verify_bgm(_p, _bgm_settings, ctx=ctx,
                                     config=getattr(engine, "config", None))
            _iv = core_bgm.narration_intervals(narration_payload, limit_s=timeline_total)
            bgm_evidence = {
                "enabled": True, "applied": False, "settings_source": _bgm_settings["_source"],
                "settings": {k: _bgm_settings[k] for k in
                             ("source", "provider", "source_id", "license", "attribution",
                              "sha256", "bed_db", "duck_db", "ramp_ms", "min_lufs", "max_lufs",
                              "max_peak_dbtp", "min_duration_s", "license_required")},
                "verify": _v,
                "narration_intervals": _iv,
                "ducking_active": bool(_iv),
                "rule": ("旁白时间段内 BGM 增益 = duck_db；之外 = bed_db；边界各 ramp_ms 线性过渡；"
                         "旁白开始前提前 ramp_ms 进入 duck（旁白优先，不被覆盖）"),
            }
            if not _v.get("ok"):
                _detail = {"code": _v.get("code"), "detail": _v.get("detail"),
                           "file": _v.get("file"), "sha256": _v.get("sha256"),
                           "license": _v.get("license"), "license_class": _v.get("license_class"),
                           "attribution": _v.get("attribution"),
                           "policy": "bgm_optional_extension_fail_closed"}
                engine.emit(task["project_id"], "TASK_BLOCKED", "editing", task["task_id"],
                            {"error": "[BGM_REJECTED] " + json.dumps(_detail, ensure_ascii=False)[:460]},
                            human_visible=True)
                raise core_bgm.BgmRejectedError(_v.get("code") or "BGM_MIX_FAILED",
                                                _v.get("detail") or "BGM 校验未通过")
            _mix = core_bgm.mix_filters(narration_label="__narr__", bgm_label="__bgm__",
                                        master_chain=None, intervals=_iv, settings=_bgm_settings,
                                        total_s=timeline_total,
                                        bgm_duration_s=_v.get("duration_s"))
            bgm_evidence.update({"apply_plan": _mix["evidence"],
                                 "volume_expression": _mix["volume_expression"]})
            bgm_ctx = {"settings": _bgm_settings, "verify": _v, "path": _p, "intervals": _iv,
                       "mix": _mix, "evidence": bgm_evidence}

        if script and script.get("segments"):
            ff_args = self._narration_args(engine, task, script, resolution, fps, params,
                                           narration_audio,
                                           background_image=(str(img) if img else None),
                                           timeline=timeline, ctx=ctx, bgm=bgm_ctx,
                                           segment_windows=(v2_windows or None),
                                           audio_time_base_s=v2_time_base)
            used_names = "、".join(sorted({s["selected_asset"]["name"] for s in scenes_with_asset}))
            summary = (f"渲染完成：{len(script['segments'])} 段旁白字幕烧录"
                       + ("，真实旁白音轨已混入" if narration_audio else "，音频为占位音")
                       + ("；{} 个镜头使用 {} 个素材（{}）".format(
                           len(scenes_with_asset), len({s["selected_asset"]["asset_id"]
                                                        for s in scenes_with_asset}), used_names)
                          if scenes_with_asset else "；画面为纯色底"))
        else:
            # 兜底演示：无脚本时生成测试片段
            ff_args = [
                "-f", "lavfi", "-i", f"testsrc=size={resolution}:rate={fps}:duration=5",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=5",
                "-vf", "drawtext=text='video-studio demo':fontfile='C\\:/Windows/Fonts/arial.ttf':fontcolor=white:fontsize=48:x=(w-text_w)/2:y=(h-text_h)/2",
                "-c:v", params.get("codec", "libx264"), "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-shortest",
            ]
            summary = "渲染完成（无脚本，演示片段）"
        try:
            result = tool.execute({"op": "raw", "args": ff_args, "output": out_rel}, ctx)
        except ToolError as exc:
            if exc.code == "FFMPEG_MISSING":
                # 降级：产出渲染方案，任务置 BLOCKED 等 ffmpeg 就绪（不重试空耗）
                data = {"status": "deferred", "reason": str(exc),
                        "render_command": ["ffmpeg", "-y", *ff_args,
                                           str(engine.project_dir(task["project_id"]) / out_rel)],
                        "summary": "ffmpeg 未安装，渲染延后", "confidence": 1.0}
                aid = engine.write_artifact(task["project_id"], task["task_id"],
                                            "render_deferred", data, summary=data["summary"])
                engine.attach_artifact(task["task_id"], aid)
                engine.db.set_task_status(task["task_id"], "BLOCKED", str(exc))
                engine.emit(task["project_id"], "TASK_BLOCKED", "editing", task["task_id"],
                            {"error": str(exc)}, human_visible=True)
                return
            raise
        scenes_with_asset_ids = {s["selected_asset"]["asset_id"] for s in scenes_with_asset}

        # ---- 3.x Phase 2-B.1：成片产出后校验时长 == 时间轴（禁止"成功但被截短"）----
        out_abs = Path(result.data["output"]) if result.data.get("output") else \
            (project_dir / out_rel)
        video_dur = probe_duration_s(ctx, out_abs)
        video_dur_delta = (None if video_dur is None
                           else round(video_dur - timeline_total, 3))
        video_dur_ok = (video_dur is not None
                        and abs(video_dur - timeline_total) <= VIDEO_DURATION_TOLERANCE_S)
        if script and script.get("segments") and not video_dur_ok:
            detail = {"video_duration_s": video_dur, "timeline_duration_s": timeline_total,
                      "delta_s": video_dur_delta,
                      "tolerance_s": VIDEO_DURATION_TOLERANCE_S,
                      "narration_state": narration_state,
                      "policy": "timeline_authoritative"}
            engine.emit(task["project_id"], "TASK_BLOCKED", "editing", task["task_id"],
                        {"error": incomplete_message("成片时长校验未通过", detail)[:500]},
                        human_visible=True)
            raise NarrationIncompleteError(incomplete_message("成片时长校验未通过", detail))

        # ---- 3.x Phase 3-B：成片响度契约（实测 → 必要时仅重编音频校正 → 再实测）----
        # 目标 -16 LUFS ±1 LU、真峰 ≤ -1.5 dBTP（`core.audio`，授权指定）。**不达标即 fail-closed**：
        # 宁可 BLOCKED，也不产出"成功但不达标"的成片。测量手段是真实 ffmpeg ebur128（非估算）。
        loud_contract = core_audio.contract_from_config(getattr(engine, "config", None))
        _master_on = core_audio.mastering_enabled_from_config(getattr(engine, "config", None))
        _chain = None
        if _master_on:
            _r = (core_audio.probe_audio_rate(ctx, project_dir / narration_audio)
                  if narration_audio else 44100)
            _chain = core_audio.mastering_chain(post_gain_db=0.0, sample_rate=_r)
        loud_film = core_audio.enforce_loudness_on_film(
            out_abs, exe=core_audio.resolve_ffmpeg(getattr(engine, "config", None)),
            contract=loud_contract, max_corrections=2)
        audio_loudness = {"ok": loud_film["ok"], "contract": loud_film["contract"],
                          "method": loud_film["method"],
                          "corrections": loud_film["corrections"],
                          "mastering_applied": bool(_master_on),
                          "audio_chain": _chain,
                          "measured_lufs": loud_film["final"].get("measured_lufs"),
                          "measured_true_peak_dbtp": loud_film["final"].get("measured_true_peak_dbtp"),
                          "delta_lu": loud_film["final"].get("delta_lu"),
                          "reasons": loud_film["final"].get("reasons") or [],
                          "passes": [{"ok": p.get("ok"), "lufs": p.get("measured_lufs"),
                                      "true_peak_dbtp": p.get("measured_true_peak_dbtp"),
                                      "applied_gain_db": p.get("applied_gain_db"),
                                      "reasons": p.get("reasons") or []}
                                     for p in loud_film["passes"]]}
        if script and script.get("segments") and not loud_film["ok"]:
            detail = {"reasons": audio_loudness["reasons"],
                      "measured_lufs": audio_loudness["measured_lufs"],
                      "measured_true_peak_dbtp": audio_loudness["measured_true_peak_dbtp"],
                      "contract": loud_film["contract"],
                      "mastering_applied": bool(_master_on),
                      "passes": audio_loudness["passes"],
                      "policy": "loudness_contract_v1"}
            engine.emit(task["project_id"], "TASK_BLOCKED", "editing", task["task_id"],
                        {"error": "[LOUDNESS_OUT_OF_CONTRACT] "
                                  + json.dumps(detail, ensure_ascii=False)[:460]},
                        human_visible=True)
            raise core_audio.LoudnessContractError(
                "成片响度不满足契约：" + "；".join(audio_loudness["reasons"]))

        # ---- 3.x Phase 2-C：成片抽帧核验（可追溯的"是否实际出现在成片"）----
        # 不能只写 artifact 状态而不看实际画面：此处对每个镜头在其窗口内抽帧，与候选素材做
        # 48×48 灰度相关，记录 argmax 与相关系数；分配了素材却在该窗口看不到它 → 渲染失败。
        scene_evidence, material_verification = self._verify_scene_frames(
            engine, ctx, out_abs, timeline, refs_pool=asset_pool, policy=mat_policy)
        # ---- Phase 19 / P19-1：VLM 存在性**仲裁层**（加法、配置门控、**默认关闭**）----
        # 关闭时 `apply_arbitration` 原样返回入参（不新建/不修改容器）⇒ 核验行为与现状逐字节一致。
        # 开启时：corr<阈值 的景 → VLM 存在性核验 → present ⇒ PASS_VLM_PRESENT（放行，附证据）；
        #         absent/uncertain/调用失败 ⇒ 维持阻断（fail-closed 语义零改动）。
        _arb_report = {"enabled": False}
        try:
            from ...core import render_arbitration as _arb
            material_verification, _arb_report = _arb.apply_arbitration(
                verification=material_verification,
                frame_dir=(engine.project_dir(task["project_id"]) / "artifacts"),
                timeline=timeline, engine=engine, root=ROOT,
                config=getattr(engine, "config", None))
            if _arb_report.get("enabled"):
                _pv = ""
                try:
                    from ...tools import vlm_judge as _vj
                    _pv = _vj.PROMPT_VERSION_PRESENCE
                except Exception:                                           # noqa: BLE001
                    _pv = "vlm-presence-verify-v1"
                engine.emit(task["project_id"],
                            "RENDER_ARBITRATION", "editing", task["task_id"],
                            {"arbitrated": _arb_report.get("arbitrated"),
                             "still_failed": _arb_report.get("still_failed"),
                             "cost_usd": _arb_report.get("cost_usd"),
                             "prompt_version": _pv},
                            human_visible=bool(_arb_report.get("arbitrated")))
                # ---- P50-3①：**仲裁逐景 VLM 调用明细落账** ----
                # 授权书要求：新日志字段须含 **模型名 / HTTP 状态 / 缓存 / 降级标志**，
                # 使「每笔 present 裁定 ⇔ 有效 VLM 调用」**可机械核验**
                # （P49-2 审计 A1 因只有汇总量而结论"未决"）。
                # 注意：`apply_arbitration` 本就在 `records` 里逐景记录了
                # `vlm{model, prompt_version, presence, reason, cache_hit,
                # error_code, frame_sha256, asset_sha256}` 与 `arbitration`
                # 处置（含 SKIPPED_MISSING_INPUT / SKIPPED_NOT_CONFIGURED），
                # 只是**从未落账**。此处**新增独立事件**持久化之（**不改**既有事件字段）。
                try:
                    _recs = list(_arb_report.get("records") or [])
                    engine.emit(task["project_id"],
                                "RENDER_ARBITRATION_DETAIL", "editing",
                                task["task_id"],
                                {"scene_count": len(_recs),
                                 "records": _recs,
                                 "fields": ["scene_id", "arbitration", "final",
                                            "cost_usd", "vlm.model",
                                            "vlm.prompt_version", "vlm.presence",
                                            "vlm.cache_hit", "vlm.error_code",
                                            "vlm.frame_sha256",
                                            "vlm.asset_sha256"],
                                 "note": ("P50-3①：逐景 VLM 调用明细；"
                                          "`arbitration` 取值含 "
                                          "VLM_PRESENCE_VERIFY / "
                                          "SKIPPED_MISSING_INPUT / "
                                          "SKIPPED_NOT_CONFIGURED ⇒ "
                                          "据此可判定每笔裁定是否对应有效调用")},
                                human_visible=False)
                except Exception as _de:                                     # noqa: BLE001
                    log_warn = "RENDER_ARBITRATION_DETAIL emit failed: {}".format(
                        str(_de)[:120])
                    try:
                        engine.emit(task["project_id"], "RENDER_ARBITRATION_DETAIL",
                                    "editing", task["task_id"],
                                    {"error": log_warn}, human_visible=False)
                    except Exception:                                        # noqa: BLE001
                        pass
        except Exception as _arb_exc:                                       # noqa: BLE001
            _arb_report = {"enabled": False, "error": "{}: {}".format(
                type(_arb_exc).__name__, str(_arb_exc)[:160])}
        data_arbitration = _arb_report
        if material_verification.get("failed_scenes"):
            detail = {"reason": "分配素材未出现在其镜头窗口内",
                      "failed_scenes": material_verification["failed_scenes"],
                      "method": material_verification["method"],
                      "min_corr": mat_policy["frame_match_min_corr"],
                      "arbitration": data_arbitration}
            engine.emit(task["project_id"], "TASK_BLOCKED", "editing", task["task_id"],
                        {"error": insufficient_message(detail)[:500]}, human_visible=True)
            raise MaterialInsufficientError(insufficient_message(detail))

        # ---- 6-A/M2：Production Integrity **渲染后硬门**（PI-3 成片静音 / PI-4 轨道 / PI-5 字幕 orphan）----
        # 在**任何交付物落库之前**对最终 MP4 实测；fail-closed：不达标即阻断且**不写 render_output/attribution**，
        # 因此不会产生"错误的生产 artifact"（已渲染的 mp4 文件保留为证据，不作为交付物登记）。
        # `narration_expected = (narration_payload is not None)`：无旁白的 plan-only 路径不因 PI-5 的 NOT_ASSESSABLE 被误伤。
        from ...core.strip import strip_claims as _strip
        _post_cues = core_captions.build_cues([{"narration": _strip(s.get("narration", "")),
                                                "duration_s": s.get("duration_s")}
                                               for s in (script.get("segments") or [])
                                               if _strip(s.get("narration", "")).strip()],
                                              windows=(v2_windows or None))
        _post_gate = core_integrity.post_render_gate(
            out_abs, timeline_total, _post_cues,
            (dcontract or {}).get("narration_duration_s"),
            narration_payload is not None,
            core_audio.resolve_ffmpeg(getattr(engine, "config", None)),
            ((getattr(engine, "config", None) or {}).get("tools", {}).get("ffmpeg", {})
             .get("ffprobe")),
            core_integrity.gate_policy(getattr(engine, "config", None)),
            narration_plan=v2_plan)
        gate_post_report = _post_gate
        if _post_gate["blocked"]:
            detail = {"reasons": _post_gate["reasons"],
                      "stage": "post_render",
                      "metrics": {k: {"state": v.get("state")} for k, v in
                                  (_post_gate["metrics"] or {}).items()},
                      "integrity_gate": _post_gate["detail"],
                      "policy": "production_integrity_gate_v1"}
            engine.emit(task["project_id"], "TASK_BLOCKED", "editing", task["task_id"],
                        {"error": core_integrity.GATE_CODE + " "
                                  + json.dumps(detail, ensure_ascii=False)[:1200]},
                        human_visible=True)
            raise core_integrity.ProductionIntegrityError(_post_gate["message"], detail)

        if scenes_with_asset:
            note = ("旁白字幕烧录自脚本产物；画面按**素材时间轴**逐镜头装配：{} 个镜头使用 {} 个本地"
                    "ingest 素材，其余 {} 个镜头为纯色底（未使用外部 provider）。".format(
                        len(scenes_with_asset), len(scenes_with_asset_ids),
                        len(timeline) - len(scenes_with_asset)))
            visual_source = "material_timeline"
        else:
            note = ("旁白字幕烧录自脚本产物；无可用本地素材 → 全部镜头为纯色底"
                    "（fallback_state=SOLID_COLOR_CARD，不伪造画面上屏）。")
            visual_source = "solid_color_subtitle_card"
        data = {"output": str(result.data["output"]), "render_params": params,
                "render_params_raw": params_raw,
                "render_params_sanitized": params != params_raw,
                "summary": summary, "confidence": 1.0,
                "visual_source": visual_source,
                "material_mode": mat_mode, "material_candidates": mat_n,
                "material_assembly": assembly_state,
                # ---- Phase 2-A：镜头级素材分配（稳定标识 + 选择理由 + 降级状态）----
                "scene_count": len(timeline),
                "scenes_with_asset": len(scenes_with_asset),
                "fallback_scenes": [s["scene_id"] for s in timeline
                                    if s.get("fallback_state") != "LOCAL_INGEST"],
                # ---- Phase 2-B：素材时间轴（render 实际据此装配）----
                "material_timeline": timeline,
                "assets_used": sorted(
                    ({k: s["selected_asset"][k] for k in
                      ("asset_id", "name", "source", "sha256", "path", "retrieval_match_score")}
                     for s in scenes_with_asset),
                    key=lambda a: a["asset_id"]),
                # 兼容既有字段（Phase 1 语义）
                "material_used": mat_used,
                "material_appearances": [{"scene_id": s["scene_id"], "start_s": s["start_s"],
                                          "end_s": s["end_s"],
                                          "asset_id": (s["selected_asset"] or {}).get("asset_id"),
                                          "fallback_state": s["fallback_state"]}
                                         for s in timeline],
                # ---- Phase 2-B.1：旁白完整性 + 时长契约（timeline 权威）----
                "narration_state": narration_state,
                "narration_completeness": narration_eval,
                "duration_contract": dcontract,
                "video_duration_s": video_dur,
                "video_duration_delta_s": video_dur_delta,
                "video_duration_tolerance_s": VIDEO_DURATION_TOLERANCE_S,
                "video_duration_ok": video_dur_ok,
                # ---- Phase 3-B：音频响度契约（实测证据；不达标时上面已 fail-closed）----
                "audio_loudness": audio_loudness,
                # ---- 6-A/M2：Production Integrity 硬门证据（只读判定；通过时才会写本 artifact）----
                # ---- 6-A/M3：补齐**审计记录**（effective_flags + post_render.disabled）----
                # 目的：任何"门禁被显式关闭"的旁路都必须在产物里留痕，且默认路径必须显示为全开；
                # 这样 gate bypass 可审计、不会被静默启用（M3 truth set 对这两点做行为断言）。
                "production_integrity": {
                    "policy": "production_integrity_gate_v1",
                    "code": core_integrity.GATE_CODE,
                    "effective_flags": {
                        k: bool(core_integrity.gate_policy(
                            getattr(engine, "config", None)).get(k))
                        for k in ("gate_enabled", "post_render_enabled", "block_on_unknown",
                                  "block_on_unknown_pi6")},
                    "pre_render": (None if not gate_report else {
                        "blocked": gate_report.get("blocked"),
                        "metrics": {k: v.get("state") for k, v in
                                    (gate_report.get("metrics") or {}).items()},
                        "disabled": gate_report.get("disabled")}),
                    "post_render": {
                        "blocked": (gate_post_report or {}).get("blocked"),
                        "metrics": {k: v.get("state") for k, v in
                                    ((gate_post_report or {}).get("metrics") or {}).items()},
                        "disabled": (gate_post_report or {}).get("disabled"),
                        "narration_expected": (gate_post_report or {}).get(
                            "detail", {}).get("narration_expected")},
                    "note": "PI-1/PI-2/PI-3/PI-5 = hard gate；PI-4/PI-6 = 正式完整性检查；"
                            "UNKNOWN/NOT_ASSESSABLE 不视为 PASS（必要时 fail-closed 阻断）"},
                # ---- Phase 4-F：可选 BGM + ducking（默认关闭；关闭时 applied=False 且无任何滤镜）----
                "bgm": bgm_evidence,
                # ---- Phase 2-C：素材不足分类学 + 可追溯决策 + 成片证据 ----
                "traceability_version": "2-C",
                "material_policy": mat_policy,
                "insufficiency_summary": insuff,
                "insufficiency_classes": {s["scene_id"]: s["insufficiency_class"]
                                          for s in timeline},
                "fallback_states": {s["scene_id"]: s["fallback_state"] for s in timeline},
                "scenes_needing_hitl": [s["scene_id"] for s in timeline if s.get("needs_hitl")],
                "assets_rejected": [{"asset_id": a["asset_id"], "name": a["name"],
                                     "usable": False, "reason": a["unusable_reason"]}
                                    for a in asset_pool if not a.get("usable", True)],
                "material_verification": material_verification,
                "scene_evidence": scene_evidence,
                "note": note}
        # 把"是否实际出现在成片"写回时间轴（证据驱动，不靠推断）
        ev_by_scene = {e["scene_id"]: e for e in scene_evidence}
        for s in timeline:
            e = ev_by_scene.get(s["scene_id"])
            s["appears_in_film"] = (None if not e or e.get("match") is None
                                    else bool(e["match"]))
            s["film_evidence"] = ({k: e[k] for k in
                                   ("sample_t", "best_asset_id", "corr", "match",
                                    "placeholder_like", "corr_expected", "corr_best")
                                   if k in e} if e else None)
        # ---- 3.x Phase 3-A：只读交付物 attribution/credits（与 material_timeline 逐条一致）----
        credits = self._build_attribution(task, timeline, data, project_dir,
                                         licence_blocked=licence_blocked, mat_policy=mat_policy,
                                         bgm=bgm_evidence)
        aid2 = engine.write_artifact(task["project_id"], task["task_id"], "attribution",
                                     credits["payload"], summary=credits["summary"])
        data["attribution_artifact"] = aid2
        data["attribution_summary"] = credits["summary"]
        data["credits_text"] = credits["credits_text"]
        data["credits_file"] = credits["credits_file"]
        data["license_classes_used"] = credits["payload"]["license_classes_used"]
        data["licence_blocked_candidates"] = credits["payload"]["licence_blocked_candidates"]

        # 顺序契约（与 2.x 冻结基线一致）：render_output 是渲染任务的**首个** artifact（[0]），
        # attribution 是新增交付物，**先写文件**（以便 render_output 内嵌其 id）、**后挂载**。
        aid = engine.write_artifact(task["project_id"], task["task_id"], "render_output",
                                    data, summary=data["summary"])
        engine.attach_artifact(task["task_id"], aid)
        engine.attach_artifact(task["task_id"], aid2)

    @classmethod
    def _excluded_matches(cls, excluded_pool: list | None, toks: set, scene_id: str) -> list:
        """Phase 2-D：本镜头查询本可命中的**被 provider 层拒收**候选（如许可证未明）。

        只做记录与 HITL 提示——它们**绝不**进入可选用池，也绝不被当作命中。
        """
        out = []
        for e in (excluded_pool or []):
            name = "{} {}".format(e.get("name") or "", e.get("ext") or "")
            s, matched = cls._match_score(toks, name)
            if s <= 0:
                continue
            out.append({**e, "scene_id": scene_id, "match_score": s, "matched_tokens": matched})
        return out

    @staticmethod
    def _build_attribution(task, timeline: list, render_data: dict, project_dir,
                           licence_blocked: list, mat_policy: dict,
                           bgm: dict | None = None) -> dict:
        """3.x Phase 3-A：生成**只读**署名/许可交付物（attribution/credits）。

        内容与 `render_output.material_timeline` **逐条一致**（同一份数据派生，不重新推断）：
          provider / source_id / source_url / license / usage_restrictions / attribution /
          selected_asset（asset_id/name/sha256/path/bytes/width/height）/ 所属镜头与时间窗。

        同时输出人可读 `credits_text` 并落盘 `output/credits_<task>.txt`（随片交付）。
        **不做法律判断**：只原样搬运提供方声明的许可证类别与归属文本。
        """
        entries, used_ids, classes = [], set(), {}
        for s in timeline:
            a = s.get("selected_asset") or {}
            if not a:
                continue                       # 占位/未选素材镜头不进署名台账（避免伪造署名）
            klass = a.get("license_class") or classify_license(a.get("license"))[0]
            scope = "external" if is_external_candidate(a) else "local_user_material"
            classes[klass] = classes.get(klass, 0) + 1
            used_ids.add(a.get("asset_id"))
            entries.append({
                "scene_id": s["scene_id"],
                "window_s": [s.get("start_s"), s.get("end_s")],
                "fallback_state": s.get("fallback_state"),
                "insufficiency_class": s.get("insufficiency_class"),
                "scope": scope,
                "provider": a.get("provider"),
                "source_id": a.get("source_id"),
                "source_url": a.get("source_url"),
                "license": a.get("license"),
                "license_class": klass,
                "usage_restrictions": a.get("usage_restrictions"),
                "attribution": a.get("attribution"),
                "selected_asset": {
                    "asset_id": a.get("asset_id"), "name": a.get("name"),
                    "sha256": a.get("sha256"), "path": a.get("path"),
                    "relative_path": a.get("relative_path"), "bytes": a.get("bytes"),
                    "width": a.get("width"), "height": a.get("height"),
                },
                "appears_in_film": s.get("appears_in_film"),
                "film_evidence": s.get("film_evidence"),
            })
        # 合规断言**只针对外部素材**（本地自带素材不在许可门禁范围，见 core.materials.license_gate_applies）
        restricted_in_film = [e["scene_id"] for e in entries
                              if e["scope"] == "external"
                              and e["license_class"] in ("RESTRICTED", "UNKNOWN")]
        external_entries = [e for e in entries if e["scope"] == "external"]
        local_entries = [e for e in entries if e["scope"] == "local_user_material"]
        lines = ["# 素材署名 / 许可台账（credits）", "",
                 "本片使用的素材来源与许可（由 material_timeline 逐条派生，未做法律判断）：", ""]
        seen = set()
        for e in entries:
            key = (e["provider"], e["source_id"], e["selected_asset"]["sha256"])
            scene = e["scene_id"]
            if key in seen:
                lines.append("- （{} 复用）{} / {} / {}".format(
                    scene, e["selected_asset"]["name"], e["license"], e["source_id"]))
                continue
            seen.add(key)
            lines += ["- 镜头 {}（{:.1f}-{:.1f}s）：{}".format(
                scene, float(e["window_s"][0] or 0), float(e["window_s"][1] or 0),
                e["selected_asset"]["name"]),
                "  - provider: {}".format(e["provider"]),
                "  - source_id: {}".format(e["source_id"]),
                "  - source_url: {}".format(e["source_url"]),
                "  - license: {}（类别 {}）".format(e["license"], e["license_class"]),
                "  - attribution: {}".format(e["attribution"] or "（提供方未给出）"),
                "  - usage_restrictions: {}".format(e["usage_restrictions"] or "（未声明）"),
                "  - sha256: {}".format(e["selected_asset"]["sha256"]),
                "  - 本地文件: {}（sha256 与上相符即字节未被替换）".format(
                    (e.get("selected_asset") or {}).get("relative_path") or ""),
                ""]
        if not entries:
            lines.append("（本片未使用任何真实素材：全部镜头为占位/纯色底，无署名项）")
        if local_entries:
            lines += ["", "本地自带素材（用户提供，管线不做许可判定，原样记录其声明值）："]
            for e in local_entries:
                lines.append("- 镜头 {}：{}（license: {}）".format(
                    e["scene_id"], e["selected_asset"]["name"], e["license"]))
        if restricted_in_film:
            lines += ["", "> **警告**：以下镜头的许可证类别为 RESTRICTED/UNKNOWN，按契约不应出现在成片中：{}"
                      .format(restricted_in_film)]
        # ---- 4.x Phase 4-F：BGM 署名（**仅在 BGM 真的被混入时**出现；关闭时不写任何 BGM 行）----
        bgm_payload = None
        if bgm and bgm.get("applied"):
            v = bgm.get("verify") or {}
            bgm_payload = {
                "applied": True,
                "settings_source": bgm.get("settings_source"),
                "provider": v.get("provider"), "source_id": v.get("source_id"),
                "license": v.get("license"), "license_class": v.get("license_class"),
                "attribution": v.get("attribution"),
                "sha256": v.get("sha256"), "bytes": v.get("bytes"),
                "duration_s": v.get("duration_s"), "lufs": v.get("lufs"),
                "true_peak_dbtp": v.get("true_peak_dbtp"),
                "bed_db": (bgm.get("settings") or {}).get("bed_db"),
                "duck_db": (bgm.get("settings") or {}).get("duck_db"),
                "ramp_ms": (bgm.get("settings") or {}).get("ramp_ms"),
                "narration_priority": True,
                "ducking_active": bool(bgm.get("ducking_active")),
                "intervals_used": bgm.get("narration_intervals") or [],
                "trimmed_to_film": (bgm.get("apply_plan") or {}).get("trimmed_to_film"),
                "padded_after_bgm_end": (bgm.get("apply_plan") or {}).get("padded_after_bgm_end"),
                "file": v.get("file"),
            }
            classes[bgm_payload["license_class"]] = classes.get(bgm_payload["license_class"], 0) + 1
            lines += ["", "## 背景音乐（BGM，可选扩展）",
                      "- 来源：{} / {}".format(bgm_payload["provider"], bgm_payload["source_id"]),
                      "  - license: {}（类别 {}）".format(bgm_payload["license"],
                                                          bgm_payload["license_class"]),
                      "  - attribution: {}".format(bgm_payload["attribution"] or "（未给出）"),
                      "  - sha256: {}".format(bgm_payload["sha256"]),
                      "  - 时长/响度: {}s / {} LUFS（TP {} dBTP）".format(
                          bgm_payload["duration_s"], bgm_payload["lufs"],
                          bgm_payload["true_peak_dbtp"]),
                      "  - ducking: 旁白期间 {} dB / 之外 {} dB，过渡 {} ms（旁白优先）".format(
                          bgm_payload["duck_db"], bgm_payload["bed_db"], bgm_payload["ramp_ms"]),
                      "  - 处理: 过长截断={}，过短补静音={}".format(
                          bgm_payload["trimmed_to_film"], bgm_payload["padded_after_bgm_end"]),
                      ""]
        credits_text = "\n".join(lines)
        out_rel = "output/credits_{}.txt".format(task["task_id"])
        try:
            (Path(project_dir) / out_rel).write_text(credits_text, encoding="utf-8")
        except OSError:
            out_rel = None
        payload = {
            "version": "3-A",
            "render_task": task["task_id"],
            "film": render_data.get("output"),
            "film_duration_s": render_data.get("video_duration_s"),
            "entries": entries,
            "entry_count": len(entries),
            "distinct_assets": sorted(x for x in used_ids if x),
            "external_entry_count": len(external_entries),
            "local_user_material_entry_count": len(local_entries),
            "license_classes_used": classes,
            "restricted_or_unknown_in_film": restricted_in_film,
            "restricted_or_unknown_in_film_scope": "external_provider_assets",
            "license_policy": {"license_required": bool(mat_policy.get("license_required", True)),
                               "blocked_classes": ["RESTRICTED", "UNKNOWN"],
                               "applies_to": "external_provider_assets",
                               "local_material_note": ("本地自带素材（local_ingest）不在许可门禁范围："
                                                       "管线没有提供方声明可查，只原样记录声明值，不做法律判断"),
                               "note": "机械规则：不做法律判断；外部素材 RESTRICTED/UNKNOWN 不得入片"},
            "licence_blocked_candidates": licence_blocked,
            # ---- 4.x Phase 4-F：BGM 署名与最终音频配置一致（关闭时为 null）----
            "bgm": bgm_payload,
            "audio_config": {
                "bgm_enabled": bool(bgm and bgm.get("enabled")),
                "bgm_applied": bool(bgm_payload),
                "narration_priority": True,
                "loudness_contract": (render_data.get("audio_loudness") or {}).get("contract"),
                "source_of_truth": "core/audio.py（未改动）",
            },
            "credits_text": credits_text,
            "credits_file": out_rel,
            "note": ("只读交付物：由 render_output.material_timeline 逐条派生，"
                     "provider/source/license/attribution 原样搬运，未重新推断、未自动判定合法性。"),
        }
        summary = "署名台账：{} 个镜头 / {} 个素材（许可类别 {}）{}".format(
            len(entries), len(used_ids), classes or "{}",
            "；含受限类别（异常）" if restricted_in_film else "")
        return {"payload": payload, "credits_text": credits_text, "credits_file": out_rel,
                "summary": summary}

    @staticmethod
    def _verify_scene_frames(engine, ctx, video_path, timeline: list, refs_pool: list,
                             policy: dict) -> tuple[list, dict]:
        """对成片逐镜头抽帧核验（Phase 2-C 可追溯证据）。

        返回 (scene_evidence, verification_summary)：
          · 分配了素材的镜头：该窗口内抽帧必须**以分配素材为 argmax 且 corr ≥ 阈值**，否则记入
            `failed_scenes`（渲染失败）——"artifact 说用了素材但画面没换"是不可接受的。
          · 占位镜头（SOLID_COLOR_CARD）：确认画面**不是**任一素材（best corr < 阈值）→
            `placeholder_verified=true`，证明占位被如实标注而非伪装成素材。
          · 无成像库/无素材时如实记 `SKIPPED_*`，不假装核验过。
        """
        summary = {"method": "frame_pearson_48x48", "min_corr": policy["frame_match_min_corr"],
                   "argmax_margin": float(policy.get("frame_argmax_margin", 0.15)),
                   "checked_scenes": [], "failed_scenes": [], "placeholder_verified": [],
                   "skipped": None}
        # ---- P32-1：bank 开关改走 resolve_config 三级链（**config.json 不再承载该开关**）----
        # 链：config.tools.frame_match（内置默认）→ 外部文件 config/frame_match.json
        #     （同 render_motion.json 模式）→ 内置默认 bank_derived=False。
        # 默认关闭 ⇒ 关闭时行为与既有**逐字节一致**（走 v1 全图原路径）。
        from ...core import corr_diagnostics as _CD
        try:
            _bank_cfg, _bank_src = _CD.resolve_config(getattr(ctx, "config", None), root=ROOT)
        except Exception as _exc:                                               # noqa: BLE001
            _bank_cfg = {"bank_derived": False}
            _bank_src = "resolve_config 失败 ⇒ 保守回落 off（{}）".format(type(_exc).__name__)
        bank_version = _CD.bank_version_of(_bank_cfg.get("bank_derived"))
        bank_mode = bool(bank_version)
        summary["bank_derived"] = bank_mode
        summary["bank_version"] = bank_version
        summary["bank_config_source"] = _bank_src
        if not policy.get("frame_verify", True):
            summary["skipped"] = "POLICY_DISABLED"
            return [], summary
        if not timeline:
            summary["skipped"] = "NO_TIMELINE"
            return [], summary
        try:
            import numpy as np  # noqa: F401  —— 仅用于可用性探测
            from PIL import Image  # noqa: F401
        except Exception as exc:                       # noqa: BLE001
            summary["skipped"] = "NO_IMAGING_LIB: {}".format(type(exc).__name__)
            return [], summary
        refs = {}
        ref_paths = {}
        _ff_exe = None
        for a in (refs_pool or []):
            if not a.get("usable", True):
                continue
            try:
                _rp = str(a.get("path") or "")
                if _rp.lower().endswith(VIDEO_EXTS):
                    # P58-3：**视频参照 = 从素材抽首帧**（缓存于素材旁 `<video>.ref.jpg`）；
                    # 抽帧失败 ⇒ 该素材无参照（其景按缺参照如实登记，不伪装通过）。
                    if _ff_exe is None:
                        import shutil as _sh0
                        _ff_exe = _sh0.which("ffmpeg") or str(ROOT / "bin" / "ffmpeg.exe")
                    refp = Path(_rp + ".ref.jpg")
                    if not refp.is_file():
                        import subprocess as _sp0
                        _sp0.run([_ff_exe, "-y", "-v", "error", "-ss", "0.5", "-i", _rp,
                                  "-frames:v", "1", str(refp)],
                                 capture_output=True, timeout=120, check=True)
                    refs[a["asset_id"]] = gray48(str(refp))
                    ref_paths[a["asset_id"]] = str(refp)
                else:
                    refs[a["asset_id"]] = gray48(a["path"])
                    ref_paths[a["asset_id"]] = a["path"]
            except Exception:                          # noqa: BLE001
                continue
        if not refs:
            summary["skipped"] = "NO_USABLE_ASSET_TO_COMPARE"
        video_dur = probe_duration_s(ctx, video_path) or 0.0
        frames_dir = Path(engine.project_dir(ctx.project_id)) / "artifacts"
        frames_dir.mkdir(parents=True, exist_ok=True)
        ffmpeg = (ctx.config.get("tools", {}).get("ffmpeg", {}) or {}).get("path")
        import shutil as _shutil
        exe = _shutil.which(ffmpeg or "ffmpeg")
        evidence = []
        for s in timeline:
            row = {"scene_id": s["scene_id"], "window_s": [s["start_s"], s["end_s"]],
                   "fallback_state": s["fallback_state"],
                   "insufficiency_class": s["insufficiency_class"],
                   "expected_asset_id": (s.get("selected_asset") or {}).get("asset_id"),
                   "sample_t": None, "best_asset_id": None, "corr": None, "match": None,
                   "placeholder_like": None, "frame": None}
            start, end = float(s["start_s"]), float(s["end_s"])
            if exe is None or video_dur <= 0 or start >= video_dur:
                row["match"] = None
                row["note"] = "NOT_RENDERED_OR_NO_FFMPEG"
                evidence.append(row)
                continue
            mid = (start + min(end, video_dur)) / 2
            # ---- P58-3：**视频场景的参照帧按取样时刻抽**（输出 t=mid 对应源
            # t = mid − start，因为视频条从 `-ss 0` 起播）。0.5s 固定参照对
            # 运动视频必然低相关 ⇒ 假失败。
            _exp = (s.get("selected_asset") or {})
            _exp_path = str(_exp.get("path") or "")
            if _exp_path.lower().endswith(VIDEO_EXTS) and _exp.get("asset_id"):
                # P0：**与装配侧同一个夹紧函数**。细分后末段入点会被夹到素材末尾，
                # 若核验仍按 `mid − start` 取参照，会与成片帧错位（实测 p58 T3a/T4b）。
                from ...core import shots as _shots_mod3
                try:
                    _vdu2 = _probe_dur(_exp_path)
                except Exception:                  # noqa: BLE001
                    _vdu2 = None
                _src_t = _shots_mod3.clamp_src_t(max(mid - start, 0.0), _vdu2)
                _refp = Path(_exp_path + ".ref_{:.2f}.jpg".format(_src_t))
                if not _refp.is_file():
                    import subprocess as _sp2
                    _sp2.run([exe, "-y", "-v", "error", "-ss", "{:.2f}".format(_src_t),
                              "-i", _exp_path, "-frames:v", "1", str(_refp)],
                             capture_output=True, timeout=120)
                if _refp.is_file():
                    try:
                        refs[_exp["asset_id"]] = gray48(str(_refp))
                        ref_paths[_exp["asset_id"]] = str(_refp)
                    except Exception:                  # noqa: BLE001
                        pass
            fp = frames_dir / "_frame_{}.png".format(s["scene_id"])
            import subprocess as _sp
            _sp.run([exe, "-y", "-v", "error", "-ss", "{:.2f}".format(mid), "-i", str(video_path),
                     "-frames:v", "1", str(fp)], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
            if not fp.exists():
                row["note"] = "FRAME_EXTRACT_FAILED"
                evidence.append(row)
                continue
            g = gray48(fp)
            # P32-2：bank v2 用**高分辨率探针** —— 画面按 v2 分辨率重新载入
            #（而不是把 48×48 上采样到 192×192，后者不增加任何真实细节）。
            g_bank = g
            if bank_version == _CD.BANK_VERSION_V2:
                try:
                    g_bank = _CD._gray(fp, _CD.BANK_RES_V2)
                except Exception:                  # noqa: BLE001
                    g_bank = g
            scores = {aid: round(frame_corr(g, ref), 3) for aid, ref in refs.items()}
            best = max(scores, key=lambda k: scores[k]) if scores else None
            row.update(sample_t=round(mid, 2), best_asset_id=best,
                       corr=(scores.get(best) if best else None), frame=str(fp))
            if row["expected_asset_id"]:
                want_corr = float(scores.get(row["expected_asset_id"], 0.0))
                if bank_mode and row["expected_asset_id"] in ref_paths:
                    # P26 §0 / P32-2：派生段口径 —— 期望素材改用**子窗口 bank 最大 corr**
                    #（版本由 frames/config 链决定：v1=冻结 48/5×5；v2=192/步进≤170px）
                    try:
                        _bk = _CD.bank_score_of(g_bank, ref_paths[row["expected_asset_id"]],
                                                bank_version)
                        want_corr = float(_bk["corr"])
                        row["corr_bank"] = want_corr
                        row["bank_version"] = bank_version
                        row["bank_window"] = _bk
                    except Exception as _bk_exc:            # noqa: BLE001
                        # P28 §0 教训：**不得静默回落** —— 记录原因以便审计
                        #（P32-4 实测该分支曾因 48/192 形状不匹配而整片静默降级）。
                        row["corr_bank"] = None
                        row["bank_error"] = "{}: {}".format(type(_bk_exc).__name__,
                                                            str(_bk_exc)[:120])
                if bank_mode and row["expected_asset_id"] in ref_paths:
                    # P26 §0：派生段口径 —— 期望素材用**子窗口 bank 最大 corr**；
                    # 无可比对象（池内仅它自己）时按"素材在屏即通过"处理（避免自比恒等扣分）。
                    _others = [v for k2, v in scores.items() if k2 != row["expected_asset_id"]]
                    best_corr = max(_others) if _others else want_corr
                else:
                    best_corr = float(scores.get(best, 0.0)) if best else 0.0
                # 真实素材（如两张相似的 VR 头显照片）之间相关性可能高于阈值，
                # 因此判据为"期望素材相关度达标"且"不明显低于最高者（margin 内）"，
                # 而不是苛刻要求 argmax —— 避免把"素材确实在屏"误判为失败。
                ok = (want_corr >= summary["min_corr"]
                      and want_corr >= best_corr - summary["argmax_margin"])
                row["match"] = ok
                row["corr_expected"] = round(want_corr, 3)
                row["corr_best"] = round(best_corr, 3)
                summary["checked_scenes"].append(s["scene_id"])
                if not ok:
                    summary["failed_scenes"].append({
                        "scene_id": s["scene_id"], "expected": row["expected_asset_id"],
                        "best": best, "corr_expected": round(want_corr, 3),
                        "corr_best": round(best_corr, 3), "sample_t": row["sample_t"],
                        "fallback_state": s["fallback_state"]})
            else:
                # 占位镜头：应**不**匹配任何素材（否则说明画面与记录不符）
                row["placeholder_like"] = bool(best is None
                                               or scores.get(best, 0.0) < summary["min_corr"])
                row["match"] = None
                if row["placeholder_like"]:
                    summary["placeholder_verified"].append(s["scene_id"])
                else:
                    summary["failed_scenes"].append({
                        "scene_id": s["scene_id"], "expected": None, "best": best,
                        "corr": row["corr"], "sample_t": row["sample_t"],
                        "fallback_state": s["fallback_state"],
                        "reason": "占位场景画面却匹配到素材（记录与成片不一致）"})
            evidence.append(row)
        summary["checked_scenes_total"] = len(summary["checked_scenes"])
        summary["placeholder_verified_total"] = len(summary["placeholder_verified"])
        return evidence, summary

    @staticmethod
    def _narration_args(engine, task, script: dict, resolution: str, fps: int,
                        params: dict, narration_audio: str | None = None,
                        background_image: str | None = None,
                        timeline: list | None = None, ctx=None,
                        bgm: dict | None = None,
                        segment_windows: list | None = None,
                        audio_time_base_s: float | None = None) -> list[str]:
        """把脚本旁白逐段烧录成字幕视频（镜头级素材装配形态）。

        narration_audio 存在时作为真实音轨混入；否则用占位正弦音。
        3.x Phase 2-A/B：timeline 非空且其中有素材 → **按素材时间轴逐镜头装配**
        （每个镜头一个素材输入，经 scale/crop 统一规格后 concat，再叠加字幕与音频）；
        无任何素材 → 退回纯色底路径（background_image 亦为 None）。
        """
        from ...core.strip import strip_claims  # V2：烧录字幕必须剥离标记
        # P57-1：旧词级路径 `build_cues_from_words` 自生产分发**退役**（不再导入、
        # 不再调用；函数本体保留于 core.captions 供历史测试引用）。
        from ...core.captions import (PROD_CUE_COUNT_RANGE, build_cues,
                                      build_cues_from_audio,
                                      production_cue_violations, split_long_cues,
                                      to_ass)
        segments = [s for s in script.get("segments", []) if strip_claims(s.get("narration", "")).strip()]
        # Duration Contract v2：总长 = **audio_time_base**（Σ 实际 TTS + pause budget + trailing）；
        # 无 v2 权威（plan-only/无 voice）时才退回声明时基。
        total = (float(audio_time_base_s) if audio_time_base_s
                 else sum(max(float(s.get("duration_s") or 0), 3.0) for s in segments) + 2.0)
        art_dir = engine.project_dir(task["project_id"]) / "artifacts"
        vf_parts: list[str] = []
        # ---- 5-M：字幕烧录改为**逐条字幕（底部居中 + 描边）**，由 libass 渲染 ASS ----
        # 旧实现：每段旁白一条 `drawtext`，整段文案按自适应字号折行后**居中铺满画面**（enable=整段时长）
        #        → 画面等于被整段文案占满，不是字幕。
        # 新实现：`core.captions` 把每段切成 ≤36 字（≤2 行）的 cue，按字数分配该段窗口内的时间；
        #        生成 ASS（PlayRes=分辨率、Alignment=2 底部居中、Outline=3）后用一次 `ass=` 滤镜烧录。
        #        时间基与画面/时间轴一致（脚本时基累计），不改变时长契约与其它滤镜顺序。
        cue_payload = [{"narration": strip_claims(s.get("narration", "")),
                        "duration_s": s.get("duration_s")} for s in segments]
        # v2：cue 时间基 = **实际音频窗口**（不再按 declared 分摊）
        # ---- P43-1：**句界吸附**（silencedetect 语音恢复点；外部产物 `recoveries.json`）----
        # 根因（监理测量）：cue 原按**字数**在窗口内**均匀铺排**，而真实句界**不均匀**
        # ⇒ 语音恢复点上 cue 中位滞后 **1.14s**（>1s 者 66 处），77 条 cue 在停顿中提前出现。
        _recoveries = None
        try:
            import json as _json_local
            for _cand in (engine.project_dir(task["project_id"]) / "media" / "voice"
                          / "recoveries_fullfilm.json",
                          ROOT / "output" / "phase36_voice" / "recoveries.json",
                          ROOT / "output" / "phase36_voice" / "recoveries.json"):
                if _cand.is_file():
                    _raw = _json_local.loads(_cand.read_text(encoding="utf-8"))
                    _recoveries = {int(k): v for k, v in
                                   (_raw.get("recoveries") or {}).items()}
                    break
        except Exception:                                                       # noqa: BLE001
            _recoveries = None
        _snap_stats: dict = {}
        # ---- P52-1：**词时刻音频锚定**（优先于词级 manifest）----
        # 弃用合成 manifest 的绝对时刻换算（其时钟 ≠ 实际音频时钟：P30 静音物化 vs
        # 合成期 pause 数学）。实测 F8 因此 cue 覆盖率仅 **14.2%**、97% 的 cue 被
        # clamp 成 1.0s。改用**独立信号源**：每景**实际音频切片**的细粒度语音运行。
        _runs = None
        try:
            import json as _json_r
            for _rc in (engine.project_dir(task["project_id"]) / "media" / "voice"
                        / "runs_by_scene.json",
                        ROOT / "output" / "phase52_voice" / "runs_by_scene.json"):
                if _rc.is_file():
                    _rr = _json_r.loads(_rc.read_text(encoding="utf-8"))
                    _runs = {k: [tuple(x) for x in v]
                             for k, v in (_rr.get("runs_by_scene") or {}).items()}
                    break
        except Exception:                                                       # noqa: BLE001
            _runs = None
        # ---- P57-1 **cue 单一分发链**（word_exact → audio_anchor → 均匀铺排兜底）----
        # F10.1 缺陷复盘（授权书 §0）：P55-1 word_exact 构好了正确 cue，却被下方
        # 旧词级路径 `build_cues_from_words` **无条件覆盖**（当时 voice 产物不带
        # `audio_time_base_s` ⇒ run() 的 v2 门不启用 ⇒ `segment_windows=[]` ⇒
        # windows=None ⇒ 词的段内局部时钟不被窗裁剪、不被 clamp）⇒ 烧录 ASS
        # 105 条 cue 压缩在 0.1–178.363s（dump 的 cue_source 标签仍是 word_exact，
        # 而每条 cue 的 source 已是 word_boundary）——「测试修了、生产没接」第五例。
        # 自 P57-1 起：**只构一次、绝不覆盖**；旧词级路径退役（不保留双路径）。
        _asegs = [{"scene_id": s.get("scene_id"),
                   "narration": strip_claims(s.get("narration", "")),
                   "duration_s": s.get("duration_s")} for s in segments]
        # ---- P53-1 **窗对齐**：窗口从**景自身**取（`audio_window_s`，36 条，权威）----
        # 历史教训：`segment_windows`（v2 派生）与景数不一致时按下标喂会错位
        #（实测转储：P04_2 start=0.0 / P08_2 dur=−2.023 / 段序错乱）。
        _scw: list = []
        for _i, _s in enumerate(segments):
            _aw = _s.get("audio_window_s")
            if isinstance(_aw, (list, tuple)) and len(_aw) == 2:
                _scw.append({"start_s": float(_aw[0]), "end_s": float(_aw[1])})
            else:
                _scw.append(None)
        if not all(_scw):
            # 回退：按 `actual_tts_duration_s` 累积（仍然是**逐景**）
            _cur, _fb = 0.0, []
            for _s in segments:
                _d = float(_s.get("actual_tts_duration_s")
                           or _s.get("duration_s") or 0.0)
                _fb.append({"start_s": round(_cur, 3),
                            "end_s": round(_cur + _d, 3)})
                _cur += _d
            _scw = _fb
        # ---- P55-1 词级 manifest（唯一词级输入；与 runs 解耦加载）----
        _wexact = None
        try:
            import json as _json_x
            for _xc in (engine.project_dir(task["project_id"]) / "media" / "voice"
                        / "words_manifest.json",
                        ROOT / "output" / "phase45_voice" / "words_manifest.json"):
                if _xc.is_file():
                    _xr = _json_x.loads(_xc.read_text(encoding="utf-8"))
                    _wexact = {p["para"]: p for p in (_xr.get("paras") or [])}
                    break
        except Exception:                                                       # noqa: BLE001
            _wexact = None
        cues = None
        _cuesrc = None
        if _wexact:
            # 景窗：把 `audio_window_s` 折进窗记录（含 `scene_id`/`actual_s`）——
            # 调用形状与 P55 验证完全一致（`_asegs` + manifest + 逐景窗）。
            _wrec = []
            for _i, _s in enumerate(segments):
                _aw = _s.get("audio_window_s")
                _wrec.append({
                    "scene_id": _s.get("scene_id"),
                    "start_s": float(_aw[0]) if _aw else 0.0,
                    "end_s": float(_aw[1]) if _aw else 0.0,
                    "actual_s": float(_s.get("actual_tts_duration_s")
                                      or _s.get("duration_s") or 0.0)})
            try:
                cues = core_captions.build_cues_from_words_exact(
                    _asegs, _wexact, windows=_wrec,
                    dump_path=(art_dir / "_cuedump_{}.json".format(
                        str(task.get("task_id") or "adhoc"))))
                _cuesrc = "word_exact"
            except Exception as _xe:                                            # noqa: BLE001
                # **fail-closed**：断言不过不静默降级，按授权书要求中止。
                # **兼容性**：测试桩（`Eng`）可能没有 `emit` ⇒ 用 getattr 守护，
                # **不吞掉原始错误**（无论 emit 成败都继续 raise 原异常，P56-2b）。
                try:
                    _em = getattr(engine, "emit", None)
                    if callable(_em):
                        _em(task["project_id"], "TASK_BLOCKED", "editing",
                            task["task_id"],
                            {"error": "P55-1 词级归属断言失败：{}".format(
                                str(_xe)[:300])}, human_visible=True)
                except Exception:                                               # noqa: BLE001
                    pass
                raise
        if cues is None and _runs:
            # P52-1 音频锚定（词 manifest 缺失时的独立信号源回退）
            cues = build_cues_from_audio(_asegs, _runs, windows=_scw)
            _cuesrc = "audio_anchor"
        if cues is None:
            # plan-only / 无 voice 产物路径（既有行为逐字不变；单测最小夹具走此）
            _cuesrc = "uniform_legacy"
            cues = build_cues(
                cue_payload,
                windows=([w for w in segment_windows] if segment_windows else None),
                recoveries=_recoveries, snap_stats=_snap_stats)
        # ---- P0（2026-10-20）：**显示级** cue 切分（长句拆成 ≤18 字 / ≤4s）----
        # 审计实测：word_exact 按静音间隔分组，单条 cue 可达 14.9s / 约 70 字。
        # 纯后处理：不改时间基、不改词归属，只按字符预算均分（总时长不变）。
        # 关闭方式：config.caption_gate.max_cue_chars=0 且 max_cue_s=0。
        _cg = ((getattr(engine, "config", None) or {}).get("caption_gate") or {})
        _dc_chars = int(_cg.get("max_cue_chars", 18) or 0)
        _dc_s = float(_cg.get("max_cue_s", 4.0) or 0)
        if cues and (_dc_chars or _dc_s):
            _before = len(cues)
            cues = split_long_cues(cues, max_chars=_dc_chars, max_s=_dc_s)
            if len(cues) != _before:
                try:
                    engine.emit(task["project_id"], "CAPTION_DISPLAY_SPLIT", "editing",
                                task["task_id"],
                                {"cues_before": _before, "cues_after": len(cues),
                                 "max_cue_chars": _dc_chars, "max_cue_s": _dc_s,
                                 "rule": "P0 display-level split（总时长不变）"},
                                human_visible=False)
                except Exception:                                               # noqa: BLE001
                    pass
        # ---- P57-1 **生产断言**（构建后、烧录前；fail-closed，授权书 §1）----
        # cue 跨度 ≈ 实测音频时长（±2s）/ 时长 median ≥3s / 排他重叠 0 /
        # 条数 101–111；**违反即不渲染**（TASK_BLOCKED + raise）。
        # 适用性：word_exact / audio_anchor 产物。word_exact 产出 0 条且 manifest
        # 与本片段键**根本不匹配** = 最小单测夹具（P56-2b 同族前提，不适用）；
        # manifest 匹配却 0 条 = 生产缺陷 ⇒ 照断（防再次产出「零字幕成片」）。
        _prod_gate = None
        if _cuesrc in ("word_exact", "audio_anchor"):
            _keys = {str(s.get("scene_id") or "").split("_")[0] for s in segments}
            _matched = bool(_wexact) and any(k in _wexact for k in _keys)
            _engaged = bool(cues) or (_cuesrc == "word_exact" and _matched)
            if _engaged:
                _audio_ref = None
                if narration_audio:
                    try:
                        _audio_ref = probe_duration_s(
                            ctx, engine.project_dir(task["project_id"]) / narration_audio)
                    except Exception:                                           # noqa: BLE001
                        _audio_ref = None
                # P0（2026-10-20）：`count_range` 不再回落到某部影片的绝对条数
                # （PROD_CUE_COUNT_RANGE=101–111 会把"切得对"的 21 条判成缺陷）。
                # 未显式配置 ⇒ 传 None，由 `production_cue_violations` 按音频时长
                # 相对推导（dur/3.8 … dur/1.2）。要钉死条数时在
                # `config.caption_gate.cue_count_range` 里显式给 [lo, hi]。
                _cue_range = ((getattr(engine, "config", None) or {})
                              .get("caption_gate", {}) or {}).get("cue_count_range")
                _viol = production_cue_violations(
                    cues, audio_dur_s=_audio_ref, count_range=_cue_range)
                _prod_gate = {"source": _cuesrc, "cues": len(cues),
                              "audio_dur_s": (round(float(_audio_ref), 3)
                                              if _audio_ref is not None else None),
                              "violations": _viol}
                if _viol:
                    _msg = "P57-1 生产 cue 契约断言失败（fail-closed）：{}".format(
                        "; ".join(_viol)[:400])
                    try:
                        _em = getattr(engine, "emit", None)
                        if callable(_em):
                            _em(task["project_id"], "TASK_BLOCKED", "editing",
                                task["task_id"],
                                {"error": _msg, "cue_gate": _prod_gate},
                                human_visible=True)
                    except Exception:                                           # noqa: BLE001
                        pass
                    raise RuntimeError(_msg)
        # 文件名只用 `task_id`（缺失时退化 `adhoc`）——部分单测以最小 task 字典直接调用本函数
        _cap_id = str(task.get("task_id") or "adhoc")
        cap_path = art_dir / "_captions_{}.ass".format(_cap_id)
        # ---- P52 诊断：**写盘前转储 cue 列表**（定位 ASS 时间轴错乱的破坏点）----
        # P57-1 增补：转储 `cue_gate`（生产断言结果）与逐条 `source` 首样本，
        # 使「标签与实际构建器不符」这类覆盖缺陷在 dump 层即可发现。
        try:
            import json as _json_d
            _dump = {"cues": len(cues), "cue_source": _cuesrc,
                     "cue_gate": _prod_gate,
                     "first5": [{k: c.get(k) for k in
                                 ("index", "segment_index", "scene_id", "start",
                                  "end", "dur", "source")} for c in cues[:5]],
                     "last2": [{k: c.get(k) for k in
                                ("index", "scene_id", "start", "end", "dur")}
                               for c in cues[-2:]],
                     "sum_dur": round(sum(float(c.get("dur") or 0) for c in cues), 3),
                     "max_end": max((float(c.get("end") or 0) for c in cues), default=0)}
            (art_dir / "_cuedump_{}.json".format(_cap_id)).write_text(
                _json_d.dumps(_dump, ensure_ascii=False, indent=1), encoding="utf-8")
        except Exception:                                                       # noqa: BLE001
            pass
        cap_path.write_text(to_ass(cues, resolution=resolution), encoding="utf-8")
        _cap_file = cap_path.as_posix().replace(":", "\\:")
        _fontsdir = "C\\:/Windows/Fonts"
        vf_parts.append("ass=filename='{}':fontsdir='{}'".format(_cap_file, _fontsdir))
        fade = f"fade=t=in:st=0:d=0.6,fade=t=out:st={total - 1.0:.2f}:d=0.8"
        try:
            tw, th = (int(x) for x in str(resolution).lower().split("x"))
        except (ValueError, TypeError):
            tw, th = 1280, 720
        codec = params.get("codec", "libx264")

        # ---- P0（2026-10-20）：**出口规格**显式化 ----------------------------------
        # 审计实测（video-studio_审计报告.md §4-⑪）：组装命令只给了
        # `-c:v libx264 -pix_fmt yuv420p -c:a aac`，**没有 -crf/-preset** ⇒ 落到
        # x264 默认 CRF23；且音频沿用 TTS 的 24 kHz 单声道。文字卡内容对压缩最敏感，
        # 字边发糊、色带明显。此处统一出口：
        #   · 视频 CRF18 / preset slow / yuv420p / faststart（可边下边播）
        #   · 音频 44.1 kHz / 立体声 / 192 kbps（平台与剪辑软件往返不再被降级）
        # 关闭/改档方式：config.tools.render_output.{crf,preset,audio_sample_rate,
        # audio_channels,audio_bitrate}；置 crf=0 即完全不传 -crf（回到旧行为）。
        _ro = (((getattr(engine, "config", None) or {}).get("tools") or {})
               .get("render_output") or {})
        _crf = int(_ro.get("crf", 18) or 0)
        _preset = str(_ro.get("preset", "slow") or "")
        _asr = int(_ro.get("audio_sample_rate", 44100) or 0)
        _ach = int(_ro.get("audio_channels", 2) or 0)
        _abr = str(_ro.get("audio_bitrate", "192k") or "")
        _enc = ["-c:v", codec, "-pix_fmt", "yuv420p"]
        if _crf > 0:
            _enc += ["-crf", str(_crf)]
        if _preset:
            _enc += ["-preset", _preset]
        _enc += ["-movflags", "+faststart"]
        _enc += ["-c:a", "aac"]
        if _abr:
            _enc += ["-b:a", _abr]
        if _asr > 0:
            _enc += ["-ar", str(_asr)]
        if _ach > 0:
            _enc += ["-ac", str(_ach)]

        # ---- 3.x Phase 3-B：音频母带链（响度契约 -16 LUFS / TP ≤ -1.5 dBTP）----
        # 审计实测（logs/phase3b_audit.json）：此前只做 apad，成片实测 **-19.7 LUFS**（超差 3.7 LU）。
        # 现在把 `core.audio` 的统一母带链（loudnorm + alimiter）接进**所有**脚本渲染分支；
        # 渲染完成后还会对**成片**实测并按契约 fail-closed（见 render 末尾 enforce_loudness_on_film）。
        # 注意：`loudnorm` 输出 192 kHz，必须用 `aresample` 复原到输入音频的真实采样率
        # （否则会把 24 kHz 旁白悄悄变成 192 kHz —— 实测踩到过）。
        _rate = (core_audio.probe_audio_rate(ctx, engine.project_dir(task["project_id"])
                                             / narration_audio)
                 if (narration_audio and ctx is not None) else
                 (None if narration_audio else 44100))  # 占位正弦音默认 44.1 kHz（保持原行为）
        audio_master = (core_audio.mastering_chain(post_gain_db=0.0, sample_rate=_rate)
                        if core_audio.mastering_enabled_from_config(
                            getattr(engine, "config", None)) else None)

        def _af(*parts) -> str | None:
            """把母带链与原有音频滤镜拼成一个 `-af` 串（母带链关闭时退化为原行为）。"""
            items = [p for p in ((audio_master,) + parts) if p]
            return ",".join(items) if items else None

        def _probe_dur(p) -> float | None:
            from ...core.narration import probe_duration_s as _pd
            try:
                return _pd(ctx, p)
            except Exception:                      # noqa: BLE001 —— 探测失败不影响主流程（证据留空）
                return None

        # ---- 4.x Phase 4-F：BGM 预混（默认关闭 → 下面所有分支走原路径，逐字不变）----
        # 设计：BGM 不插进各分支的滤镜图，而是**先**用一次纯音频 ffmpeg 把
        # 「旁白 + 带 ducking 包络的 BGM」混成一个中间音轨，再把该音轨交给**原有**分支，
        # 由原有位置统一套用母带链与 apad —— 这样既有链路与分支结构完全不动，母带链只生效一次。
        # 旁白优先：`amix=normalize=0`（不改变旁白电平）、BGM 增益恒为负、旁白期间再压 duck_db。
        _bgm_settings = (bgm or {}).get("settings") or {}
        _bgm_on = bool(bgm) and bool(_bgm_settings.get("enabled"))
        if _bgm_on:
            _total_s = float(total)
            _mix = core_bgm.mix_filters(narration_label="0:a", bgm_label="1:a",
                                        master_chain=None, intervals=bgm["intervals"],
                                        settings=_bgm_settings, total_s=_total_s,
                                        bgm_duration_s=bgm["verify"].get("duration_s"))
            _mix_frags = [f for f in _mix["filters"] if not f.endswith("[aout]")]
            _mix_out = "artifacts/_bgm_mix_{}.wav".format(task["task_id"])
            _mix_abs = art_dir.parent / _mix_out
            _mix_abs.parent.mkdir(parents=True, exist_ok=True)
            _exe = core_audio.resolve_ffmpeg(getattr(engine, "config", None))
            _rate_in = (core_audio.probe_audio_rate(ctx, engine.project_dir(task["project_id"])
                                                    / narration_audio)
                        if narration_audio else None)
            _cmd = [_exe or "ffmpeg", "-y", "-hide_banner", "-nostats"]
            if narration_audio is not None:
                _cmd += ["-i", str(engine.project_dir(task["project_id"]) / narration_audio)]
            else:
                _cmd += ["-f", "lavfi", "-t", "{:.3f}".format(_total_s), "-i",
                         "anullsrc=r={}:cl=mono".format(int(_rate_in or 24000))]
            _cmd += ["-i", str(bgm["path"]), "-filter_complex", ";".join(_mix_frags),
                     "-map", "[mix]", "-t", "{:.3f}".format(_total_s),
                     "-c:a", "pcm_s16le"] + (["-ar", str(int(_rate_in))] if _rate_in else [])
            _cmd += [str(_mix_abs)]
            try:
                import subprocess as _sp
                _r = _sp.run(_cmd, capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=900)
            except (OSError, Exception) as _exc:                      # noqa: BLE001
                _r = None
                _err = "{}: {}".format(type(_exc).__name__, str(_exc)[:160])
            if _r is None or _r.returncode != 0 or not _mix_abs.is_file():
                _detail = {"code": "BGM_MIX_FAILED",
                           "rc": (None if _r is None else _r.returncode),
                           "stderr": ("" if _r is None else (_r.stderr or "")[-300:]),
                           "policy": "bgm_optional_extension_fail_closed"}
                engine.emit(task["project_id"], "TASK_BLOCKED", "editing", task["task_id"],
                            {"error": "[BGM_REJECTED] " + json.dumps(_detail, ensure_ascii=False)[:460]},
                            human_visible=True)
                raise core_bgm.BgmRejectedError("BGM_MIX_FAILED", _detail["stderr"][:160])
            import hashlib as _hl
            # ---- 母带：BGM 混音动态更大，单遍动态 loudnorm 会系统性低于目标（实测 -19.5 LUFS，
            # 偏差 3.5 LU > 3 LU 收尾校正上限 → 按契约 fail-closed）。因此 BGM 路径改用**两遍线性**
            # loudnorm（同一份契约常量；见 core/audio.normalize_two_pass），随后渲染侧不再重复套母带链。
            _master_rel = "artifacts/_bgm_master_{}.wav".format(task["task_id"])
            _master_abs = art_dir.parent / _master_rel
            _tp = core_audio.normalize_two_pass(
                _mix_abs, _master_abs, exe=_exe,
                contract=core_audio.contract_from_config(getattr(engine, "config", None)),
                sample_rate=_rate_in)
            if not _tp.get("ok"):
                _detail = {"code": "BGM_MIX_FAILED", "stage": "two_pass_master",
                           "error": _tp.get("error"), "policy": "loudness_contract_v1"}
                engine.emit(task["project_id"], "TASK_BLOCKED", "editing", task["task_id"],
                            {"error": "[BGM_REJECTED] " + json.dumps(_detail, ensure_ascii=False)[:460]},
                            human_visible=True)
                raise core_bgm.BgmRejectedError("BGM_MIX_FAILED",
                                                "两遍母带未达契约：{}".format(_tp.get("error")))
            bgm["evidence"].update({
                "applied": True,
                "mastered": True,
                "premix": {"file": _mix_out, "sha256": _hl.sha256(_mix_abs.read_bytes()).hexdigest(),
                           "command": ["ffmpeg", *[a for a in _cmd[1:] if a != "-nostats"]],
                           "duration_s": _probe_dur(_mix_abs),
                           "narration_input": narration_audio,
                           "narration_input_present": narration_audio is not None},
                "master": {"file": _master_rel,
                           "sha256": _hl.sha256(_master_abs.read_bytes()).hexdigest(),
                           "method": "两遍线性 loudnorm（同一契约常量）+ alimiter",
                           "measured_lufs": (_tp.get("after") or {}).get("measured_lufs"),
                           "measured_true_peak_dbtp": (_tp.get("after") or {}).get("measured_true_peak_dbtp"),
                           "measured_input": _tp.get("measured_input")},
                "apply_plan": _mix["evidence"], "volume_expression": _mix["volume_expression"]})
            narration_audio_render = _master_rel
            # 已用**两遍线性** loudnorm 达到契约（同一契约常量）→ 渲染侧不再重复套单遍链，
            # 只保留 `apad`；最终成片仍由渲染末尾的响度 QC 实测把关（未变）。
            audio_master = None
        else:
            narration_audio_render = narration_audio

        # ---- 3.x Phase 2-A/B：按素材时间轴逐镜头装配 ----
        # 每个镜头一个输入（素材图或纯色底），统一 scale/crop/fps 后 concat，
        # 再叠加逐段字幕与淡入淡出，最后混入旁白音轨。
        # 3.x Phase 2-B.1：时长契约 = **时间轴权威**。旁白较短时用 `apad` 静音补齐到 `total`，
        # 去掉 `-shortest`——不再让音轨长度决定（截短）成片时长。
        if any(s.get("selected_asset") for s in (timeline or [])):
            inputs, filters = [], []
            # ---- P0（2026-10-20）：**镜头细分**（scene=章节 → shot=镜头）-------------
            # 审计实测：全片 3 个 scene（19–24s）硬切 ⇒ "像 AI 拼接"。
            # 这里把每个 scene 按**字幕句界**切成 ≤max_shot_s 的 shot（默认 4s）：
            #   · `src_in_s`：视频条按此 `-ss` 前进（同一素材连续切片，不是换素材）；
            #   · `reframe`：确定性取景缩放，使同素材连续切镜"看得见切点"；
            #   · 总时长与素材归属不变 ⇒ 字幕/淡入淡出/响度/抽帧核验语义不变。
            # 关闭方式：config.tools.render_shots.enabled=false。
            _shcfg = (((getattr(engine, "config", None) or {}).get("tools") or {})
                      .get("render_shots") or {})
            _units = timeline
            _shots_meta = None
            if _shcfg.get("enabled", True):
                try:
                    from ...core import shots as _shots_mod
                    # P0：视频素材时长表（决定某景能否细分——素材比景短时不切，
                    # 否则入点越过素材末尾会让"抽帧核验"的源时间等式失效）
                    _adur: dict = {}
                    for _s in (timeline or []):
                        _p = str((_s.get("selected_asset") or {}).get("path") or "")
                        if _p and _p.lower().endswith(VIDEO_EXTS) and _p not in _adur:
                            _adur[_p] = _probe_dur(_p)
                    _units = _shots_mod.plan_shots(
                        timeline, cues, asset_dur=_adur,
                        max_shot_s=float(_shcfg.get("max_shot_s", 4.0) or 4.0),
                        min_shot_s=float(_shcfg.get("min_shot_s", 1.2) or 1.2))
                    _shots_meta = {
                        "enabled": True,
                        "rule": "p0-display-shot-v1",
                        "max_shot_s": float(_shcfg.get("max_shot_s", 4.0) or 4.0),
                        "min_shot_s": float(_shcfg.get("min_shot_s", 1.2) or 1.2),
                        "scenes": len(timeline or []), "shots": len(_units or []),
                        "cuts": [{"scene_id": s.get("scene_id"),
                                  "start_s": s.get("start_s"), "end_s": s.get("end_s"),
                                  "src_in_s": s.get("src_in_s"),
                                  "reframe": s.get("reframe")} for s in (_units or [])],
                    }
                except Exception as _exc_sh:                                 # noqa: BLE001
                    _units = timeline
                    _shots_meta = {"enabled": False,
                                   "error": "{}: {}".format(type(_exc_sh).__name__,
                                                            str(_exc_sh)[:160])}
            # Phase 13（P13-2）：运动层（**默认关闭**，fail-closed）。开关走 resolve_config 链
            # （config.tools.render_motion → 可选外部文件 config/render_motion.json → 默认 off）；
            # config.json 零改动。关闭时下面的滤镜串与现状**逐字节一致**。
            motion_plan = None
            motion_cfg = {"enabled": False}
            try:
                from ...core import motion as _motion
                motion_cfg, motion_cfg_src = _motion.resolve_config(
                    getattr(engine, "config", None), root=ROOT)
                if motion_cfg.get("enabled"):
                    _scenes = [{"scene_id": str(s.get("scene_id")),
                                "duration_s": max(round(float(s["end_s"]) - float(s["start_s"]),
                                                        3), 0.5),
                                "hook": bool(s.get("hook"))}
                               for s in _units]
                    motion_plan = _motion.build_plan(
                        _scenes, out_w=tw, out_h=th, fps=fps,
                        # P0：按镜长限幅（duration_scaled）+ 允许短镜运动（min_scene_s）
                        duration_scaled=bool(motion_cfg.get("duration_scaled")),
                        policy=({"min_scene_s": motion_cfg["min_scene_s"]}
                                if motion_cfg.get("min_scene_s") else None))
            except Exception as _exc:                                         # noqa: BLE001
                motion_plan = None
                motion_cfg = {"enabled": False, "error": "{}: {}".format(
                    type(_exc).__name__, str(_exc)[:120])}
            motion_plans = ({p["scene_id"]: p for p in (motion_plan or {}).get("scenes") or []}
                            if motion_plan else {})
            motion_evidence = []
            _vdur_cache: dict = {}
            for i, sc in enumerate(_units):
                d = max(round(float(sc["end_s"]) - float(sc["start_s"]), 3), 0.5)
                _sel_path = str((sc.get("selected_asset") or {}).get("path") or "")
                _is_video = _sel_path.lower().endswith(VIDEO_EXTS)
                # P0：同一素材内的入点（视频条用；静态图忽略）
                _src_in = max(float(sc.get("src_in_s") or 0.0), 0.0)
                # P0：确定性取景（同素材连续切镜时逐镜变化，切点可见）
                _z = max(float(sc.get("reframe") or 1.0), 1.0)
                _fw = int(round(tw * _z)) // 2 * 2
                _fh = int(round(th * _z)) // 2 * 2
                if sc.get("selected_asset") and _is_video:
                    # ---- P58-2：**视频条输入**（media_type=video）----
                    # · `-ss src_in_s -t ceil(d)+2`：从**本 shot 入点**取，覆盖 shot 长；
                    # · 音频流不进 filter_complex（只用 [i:v]）⇒ 天然静音，旁白优先不变；
                    # · 滤镜链 `trim → tpad=clone → trim`：素材短于景长时**定格末帧**
                    #   补齐，再精确裁到 d 秒（时长契约在视频轨上成立）。
                    # P0 修正：细分后某些 shot 的入点会越过素材末尾（如 P01_3 源 22.08s
                    # 而时间轴要 24.09s）⇒ `-ss` 落在流外、取不到帧 ⇒ 该 shot 时长丢失，
                    # 成片比时间轴短 2.0s（PI-4 拦下）。这里把入点夹到「源末 − 0.4s」，
                    # 保证每个 shot 至少能取到帧，余量由 tpad 定格补齐。
                    if _sel_path not in _vdur_cache:
                        _vdur_cache[_sel_path] = _probe_dur(_sel_path)
                    _vdu = _vdur_cache.get(_sel_path)
                    # 与抽帧核验共用同一夹紧函数（否则参照帧与成片帧不对齐 ⇒ 假失败）
                    from ...core import shots as _shots_mod2
                    _src_in = _shots_mod2.clamp_src_t(_src_in, _vdu)
                    src_t = float(math.ceil(d)) + 2.0
                    inputs += ["-ss", f"{_src_in:.3f}", "-t", f"{src_t:.3f}", "-i", _sel_path]
                    filters.append(
                        f"[{i}:v]scale={_fw}:{_fh}:force_original_aspect_ratio=increase,"
                        f"crop={tw}:{th},setsar=1,fps={fps},trim=duration={d:.3f},"
                        f"tpad=stop_mode=clone:stop_duration={d:.3f},"
                        f"trim=duration={d:.3f},setpts=PTS-STARTPTS[v{i}]")
                elif sc.get("selected_asset"):
                    # 5-K（Post-Final Maintenance）正式纳入并**修正**低解码负载的静态图输入：
                    #   · `-framerate 1`：静态图按 1fps 取帧，后续 `fps={fps}` 复制上采样 → 解码量
                    #     从旧形态的 25·d 帧降到 ~d 帧（实测 21 路 25min 片 WorkingSet 6.7GB、
                    #     输出停滞的根因即 N 路图片输入按 25fps 持续解码）；
                    #   · `-t ceil(d)+2`：保证 1fps 源**足够覆盖** d 秒（ffmpeg 1fps 图片源实际
                    #     产出帧数 = floor(t)-1，取 d 会短 ~1s —— 5-K 审计发现的缺陷，见下）；
                    #   · 每段随后 `fps,trim=duration=d,setpts=PTS-STARTPTS`：**精确**裁到 d 秒
                    #     （含小数 d），保证"时长 = 时间轴权威"契约在**视频轨**上成立。
                    src_t = float(math.ceil(d)) + 2.0
                    inputs += ["-loop", "1", "-framerate", "1", "-t", f"{src_t:.3f}", "-i",
                               _sel_path]
                else:
                    inputs += ["-f", "lavfi", "-t", f"{d:.3f}", "-i",
                               f"color=c=0x0b1226:size={tw}x{th}:rate={fps}"]
                if not (sc.get("selected_asset") and _is_video):
                    filters.append(
                        f"[{i}:v]scale={_fw}:{_fh}:force_original_aspect_ratio=increase,"
                        f"crop={tw}:{th},setsar=1,fps={fps},trim=duration={d:.3f},"
                        f"setpts=PTS-STARTPTS[v{i}]")
                # Phase 13（P13-2）：该场景若被确定性策略选中且滤镜构造成功 ⇒ 用整数帧
                # pan/zoom 替换静态 crop（**在 concat 之前**；字幕/混音/时基不变）。
                # P58-2：**视频条不做运动层**（素材自带运动；替换会覆盖 tpad 链）。
                _p13 = motion_plans.get(str(sc.get("scene_id")))
                if _p13 and _p13.get("enabled") and not _is_video:
                    try:
                        from ...core import motion as _motion
                        _filt = _motion.crop_filter(_p13)
                        filters[-1] = (
                            f"[{i}:v]scale={_p13['src_w']}:{_p13['src_h']}:"
                            f"force_original_aspect_ratio=increase,"
                            f"crop={_p13['src_w']}:{_p13['src_h']},setsar=1,fps={fps},"
                            f"{_filt},trim=duration={d:.3f},setpts=PTS-STARTPTS[v{i}]")
                        motion_evidence.append({"scene_id": sc.get("scene_id"),
                                                "status": "MOTION_APPLIED",
                                                "motion_type": _p13["motion_type"],
                                                "filter": _filt, "params": _p13["params"],
                                                "n_frames": _p13["n_frames"]})
                    except Exception as _exc2:                                # noqa: BLE001
                        motion_evidence.append({
                            "scene_id": sc.get("scene_id"),
                            "status": "MOTION_FALLBACK_STATIC",
                            "error": "{}: {}".format(type(_exc2).__name__, str(_exc2)[:120])})
            n = len(_units)
            # P0：镜头细分证据留痕（切点数、镜长、入点、取景）
            if _shots_meta and _shots_meta.get("enabled"):
                try:
                    engine.emit(task["project_id"], "SHOT_SPLIT", "editing", task["task_id"],
                                {"scenes": _shots_meta["scenes"], "shots": _shots_meta["shots"],
                                 "max_shot_s": _shots_meta["max_shot_s"],
                                 "avg_shot_s": round(float(total) / max(n, 1), 3),
                                 "rule": _shots_meta["rule"]},
                                human_visible=True)
                except Exception:                                               # noqa: BLE001
                    pass
            # Phase 13：运动层证据留痕（**只在开启时写**；关闭时不产生任何文件 ⇒ 零副作用）
            if motion_plan is not None or motion_cfg.get("enabled") or motion_cfg.get("error"):
                try:
                    _mdir = engine.project_dir(task["project_id"]) / "render"
                    _mdir.mkdir(parents=True, exist_ok=True)
                    (_mdir / "motion_evidence.json").write_text(json.dumps({
                        "schema": "motion-render-evidence-v1",
                        "config_source": motion_cfg_src if motion_plan is not None else None,
                        "config": {k: v for k, v in motion_cfg.items() if k != "error"},
                        "config_error": motion_cfg.get("error"),
                        "plan_artifact_hash": (motion_plan or {}).get("artifact_hash"),
                        "plan_counts": (motion_plan or {}).get("counts"),
                        "policy": (motion_plan or {}).get("policy"),
                        "applied": [e for e in motion_evidence
                                    if e["status"] == "MOTION_APPLIED"],
                        "fallback": [e for e in motion_evidence
                                     if e["status"] != "MOTION_APPLIED"],
                        "fallback_code": MOTION_FALLBACK_CODE if any(
                            e["status"] != "MOTION_APPLIED" for e in motion_evidence) else None,
                        "executed": False, "rendered": True,
                    }, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
                except Exception:                                             # noqa: BLE001
                    pass
            filters.append("".join(f"[v{i}]" for i in range(n)) +
                           f"concat=n={n}:v=1:a=0[vc]")
            filters.append("[vc]" + ",".join(vf_parts + [fade]) + "[vout]")
            if narration_audio_render is not None:
                inputs += ["-i", str(engine.project_dir(task["project_id"]) / narration_audio_render)]
                filters.append(f"[{n}:a]" + _af("apad") + "[aout]")
                amap = "[aout]"
            else:
                inputs += ["-f", "lavfi", "-t", f"{total:.2f}", "-i",
                           f"sine=frequency=220:duration={total:.2f}"]
                filters.append(f"[{n}:a]" + _af() + "[aout]")
                amap = "[aout]"
            return [*inputs,
                    "-filter_complex", ";".join(filters),
                    "-map", "[vout]", "-map", amap,
                    *_enc,
                    "-t", f"{total:.2f}"]

        # ---- 无任何素材：单张背景（Phase 1 行为）或纯色底 ----
        if background_image:
            vf = ",".join([f"scale={tw}:{th}:force_original_aspect_ratio=increase",
                           f"crop={tw}:{th}"] + vf_parts + [fade])
            if narration_audio_render is not None:
                return ["-loop", "1", "-t", f"{total:.2f}", "-i", str(background_image),
                        "-i", str(engine.project_dir(task["project_id"]) / narration_audio_render),
                        "-vf", vf, "-af", _af("apad"), "-map", "0:v", "-map", "1:a",
                        *_enc,
                        "-t", f"{total:.2f}"]
            return ["-loop", "1", "-t", f"{total:.2f}", "-i", str(background_image),
                    "-f", "lavfi", "-t", f"{total:.2f}", "-i",
                    f"sine=frequency=220:duration={total:.2f}",
                    "-vf", vf, "-af", _af(), "-map", "0:v", "-map", "1:a",
                    *_enc,
                    "-t", f"{total:.2f}"]
        vf = ",".join(vf_parts + [fade])
        if narration_audio_render is not None:
            return [
                "-i", str(engine.project_dir(task["project_id"]) / narration_audio_render),
                "-f", "lavfi", "-i",
                f"color=c=0x0b1226:size={tw}x{th}:rate={fps}:duration={total:.2f}",
                "-vf", vf, "-af", _af("apad"),
                "-map", "1:v", "-map", "0:a",
                *_enc,
                "-t", f"{total:.2f}",
            ]
        return [
            "-f", "lavfi", "-i",
            f"color=c=0x0b1226:size={tw}x{th}:rate={fps}:duration={total:.2f}",
            "-f", "lavfi", "-i", f"sine=frequency=220:duration={total:.2f}",
            "-vf", vf, "-af", _af(),
            *_enc,
            "-t", f"{total:.2f}",
        ]
