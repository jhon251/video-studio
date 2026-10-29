"""validator（v3-mvp）：确定性 Validator / Safety Gate（唯一执行大门）。

四层：
  S1 schema：字段/枚举结构
  S2 结构/语义：注意力目标存在、图形 ≤12 字且≠整句、运动必要性、关系声明、
     **反模板规则**（模板名黑名单 + "因为这是X句所以用Y模板"句式 → REJECT）
  S3 安全/Truth：白名单/rights/阈值/素材一致、数字⊆原文、稿文未改、不重检索
  S4 完整性：层数 ≤3、无幻觉计划（抠像/分割/生成式等不可执行行为 → REJECT）

结论：PASS / PASS_WITH_REPAIRS（junk ≤5% 留痕）/ REJECTED（绝不执行）。
"""
from __future__ import annotations

import re

from video_studio.stage33 import schemas
from video_studio.stage33.planner_fallback import NUM_RE, detect_beat_types

STRIP = re.compile(r"[，。；！？、\s\u3000]")
CAPABILITY_VIOLATION = re.compile(r"(抠像|物体分割|语义分割|生成式|风格化|重绘|路径动画)")
TEMPLATE_REASON = re.compile(schemas.TEMPLATE_REASON_PATTERN)
# 全字段数字/数值/统计量token：西方数字（含小数/单位）或中文数词+单位。
# 任何 token 必须逐字存在于口播原文，否则 = 自造事实。
NUM_TOKEN_RE = re.compile(
    r"[0-9]+(?:[.,][0-9]+)?(?:%|℃|°C|度|米|倍|年)?"
    r"|[一二两三四五六七八九十百千万亿]{1,}(?:度|米|倍|年|分之一|°C|℃)")
PLACEHOLDER_RE = re.compile(r"第一眼看\s*[XY]|[XY]→|看\s*[XY]\s*[，→]")
JUNK_PREFIXES = ("SCHEMA.", "SAFETY.", "TRUTH.")


def _strip(s: str) -> str:
    return STRIP.sub("", s or "")


class Validator:
    def __init__(self, plan: dict, ctx: dict):
        self.plan = plan
        self.ctx = ctx
        self.registry = ctx.get("registry", {})
        self.narration_by_shot = {s["shot_id"]: s["narration"] for s in ctx["shots"]}
        self.whitelist_by_shot = {s["shot_id"]: s["whitelisted_candidates"]
                                  for s in ctx["shots"]}
        self.beats = plan["beats"]
        self.repairs: list[dict] = []
        self.rejects: list[dict] = []
        self.human_flags: list[str] = []

    def _repair(self, beat_id: str, field: str, original, repaired, rule_id: str):
        self.repairs.append({"beat_id": beat_id, "field": field, "original": original,
                             "repaired": repaired, "rule_id": rule_id})
        return repaired

    def _reject(self, shot_id: str, reason: str):
        self.rejects.append({"shot_id": shot_id, "reason": reason})

    def _text_fields(self, b: dict) -> dict:
        st = b.get("statement", {})
        fields = {}
        for k in ("narrative_intent", "attention_target", "attention_path", "visual_evidence",
                  "visual_metaphor", "shot_language", "audio_relationship", "director_note",
                  "motion.necessity", "motion.describe"):
            v = (st.get(k) if "." not in k else (st.get("motion") or {}).get(k.split(".")[1]))
            fields[k] = v or ""
        layers = (st.get("composition") or {}).get("layers", [])
        for l in layers:
            fields[f"layer.{l.get('role')}"] = (l.get("content") or "") + (l.get("purpose") or "")
        stages = (st.get("temporal_behavior") or {}).get("stages", [])
        for s in stages:
            fields[f"stage.{s.get('name')}"] = (s.get("action") or "") + (s.get("purpose") or "")
        gl = st.get("graphic_layer") or {}
        fields["graphic.text"] = gl.get("text") or ""
        for rk in ("relation_to_previous", "relation_to_next"):
            r = st.get(rk) or {}
            fields[f"{rk}.explain"] = r.get("explain") or ""
        return fields

    def _iter_text(self, st: dict):
        """(path, value) 遍历 statement 全部文本字段（含嵌套）。"""
        yield "narrative_intent", st.get("narrative_intent") or ""
        yield "attention_target", st.get("attention_target") or ""
        yield "attention_path", st.get("attention_path") or ""
        yield "visual_evidence", st.get("visual_evidence") or ""
        yield "visual_metaphor", st.get("visual_metaphor") or ""
        yield "shot_language", st.get("shot_language") or ""
        yield "audio_relationship", st.get("audio_relationship") or ""
        yield "director_note", st.get("director_note") or ""
        m = st.get("motion") or {}
        yield "motion.necessity", m.get("necessity") or ""
        yield "motion.describe", m.get("describe") or ""
        gl = st.get("graphic_layer") or {}
        yield "graphic_layer.text", gl.get("text") or ""
        yield "graphic_layer.purpose", gl.get("purpose") or ""
        for i, l in enumerate((st.get("composition") or {}).get("layers", []) or []):
            yield f"layers.{i}.content", l.get("content") or ""
            yield f"layers.{i}.purpose", l.get("purpose") or ""
        for i, s in enumerate((st.get("temporal_behavior") or {}).get("stages", []) or []):
            yield f"stages.{i}.action", s.get("action") or ""
            yield f"stages.{i}.purpose", s.get("purpose") or ""
        for rk in ("relation_to_previous", "relation_to_next"):
            r = st.get(rk) or {}
            yield f"{rk}.explain", r.get("explain") or ""

    def _set_text(self, st: dict, path: str, value: str):
        if path == "narrative_intent":
            st["narrative_intent"] = value
        elif path == "attention_target":
            st["attention_target"] = value
        elif path == "attention_path":
            st["attention_path"] = value
        elif path == "visual_evidence":
            st["visual_evidence"] = value
        elif path == "visual_metaphor":
            st["visual_metaphor"] = value
        elif path == "shot_language":
            st["shot_language"] = value
        elif path == "audio_relationship":
            st["audio_relationship"] = value
        elif path == "director_note":
            st["director_note"] = value
        elif path == "motion.necessity":
            st.setdefault("motion", {})["necessity"] = value
        elif path == "motion.describe":
            st.setdefault("motion", {})["describe"] = value
        elif path == "graphic_layer.text":
            st.setdefault("graphic_layer", {})["text"] = value
        elif path == "graphic_layer.purpose":
            st.setdefault("graphic_layer", {})["purpose"] = value
        elif path.startswith("layers."):
            i = int(path.split(".")[1])
            key = path.split(".")[2]
            st["composition"]["layers"][i][key] = value
        elif path.startswith("stages."):
            i = int(path.split(".")[1])
            key = path.split(".")[2]
            st["temporal_behavior"]["stages"][i][key] = value
        elif path.endswith(".explain"):
            rk = path.split(".")[0]
            st.setdefault(rk, {})["explain"] = value

    def stage_truth_text(self):
        """全字段事实校验：任何数字/数值 token 必须逐字存在于口播原文；否则剔除并留痕。"""
        for b in self.beats:
            st = b.get("statement", {})
            nar = self.narration_by_shot.get(b["shot_id"], "")
            mat_id = st.get("evidence_material") or ""
            for path, val in self._iter_text(st):
                if not val:
                    continue
                newval = val
                for m in NUM_TOKEN_RE.finditer(val):
                    tok = m.group(0)
                    # 素材 ID 内的数字是白名单资源引用，不是事实
                    if tok in nar or (mat_id and tok in mat_id):
                        continue
                    newval = newval.replace(tok, "", 1)
                    self.repairs.append(
                        {"beat_id": b["beat_id"], "field": path, "original": tok,
                         "repaired": "removed", "rule_id": "TRUTH.FACT_INVENTED"})
                if newval != val:
                    newval = re.sub(r"[±≈~]\s*", "", newval)
                    newval = re.sub(r"\s{2,}", " ", newval).strip(" ，。；、")
                    if path == "visual_evidence" and not newval:
                        newval = f"口播原文「{st.get('attention_target', '')}」"
                    self._set_text(st, path, newval)

    def stage_consistency(self):
        """placeholder / path-target 一致 / motion 矛盾 的确定性修复。"""
        for b in self.beats:
            st = b.get("statement", {})
            target = st.get("attention_target") or ""
            has_num = bool(NUM_TOKEN_RE.search(target))
            # 1) placeholder 泄漏
            for path, val in self._iter_text(st):
                if PLACEHOLDER_RE.search(val):
                    fixed = ("先看焦点词，再看它与全句的关系" if path == "attention_path"
                             else val.replace("第一眼看X→第二眼理解Y", "先看焦点，再理解关系")
                             .replace("X", target[:6]).replace("Y", "全句"))
                    self._set_text(st, path, fixed)
                    self._repair(b["beat_id"], path, val, fixed, "SEMANTIC.PLACEHOLDER")
            # 2) path 与 target 一致：target 非数字而 path 说"看数字" → 修复
            path = st.get("attention_path") or ""
            if "数字" in path and not has_num:
                fixed = f"先看「{target}」，再理解它与全句的关系"
                st["attention_path"] = fixed
                self._repair(b["beat_id"], "attention_path", path, fixed,
                             "SEMANTIC.PATH_TARGET")
            # 3) motion 一致性：intent≠none 但 necessity 声称静止 → intent=none；
            #    intent=none 但 necessity 声称删掉有损失 → 改成静止理由
            m = st.get("motion") or {}
            intent, necessity = m.get("intent"), m.get("necessity") or ""
            if intent != "none" and ("静止" in necessity or "不会损失" in necessity):
                m["intent"] = "none"
                m["describe"] = "保持绝对静止"
                m["necessity"] = "静止即完整表达，删掉运动观众不会损失信息"
                self._repair(b["beat_id"], "motion.intent", intent, "none",
                             "SEMANTIC.MOTION_CONSIST")
            elif intent == "none" and necessity and \
                    ("删掉" in necessity and "损失" in necessity and
                     "不会损失" not in necessity):
                m["necessity"] = "静止即完整表达，删掉运动观众不会损失信息"
                m["describe"] = "保持绝对静止"
                self._repair(b["beat_id"], "motion.necessity", necessity,
                             m["necessity"], "SEMANTIC.MOTION_CONSIST")

    def stage_schema(self):
        for b in self.beats:
            st = b.get("statement", {})
            if not isinstance(st, dict) or not st:
                self._reject(b["shot_id"], "statement 缺失")
                continue
            if st.get("evidence_material") is not None and \
                    not isinstance(st["evidence_material"], str):
                st["evidence_material"] = self._repair(
                    b["beat_id"], "evidence_material", st["evidence_material"], None,
                    "SCHEMA.EVIDENCE_MATERIAL")
            m = st.get("motion") or {}
            if m.get("intent") not in schemas.MOTION_INTENTS:
                m["intent"] = self._repair(b["beat_id"], "motion.intent", m.get("intent"),
                                           "none", "SCHEMA.MOTION_INTENT")
            for rk in ("relation_to_previous", "relation_to_next"):
                r = st.get(rk) or {}
                if r.get("type") not in schemas.RELATION_TYPES:
                    r["type"] = self._repair(b["beat_id"], f"{rk}.type", r.get("type"),
                                             "none", "SCHEMA.RELATION_TYPE")
            layers = (st.get("composition") or {}).get("layers", []) or []
            if len(layers) > schemas.CAPS["LAYERS_MAX"]:
                layers = layers[:schemas.CAPS["LAYERS_MAX"]]
                self._repair(b["beat_id"], "composition.layers", ">3", layers,
                             "SCHEMA.LAYERS_MAX")
            for l in layers:
                if l.get("role") not in schemas.LAYER_ROLES:
                    l["role"] = self._repair(b["beat_id"], "layer.role", l.get("role"),
                                             "foreground", "SCHEMA.LAYER_ROLE")
            stages = (st.get("temporal_behavior") or {}).get("stages", []) or []
            for s in stages:
                if s.get("name") not in schemas.STAGE_NAMES:
                    s["name"] = self._repair(b["beat_id"], "stage.name", s.get("name"),
                                             "hold", "SCHEMA.STAGE_NAME")

    def stage_structural(self):
        for b in self.beats:
            st = b.get("statement", {})
            text = b["beat_text"]
            fields = self._text_fields(b)
            # 反模板：黑名单
            for fname, fval in fields.items():
                for bad in schemas.TEMPLATE_NAMES_BLACKLIST:
                    if bad in fval:
                        self._reject(b["shot_id"], f"{fname} 含模板名 {bad}")
                        break
            # 反模板：句式
            for fname, fval in fields.items():
                if TEMPLATE_REASON.search(fval):
                    self._reject(b["shot_id"], f"{fname} 模板式决策句式")
            # 幻觉计划
            for fname, fval in fields.items():
                if CAPABILITY_VIOLATION.search(fval):
                    self._reject(b["shot_id"], f"{fname} 要求不可执行行为")
            # attention_target 必须是原文子串
            at = st.get("attention_target") or ""
            if at and at not in text:
                m = NUM_RE.search(text)
                fixed = m.group(0) if m else _strip(text)[:6]
                st["attention_target"] = self._repair(
                    b["beat_id"], "attention_target", at, fixed, "SEMANTIC.ATTENTION_TARGET")
            if not st.get("attention_target"):
                st["attention_target"] = self._repair(
                    b["beat_id"], "attention_target", "", _strip(text)[:6],
                    "SEMANTIC.ATTENTION_TARGET")
            # graphic 文本：⊆ 原文、≤12、≠整句（整句=该镜口播全文，字幕已承载）
            gl = st.get("graphic_layer") or {}
            gt = gl.get("text") or ""
            full_narration = _strip(self.narration_by_shot.get(b["shot_id"], ""))
            if gt:
                if _strip(gt) == full_narration:
                    self._reject(b["shot_id"], "graphic_layer 全文复制（字幕重复）")
                elif len(gt) > schemas.CAPS["GRAPHIC_TEXT_MAX"] or gt not in text:
                    fixed = (st.get("attention_target") or _strip(text)[:6])[:12]
                    gl["text"] = self._repair(b["beat_id"], "graphic_layer.text", gt,
                                              fixed, "SEMANTIC.GRAPHIC_TEXT")
            # motion.necessity 必须非空且足够长
            mn = (st.get("motion") or {}).get("necessity") or ""
            if len(_strip(mn)) < schemas.CAPS["MOTION_NECESSITY_MIN"]:
                st.setdefault("motion", {})["necessity"] = self._repair(
                    b["beat_id"], "motion.necessity", mn,
                    "静止即完整表达，删掉运动观众不会损失信息", "SEMANTIC.MOTION_NECESSITY")
            # 无素材 beat 必须有 metaphor
            if st.get("evidence_material") is None and \
                    not (_strip(st.get("visual_metaphor") or "")):
                st["visual_metaphor"] = self._repair(
                    b["beat_id"], "visual_metaphor", "",
                    f"以原文词「{st.get('attention_target')}」为唯一焦点做最小构图演绎",
                    "SEMANTIC.METAPHOR_REQUIRED")
            # director_note ≤80
            dn = st.get("director_note") or ""
            if len(dn) > schemas.CAPS["DIRECTOR_NOTE_MAX"]:
                st["director_note"] = self._repair(
                    b["beat_id"], "director_note", dn, dn[:80], "SEMANTIC.NOTE_LEN")
            # 层职责非空
            for l in (st.get("composition") or {}).get("layers", []) or []:
                if not _strip(l.get("purpose") or ""):
                    l["purpose"] = self._repair(
                        b["beat_id"], f"layer.{l.get('role')}.purpose", "",
                        f"承载{l.get('content','元素')}", "SEMANTIC.LAYER_PURPOSE")

    def stage_safety(self):
        for b in self.beats:
            st = b.get("statement", {})
            sid = b["shot_id"]
            mat = st.get("evidence_material")
            if mat is not None:
                reg = self.registry.get(mat)
                if not reg or reg["shot_id"] != sid:
                    st["evidence_material"] = self._repair(
                        b["beat_id"], "evidence_material", mat, None,
                        "SAFETY.MATERIAL_OUT_OF_WHITELIST")
                    if not _strip(st.get("visual_metaphor") or ""):
                        st["visual_metaphor"] = (
                            f"以原文词「{st.get('attention_target')}」为唯一焦点"
                            f"做最小构图演绎")
                else:
                    st["_material_rights"] = reg["rights_status"]
            # 锚点数字 ⊆ 原文（graphic text 已强制 ⊆，此处复核）
            gl = st.get("graphic_layer") or {}
            for n in NUM_RE.findall(gl.get("text") or ""):
                if n not in b["beat_text"]:
                    self._repair(b["beat_id"], "graphic.text.number", n, None,
                                 "TRUTH.NUMBER_VERBATIM")
                    gl["text"] = gl["text"].replace(n, "")
            gl["text"] = (gl.get("text") or "")[:12]

    def stage_integrity(self):
        for b in self.beats:
            st = b.get("statement", {})
            layers = (st.get("composition") or {}).get("layers", []) or []
            if len(layers) > schemas.CAPS["LAYERS_MAX"]:
                self._reject(b["shot_id"], "层数 >3")
            m = st.get("motion") or {}
            if m.get("intent") == "none" and "动" in (m.get("describe") or "") and \
                    "静止" not in (m.get("describe") or ""):
                self.human_flags.append(f"{b['beat_id']}: motion.intent=none 但 describe 提到运动")

    def run(self) -> dict:
        self.stage_schema()
        self.stage_structural()
        self.stage_consistency()
        self.stage_truth_text()
        self.stage_safety()
        self.stage_integrity()
        n = len(self.beats)
        junk = [r for r in self.repairs
                if r["rule_id"].startswith(JUNK_PREFIXES)]
        junk_rate = len(junk) / max(n, 1)
        if self.rejects:
            gate = "REJECTED"
        elif junk_rate > schemas.CAPS["REPAIR_RATE_MAX"]:
            gate = "REJECTED"
        elif self.repairs:
            gate = "PASS_WITH_REPAIRS"
        else:
            gate = "PASS"
        self.plan["validator_log"] = {
            "gate": gate, "repairs_total": len(self.repairs),
            "repairs_junk": len(junk), "repair_rate_junk": round(junk_rate, 3),
            "repair_rate_total": round(len(self.repairs) / max(n, 1), 3),
            "structural_rejects": self.rejects, "field_repairs": self.repairs,
        }
        self.plan["human_review_flags"] = self.human_flags
        return {"gate": gate, "rejects": self.rejects, "repairs": self.repairs,
                "junk": junk, "budget": {}}
