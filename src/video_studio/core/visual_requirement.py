# -*- coding: utf-8 -*-
"""P7-1：**VisualRequirement 契约**（机器可读视觉需求；确定性/离线，无网络、无 LLM 调用）。

设计原则（P7 目标序：visual relevance > semantic coverage > diversity > quantity）
--------------------------------------------------------------------------
1. **不臆造**：任何字段若当前输入无法可靠推导，必须显式 `NOT_DERIVABLE`，绝不"填满 schema"。
2. **可复算**：同一输入 ⇒ 同一规范化表示 ⇒ 同一 hash（字段顺序/key 顺序/空白/Unicode 形式/
   列表顺序均不影响 hash）。
3. **可追溯**：每条 requirement 带 `provenance`（源 artifact id / 路径 / sha256 / 实际用到的字段 /
   所用规则 id）。
4. **fail-closed**：身份或溯源缺失/不一致 ⇒ `VisualRequirementError`（INVALID），
   不静默降级、不产半成品。

三态语义
--------
* `DERIVABLE`     —— 输入中存在**显式**依据（或可用既有确定性规则从输入文本机械抽取）。
* `NOT_DERIVABLE` —— 输入中**根本不存在**该类信息（例如自由文本里没有结构化 subject/action）。
* `INVALID`       —— 违反身份/溯源/结构约束（构造期即抛错，不会出现在产物中）。

字段级说明见 `FIELD_SPEC`（每字段：为什么需要 / 来源 / 是否允许推断 / 无法获得时如何表示）。
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata

SCHEMA = "visual-requirement-v1"
ARTIFACT_SCHEMA = "visual-requirements-artifact-v1"
ARTIFACT_VERSION = 1

STATUS_DERIVABLE = "DERIVABLE"
STATUS_NOT_DERIVABLE = "NOT_DERIVABLE"
STATUS_INVALID = "INVALID"
STATUSES = (STATUS_DERIVABLE, STATUS_NOT_DERIVABLE, STATUS_INVALID)

#: requirement 的**必需字段**（结构与类型；值可为 None 表示 NOT_DERIVABLE）
REQUIRED_FIELDS = ("requirement_id", "scene_id", "subject", "action", "object", "environment",
                   "concept", "visual_goal", "evidence_type", "queries_en", "query_ladder",
                   "concepts_pos", "concepts_neg", "avoid_list", "expected_kind", "reuse_policy",
                   "min_match_score", "status", "field_status", "provenance",
                   "deterministic_hash")

#: **无序**列表字段（规范化时排序+去重）；`query_ladder` 为**有序**阶梯，不排序
UNORDERED_LIST_FIELDS = ("queries_en", "concepts_pos", "concepts_neg", "avoid_list")
ORDERED_LIST_FIELDS = ("query_ladder",)

_WS = re.compile(r"\s+")
_SCENE_ID = re.compile(r"^S\d{2}$")

#: 每字段：为什么需要 / 来源 / 是否允许推断 / 无法获得时的表示
FIELD_SPEC = {
    "requirement_id": {
        "why": "需求自身的稳定标识，供候选/绑定/台账跨阶段引用",
        "source": "由规范化 body 的 sha256 派生（vr-<前16位>）",
        "infer_allowed": False, "when_unavailable": "不可能缺失（由 hash 生成）"},
    "scene_id": {
        "why": "把需求绑定到确定镜头；跨 artifact 一致性锚点",
        "source": "source render_output.material_timeline[i].scene_id（显式）",
        "infer_allowed": False, "when_unavailable": "INVALID（fail-closed：身份不可缺）"},
    "subject": {
        "why": "画面的主体（谁/什么），决定检索词与相关性判定",
        "source": "**当前输入无结构化来源**（自由文本无法可靠解析）",
        "infer_allowed": False,
        "when_unavailable": "NOT_DERIVABLE（需 LLM structured extraction 并附证据引用）"},
    "action": {
        "why": "主体在做什么，决定候选人/物/场景类别",
        "source": "**当前输入无结构化来源**", "infer_allowed": False,
        "when_unavailable": "NOT_DERIVABLE"},
    "object": {
        "why": "动作对象/被展示物（如论文页、代码、图）",
        "source": "**当前输入无结构化来源**", "infer_allowed": False,
        "when_unavailable": "NOT_DERIVABLE"},
    "environment": {
        "why": "环境/场所/背景（影响素材风格与可用性）",
        "source": "**当前输入无结构化来源**", "infer_allowed": False,
        "when_unavailable": "NOT_DERIVABLE"},
    "concept": {
        "why": "抽象概念（如 surveyability / formal verification），用于语义匹配",
        "source": "**当前输入无结构化来源**", "infer_allowed": False,
        "when_unavailable": "NOT_DERIVABLE"},
    "visual_goal": {
        "why": "该镜应呈现的画面意图（给候选准入与相关性判定的第一依据）",
        "source": "上游**显式**字段 shot_description / shot_gen_prompt",
        "infer_allowed": False,
        "when_unavailable": "NOT_DERIVABLE（不根据旁白想象画面）"},
    "evidence_type": {
        "why": "所需视觉证据类型（照片/截图/图表/文档…），决定来源与许可策略",
        "source": "上游显式 shot.source（+ shot_size）经**固定映射表**",
        "infer_allowed": False,
        "when_unavailable": "NOT_DERIVABLE（不猜来源类型）"},
    "queries_en": {
        "why": "面向外部素材库的检索词（英文/拉丁 token 为跨库通用形式）",
        "source": "输入文本中**已存在的** ASCII/拉丁 token（≥3 字符）——**不做翻译**",
        "infer_allowed": False,
        "when_unavailable": "NOT_DERIVABLE（无拉丁 token ⇒ 不生成英文查询）"},
    "query_ladder": {
        "why": "检索阶梯（由窄到宽），供 P7-5 采集时按序尝试",
        "source": "仅由 queries_en / concepts_pos 中**已存在**的 token 机械组合",
        "infer_allowed": False,
        "when_unavailable": "NOT_DERIVABLE（随 queries_en 缺失而缺失）"},
    "concepts_pos": {
        "why": "正向概念线索（年份/数字/专名等表层 token），用于匹配与可解释性",
        "source": "输入文本中的数字/年份 + ASCII token（≥2 字符，去停用词）",
        "infer_allowed": False,
        "when_unavailable": "NOT_DERIVABLE（0 命中即视为无法确定概念内容）"},
    "concepts_neg": {
        "why": "负向概念线索（明确不想要的语义）",
        "source": "显式否定短语（core.materials.extract_constraints 既有规则）",
        "infer_allowed": False,
        "when_unavailable": "NOT_DERIVABLE（无源文本时）"},
    "avoid_list": {
        "why": "显式禁用项（品牌/logo/人物等），候选准入硬约束",
        "source": "显式 constraints[] + style_constraint/gen_prompt 中的否定短语（既有规则）",
        "infer_allowed": False, "when_unavailable": "NOT_DERIVABLE（无源文本时）"},
    "expected_kind": {
        "why": "期望素材种类（image/video…），决定解码与时长校验",
        "source": "上游显式 original_requirement.expected_kind", "infer_allowed": False,
        "when_unavailable": "NOT_DERIVABLE"},
    "reuse_policy": {
        "why": "复用策略（allow/prefer_unused/forbid），与 DQ-2 口径一致",
        "source": "上游显式 original_requirement.reuse_policy", "infer_allowed": False,
        "when_unavailable": "NOT_DERIVABLE"},
    "min_match_score": {
        "why": "候选准入阈值（沿用冻结口径，P7-1 不修改）",
        "source": "上游显式 original_requirement.min_match_score", "infer_allowed": False,
        "when_unavailable": "NOT_DERIVABLE"},
    "status": {
        "why": "本条需求整体可推导性（决定后续是否允许进入获取/绑定）",
        "source": "由字段级状态机械汇总", "infer_allowed": False,
        "when_unavailable": "INVALID（不可能缺失）"},
    "field_status": {
        "why": "**字段级**可推导性与来源（防止把缺失当已知）",
        "source": "构建期逐字段记录", "infer_allowed": False,
        "when_unavailable": "INVALID（不可能缺失）"},
    "provenance": {
        "why": "溯源：源 artifact/文件 id+sha256、实际使用的字段、所用规则 id",
        "source": "构建期记录", "infer_allowed": False,
        "when_unavailable": "INVALID（无溯源不得生成需求）"},
    "deterministic_hash": {
        "why": "确定性哈希：同输入同 hash；跨阶段引用与防篡改",
        "source": "规范化 body 的 sha256", "infer_allowed": False,
        "when_unavailable": "INVALID（不可能缺失）"},
}

#: evidence_type 固定映射（仅**显式** shot.source 才映射；不改写上游数据）
EVIDENCE_TYPE_MAP = {
    "screen_capture": "screenshot", "screenshot": "screenshot",
    "code": "code_screenshot", "code_screenshot": "code_screenshot",
    "stock_photo": "photograph", "photo": "photograph", "photograph": "photograph",
    "chart": "data_visual", "diagram": "data_visual", "infographic": "data_visual",
    "document": "document_scan", "scan": "document_scan", "paper": "document_scan",
    "video": "video_clip", "broll": "video_clip", "ai_generated": "ai_generated",
    # 实测上游 shot.source 取值（visual_plan_output）：ai_generate ×7、stock ×1
    "ai_generate": "ai_generated", "stock": "stock_photo",
}
STOPWORDS_EN = frozenset({
    "the", "and", "for", "with", "that", "this", "from", "are", "was", "were", "not", "but",
    "you", "his", "her", "its", "our", "their", "has", "have", "had", "will", "would", "can",
    "could", "into", "than", "then", "them", "they", "there", "here", "when", "what", "which",
    "who", "how", "why", "all", "any", "one", "two", "out", "off", "over", "under", "about",
})


class VisualRequirementError(RuntimeError):
    """构造/校验失败（fail-closed）。`code` 见模块内 INVALID_* 常量。"""

    def __init__(self, code: str, detail: str = ""):
        super().__init__("[{}] {}".format(code, detail))
        self.code = code
        self.detail = detail


INVALID_SCENE_ID = "VR_INVALID_SCENE_ID"
INVALID_DUPLICATE_SCENE = "VR_INVALID_DUPLICATE_SCENE"
INVALID_MISSING_PROVENANCE = "VR_INVALID_MISSING_PROVENANCE"
INVALID_SOURCE_HASH = "VR_INVALID_SOURCE_HASH"
INVALID_SCHEMA = "VR_INVALID_SCHEMA"
INVALID_HASH_MISMATCH = "VR_INVALID_HASH_MISMATCH"
INVALID_NO_SOURCE_TEXT = "VR_INVALID_NO_SOURCE_TEXT"
INVALID_HALLUCINATION = "VR_INVALID_HALLUCINATION_NO_EVIDENCE"

#: 这五个字段属"深层语义"：一旦赋值，**必须**在 provenance.evidence_refs 中给出该字段的证据引用，
#: 否则视为"为填满 schema 而臆造" ⇒ fail-closed（P7-1 的确定性 builder 从不赋值它们）。
EVIDENCE_REQUIRED_FIELDS = ("subject", "action", "object", "environment", "concept")


# ---------------------------------------------------------------- 规范化
def norm_text(v) -> str | None:
    """NFC + 空白折叠 + 去首尾；空 ⇒ None。"""
    if v is None:
        return None
    s = unicodedata.normalize("NFC", str(v))
    s = _WS.sub(" ", s).strip()
    return s or None


def norm_list(v, ordered: bool = False) -> list | None:
    """列表规范化：NFC/空白折叠/去空；无序列表去重并排序；有序列表保序。"""
    if v is None:
        return None
    if isinstance(v, (str, bytes)):
        v = [v]
    items, seen = [], set()
    for x in v:
        if isinstance(x, (list, tuple)):
            sub = norm_list(list(x), ordered=True)
            if sub:
                items.append(sub)
            continue
        s = norm_text(x)
        if not s:
            continue
        key = s.casefold()
        if key in seen:
            continue
        seen.add(key)
        items.append(s)
    if not ordered:
        items.sort(key=lambda s: (s.casefold(), s))
    return items


def canonical(obj) -> str:
    """规范化 JSON（key 排序、紧凑分隔符、保 UTF-8）；用于哈希与字节级比较。"""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
                      default=str)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def requirement_body(req: dict) -> dict:
    """参与哈希的 body：去掉 `deterministic_hash` 及**由它派生**的 `requirement_id`（避免自引用）。"""
    return {k: v for k, v in req.items() if k not in ("deterministic_hash", "requirement_id")}


def requirement_hash(req: dict) -> str:
    return sha256_text(canonical(requirement_body(req)))


def artifact_body(art: dict) -> dict:
    return {k: v for k, v in art.items() if k != "artifact_hash"}


def artifact_hash(art: dict) -> str:
    return sha256_text(canonical(artifact_body(art)))


def field_status(status: str, source: str, reason: str = "", inferred: bool = False) -> dict:
    if status not in STATUSES:
        raise VisualRequirementError(INVALID_SCHEMA, "未知字段状态 {}".format(status))
    out = {"status": status, "source": source, "inferred": bool(inferred)}
    if reason:
        out["reason"] = reason
    return out


# ---------------------------------------------------------------- 校验
def validate_requirement(req: dict) -> list[str]:
    """结构校验；返回错误列表（空 ⇒ 合法）。不修改入参。"""
    errs: list[str] = []
    if not isinstance(req, dict):
        return ["requirement 必须是对象"]
    for f in REQUIRED_FIELDS:
        if f not in req:
            errs.append("缺少字段 {}".format(f))
    if req.get("schema") != SCHEMA:
        errs.append("schema 必须为 {}".format(SCHEMA))
    sid = req.get("scene_id")
    if not isinstance(sid, str) or not _SCENE_ID.match(sid or ""):
        errs.append("scene_id 非法：{!r}".format(sid))
    if req.get("status") not in (STATUS_DERIVABLE, STATUS_NOT_DERIVABLE):
        errs.append("status 非法：{!r}".format(req.get("status")))
    fs = req.get("field_status")
    if not isinstance(fs, dict) or not fs:
        errs.append("field_status 缺失或为空")
    else:
        for name in REQUIRED_FIELDS:
            if name in ("requirement_id", "scene_id", "status", "field_status", "provenance",
                        "deterministic_hash", "schema"):
                continue
            if name not in fs:
                errs.append("field_status 缺少 {}".format(name))
            elif fs[name].get("status") not in (STATUS_DERIVABLE, STATUS_NOT_DERIVABLE):
                errs.append("field_status[{}] 状态非法".format(name))
    prov = req.get("provenance")
    if not isinstance(prov, dict) or not prov.get("source_id") or not prov.get("source_sha256"):
        errs.append("provenance 缺失 source_id/source_sha256")
    h = req.get("deterministic_hash")
    if not isinstance(h, str) or len(h) != 64:
        errs.append("deterministic_hash 缺失或非法")
    elif h != requirement_hash(req):
        errs.append("deterministic_hash 与 body 不一致")
    # 无序列表必须已规范化（排序+去重）
    for f in UNORDERED_LIST_FIELDS:
        v = req.get(f)
        if isinstance(v, list) and v != norm_list(v):
            errs.append("{} 未按规范化（排序/去重）".format(f))
    return errs


def make_requirement(*, scene_id: str, values: dict, statuses: dict, provenance: dict) -> dict:
    """构造一条 requirement（规范化 → 状态汇总 → 哈希）。任何身份/溯源问题即抛错。"""
    if not isinstance(scene_id, str) or not _SCENE_ID.match(scene_id):
        raise VisualRequirementError(INVALID_SCENE_ID, repr(scene_id))
    if not isinstance(provenance, dict) or not provenance.get("source_id") \
            or not provenance.get("source_sha256"):
        raise VisualRequirementError(INVALID_MISSING_PROVENANCE, str(provenance)[:120])
    req = {"schema": SCHEMA, "scene_id": scene_id}
    ev_refs = provenance.get("evidence_refs") or {}
    ev_keys = set(ev_refs.keys()) if isinstance(ev_refs, dict) else set(ev_refs)
    provided_sem = [f for f in EVIDENCE_REQUIRED_FIELDS if norm_text(values.get(f))]
    missing_ev = [f for f in provided_sem if f not in ev_keys]
    if missing_ev:
        raise VisualRequirementError(
            INVALID_HALLUCINATION,
            "字段 {} 有值但 provenance.evidence_refs 未给出证据引用（禁止臆造）".format(missing_ev))
    for name in ("subject", "action", "object", "environment", "concept"):
        v = norm_text(values.get(name))
        req[name] = v
        statuses.setdefault(name, field_status(
            STATUS_DERIVABLE if v else STATUS_NOT_DERIVABLE,
            "structured-extraction+evidence_ref" if v else "none",
            "" if v else "当前输入无结构化来源"))
    req["visual_goal"] = norm_text(values.get("visual_goal"))
    req["evidence_type"] = norm_text(values.get("evidence_type"))
    req["queries_en"] = norm_list(values.get("queries_en"))
    req["query_ladder"] = norm_list(values.get("query_ladder"), ordered=True)
    for f in ("concepts_pos", "concepts_neg", "avoid_list"):
        req[f] = norm_list(values.get(f))
    req["expected_kind"] = norm_text(values.get("expected_kind"))
    req["reuse_policy"] = norm_text(values.get("reuse_policy"))
    mk_ = values.get("min_match_score")
    req["min_match_score"] = int(mk_) if isinstance(mk_, (int, float)) else None
    # 其余字段的默认状态（调用方未显式给出时）：有值 ⇒ DERIVABLE(source=explicit)，无值 ⇒ NOT_DERIVABLE
    for name in ("visual_goal", "evidence_type", "queries_en", "query_ladder", "concepts_pos",
                 "concepts_neg", "avoid_list", "expected_kind", "reuse_policy",
                 "min_match_score"):
        if name in statuses:
            continue
        has = req[name] not in (None, [], "")
        statuses[name] = field_status(
            STATUS_DERIVABLE if has else STATUS_NOT_DERIVABLE,
            "explicit" if has else "none",
            "" if has else "调用方未提供该字段来源")
    # 状态汇总：核心（visual_goal）或概念线索可用 ⇒ DERIVABLE；否则 NOT_DERIVABLE
    core_ok = statuses.get("visual_goal", {}).get("status") == STATUS_DERIVABLE \
        or statuses.get("concepts_pos", {}).get("status") == STATUS_DERIVABLE
    req["status"] = STATUS_DERIVABLE if core_ok else STATUS_NOT_DERIVABLE
    req["field_status"] = {k: statuses[k] for k in sorted(statuses)}
    req["provenance"] = provenance
    req["deterministic_hash"] = requirement_hash(req)
    req["requirement_id"] = "vr-" + req["deterministic_hash"][:16]
    errs = validate_requirement(req)
    if errs:
        raise VisualRequirementError(INVALID_SCHEMA, "; ".join(errs[:6]))
    return req


# ---------------------------------------------------------------- 未来接口（仅定义，不调用）
class StructuredExtractor:                                            # pragma: no cover
    """**未来** LLM 结构化抽取接口（P7-1 仅定义，不实现、不调用、无网络）。

    实现者必须：
      · 对每个填入的字段给出 `evidence_ref`（原文片段或 artifact 引用）；
      · 无证据 ⇒ 返回 None 并把该字段标为 NOT_DERIVABLE（**不得猜测**）；
      · 输出必须经 `validate_requirement` 通过后才可进入管线；
      · 不得直接写 baseline/ledger/6-G 产物。
    """

    name = "structured-extractor-interface"
    requires_network = True

    def extract(self, scene: dict) -> dict:                            # pragma: no cover
        raise NotImplementedError("P7-1 不实现、不调用真实 LLM 抽取")


def extractor_contract() -> dict:
    """供文档/测试引用的接口契约（不触发任何外部调用）。"""
    return {"name": StructuredExtractor.name, "requires_network": True,
            "implemented_in_p7_1": False, "called_in_p7_1": False,
            "obligations": ["每字段必须带 evidence_ref", "无证据即 NOT_DERIVABLE",
                            "输出须过 validate_requirement",
                            "不得写 baseline/ledger/6-G 产物"]}
