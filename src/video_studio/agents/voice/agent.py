"""Voice Agent：配音（TTS 工具执行 + 音色方案管理）。

- provider 未配置（none）：产出配音方案产物（计划模式）。
- provider 已配置：逐段合成 → 拼接为完整旁白 → 产出 voice_output 产物。
- **3.x Phase 2-B.1（本阶段修复的真实缺陷）**：原实现把失败段只记进 `errors` 后继续，任务仍报
  SUCCEEDED、confidence=1.0，最终 `narration.mp3` 只覆盖成功段（实测 12 段只成功 1/12、9/12、7/12），
  下游 render 因 `-shortest` 把成片截短。现在：
    1. **逐段真实状态**：每段独立记录 `status/attempts/errors/bytes/duration_s/text_sha256`；
    2. **失败段独立重试**：可重试错误码（网络类）按 `tools.tts.max_attempts` 重试并退避；
    3. **成功段复用**：`media/voice/segments_manifest.json` 记录文本哈希/音色/时长，
       文本与音色未变且文件合法时**不再调用 TTS**；
    4. **失败即失败**：任一段最终失败 → 写 INCOMPLETE 证据产物后抛错（任务 FAILED→重试→BLOCKED），
       且**不覆盖**已有的完整 `narration.mp3`；
    5. **完整性/时长契约**：产物记录 expected/successful/时长与容差判定（见 `core/narration.py`）。
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from ...core.narration import (NarrationIncompleteError, duration_contract,
                               incomplete_message, narration_plan, narration_segment_indexes,
                               narration_text, probe_duration_s, script_time_base_s,
                               segment_file_ok, tolerance_ratio)
from ...tools.base import ToolContext, ToolError
from ...tools.ffmpeg_tool import FFmpegTool
from ...tools.tts_tool import TTSTool
from ..base import Agent, register

MANIFEST_REL = "media/voice/segments_manifest.json"
NARRATION_REL = "media/voice/narration.mp3"
DEFAULT_MAX_ATTEMPTS = 3
# 可重试（临时性）错误：连接/超时/DNS 等网络类；其余为实质失败
RETRYABLE_MARKERS = ("ClientConnectorError", "ClientOSError", "ServerDisconnectedError",
                     "ConnectionResetError", "ConnectionError", "TimeoutError", "timeout",
                     "getaddrinfo", "Cannot connect", "Temporary failure", "SSL")


def classify_tts_error(exc: BaseException | str) -> tuple[str, bool]:
    """把 TTS 失败归类为明确错误码 + 是否可重试。保留原始异常文本供诊断。"""
    text = str(exc)
    for m in RETRYABLE_MARKERS:
        if m.lower() in text.lower():
            return "TTS_NETWORK", True
    if "TTS_FAILED" in text or "TTS_" in text:
        return "TTS_SYNTHESIS_FAILED", False
    return "TTS_UNKNOWN", False


def _text_sha(text: str, voice: str, provider: str) -> str:
    return hashlib.sha256("{}|{}|{}".format(provider, voice, text).encode("utf-8")).hexdigest()[:32]


@register
class VoiceAgent(Agent):
    role = "voice"
    tier = "-"
    needs_llm = False
    description = "配音：音色方案、TTS 生成、时长检查。不负责混音，不修改脚本文本。"

    # ---------------- 主流程 ----------------

    def run(self, engine, task: dict) -> None:
        script = self._load_script(engine, task)
        provider = engine.config.get("tools", {}).get("tts", {}).get("provider", "none")
        voice = (task["inputs"].get("voice")
                 or engine.config.get("tools", {}).get("tts", {}).get("voice_type") or "")
        expected = narration_segment_indexes(script)
        segments = list((script or {}).get("segments") or [])

        if provider == "none":
            self._plan_only(engine, task, segments, provider)
            return
        if not expected:
            self._plan_only(engine, task, segments, provider, note="；脚本无可配音段落")
            return

        project_dir = engine.project_dir(task["project_id"])
        ctx = ToolContext(role="voice", project_id=task["project_id"], project_dir=project_dir,
                          db=engine.db, config=engine.config)
        tts = TTSTool()
        ffmpeg = FFmpegTool()
        max_attempts = self._max_attempts(engine)
        backoff = float((engine.config.get("retry") or {}).get("backoff_base_s") or 5)
        manifest = self._load_manifest(project_dir)

        records: list[dict] = []
        for i in expected:
            text = narration_text(segments[i])
            rel = "media/voice/seg_{:02d}.mp3".format(i)
            rec = self._reuse_or_synthesize(ctx, tts, ffmpeg, manifest, i, text, rel, voice,
                                            provider, max_attempts, backoff)
            records.append(rec)

        ok_records = [r for r in records if r["status"] in ("SUCCESS", "REUSED")]
        bad_records = [r for r in records if r["status"] not in ("SUCCESS", "REUSED")]
        self._save_manifest(project_dir, manifest)

        # 只有全部段齐备才（重）写 narration.mp3——避免用残缺音轨覆盖已有的完整音轨
        narration_dur, wrote, concat_error = None, False, None
        if not bad_records:
            try:
                ffmpeg.execute({"op": "concat",
                                "inputs": [r["audio"] for r in records],
                                "output": NARRATION_REL}, ctx)
                wrote = True
            except ToolError as exc:
                concat_error = {"code": "TTS_CONCAT_FAILED", "retryable": False,
                                "error": str(exc)[:200]}
            if wrote:
                narration_dur = probe_duration_s(ctx, project_dir / NARRATION_REL)

        timeline_s = script_time_base_s(script)
        # ---- Duration Contract v2：**实际 TTS 时长 = narration 事实**；audio_time_base = 生产权威 ----
        # 先按 v1 口径算一次（保留 `duration_contract` 字段兼容性），再用 v2 权威对象覆盖：
        # v2 下 "timeline" 即 audio_time_base ⇒ delta≈0、audio_padded_to_timeline=False（不再有"缺口"）。
        contract_v1 = duration_contract(timeline_s, narration_dur, tolerance_ratio(engine.config))
        _payload_for_plan = {"segments": [{k: r[k] for k in ("index", "audio", "status", "reused",
                                                             "attempts", "bytes", "duration_s",
                                                             "text_sha256")} for r in records],
                             "narration_duration_s": narration_dur}
        plan = narration_plan(script, _payload_for_plan, config=engine.config)
        base = plan.get("audio_time_base_s")
        contract = (duration_contract(base, narration_dur, tolerance_ratio(engine.config))
                    if base else contract_v1)
        if base:
            contract["policy"] = "audio_time_base_v2"
            contract["planned_time_base_s"] = contract_v1["timeline_duration_s"]
            contract["planning_delta_s"] = contract_v1["delta_s"]
            contract["audio_time_base_s"] = base
            contract["audio_padded_to_timeline"] = False      # v2：不靠 apad 掩盖短缺
            contract["padding_budget_s"] = (plan.get("padding_policy") or {}).get("apad_allowed_s")
        complete = bool(not bad_records and wrote and narration_dur is not None and narration_dur > 0)
        # v2 fail-closed：实际时长不可测 / 拼接不一致 ⇒ 不得声称完整
        v2_blockers = []
        if complete and base is None:
            v2_blockers.append({"code": "NARRATION_DURATION_UNMEASURABLE",
                                "detail": "逐段实际 TTS 时长缺失 ⇒ 无法建立 audio_time_base"})
        if complete and plan.get("concat_consistent") is False:
            v2_blockers.append({"code": "NARRATION_CONCAT_MISMATCH",
                                "detail": "拼接音轨实测 {:.3f}s 与 Σ 段实际 {:.3f}s 不一致".format(
                                    float(narration_dur or 0),
                                    float(plan.get("actual_total_narration_s") or 0))})
        if v2_blockers:
            complete = False
        errors = [{"segment": r["index"], **e} for r in records for e in (r.get("errors") or [])]
        errors.extend({"segment": None, **b} for b in v2_blockers)
        if concat_error:
            errors.append({"segment": None, **concat_error})
        data = {
            "voice": str(voice),
            "provider": provider,
            "audio": NARRATION_REL if complete else None,
            "narration_path": NARRATION_REL,
            "narration_written": wrote,
            "narration_reused_previous": bool((not wrote) and (project_dir / NARRATION_REL).is_file()),
            # 兼容既有字段名（下游按 segments/audio 读取）
            "segments": [{k: r[k] for k in ("index", "audio", "status", "reused", "attempts",
                                            "bytes", "duration_s", "text_sha256")}
                         for r in records],
            "segment_details": records,
            "errors": errors,
            "expected_segments": len(expected),
            "successful_segments": len(ok_records),
            "failed_segments": [r["index"] for r in bad_records],
            "concat_error": concat_error,
            "reused_segments": [r["index"] for r in records if r["reused"]],
            "status": "COMPLETE" if complete else "INCOMPLETE",
            "complete": complete,
            "narration_duration_s": contract["narration_duration_s"] or None,
            "script_time_base_s": contract.get("planned_time_base_s",
                                               contract["timeline_duration_s"]),
            "duration_contract": contract,
            "duration_ok": contract["within_tolerance"],
            # ---- Duration Contract v2 字段（生产权威链）----
            "audio_time_base_s": base,
            "contract_policy": contract.get("policy"),
            "narration_plan": plan,
            "segment_actual_durations_s": [w["actual_s"] for w in (plan.get("segments") or [])],
            "audio_segment_windows": plan.get("segments") or [],
            "planning_drift": plan.get("planning_drift"),
            "padding_budget_s": (plan.get("padding_policy") or {}).get("apad_allowed_s"),
            "padding_applied_s": 0.0,
            "duration_authority_note": "actual TTS duration = narration 事实；declared 仅为规划估计（PLANNING_DRIFT；不阻断）",
            "summary": self._summary(len(expected), len(ok_records), complete, contract, wrote),
            "confidence": 1.0 if complete else 0.0,
            "note": ("由 Voice Agent 经 TTS 工具合成（逐段状态 + 复用 + 重试；"
                     "失败段不阻塞已成功段，但不完整即判失败）"),
        }
        aid = engine.write_artifact(task["project_id"], task["task_id"], "voice_output",
                                   data, summary=data["summary"])
        engine.attach_artifact(task["task_id"], aid)
        engine.db.update_task(task["task_id"], confidence=data["confidence"])

        if not complete:
            detail = {"expected_segments": len(expected),
                      "successful_segments": len(ok_records),
                      "failed_segments": data["failed_segments"],
                      "error_codes": sorted({e.get("code") for e in errors}),
                      "narration_duration_s": contract["narration_duration_s"],
                      "script_time_base_s": contract["timeline_duration_s"]}
            # 失败即失败：交给引擎统一重试/阻塞策略（下游 render 因依赖未成功不会派发）
            raise NarrationIncompleteError(incomplete_message("voice 分段未全部成功", detail))

    # ---------------- 逐段处理 ----------------

    def _reuse_or_synthesize(self, ctx, tts, ffmpeg, manifest: dict, i: int, text: str, rel: str,
                             voice: str, provider: str, max_attempts: int,
                             backoff: float) -> dict:
        """单段：合法且文本/音色未变 → 复用；否则合成（可重试）。"""
        want = _text_sha(text, voice, provider)
        entry = (manifest.get("segments") or {}).get(str(i)) or {}
        rec = {"index": i, "audio": rel, "text_sha256": want, "status": "PENDING",
               "reused": False, "attempts": 0, "bytes": None, "duration_s": None, "errors": []}
        if entry.get("text_sha256") == want and entry.get("voice") == str(voice) \
                and entry.get("provider") == provider:
            ok, dur = segment_file_ok(ctx, ctx.project_dir, rel)
            if ok:
                rec.update(status="REUSED", reused=True, bytes=self._size(ctx, rel),
                           duration_s=round(dur, 3), generated_at=entry.get("generated_at"))
                return rec

        for attempt in range(1, max_attempts + 1):
            rec["attempts"] = attempt
            try:
                tts.execute({"text": text, "voice": voice, "output": rel}, ctx)
            except ToolError as exc:
                code, retryable = classify_tts_error(exc)
                rec["errors"].append({"code": code, "retryable": retryable, "attempt": attempt,
                                      "error": str(exc)[:200]})
                if retryable and attempt < max_attempts:
                    time.sleep(min(backoff * attempt, 30))
                    continue
                rec["status"] = "FAILED"
                return rec
            ok, dur = segment_file_ok(ctx, ctx.project_dir, rel)
            if ok:
                rec.update(status="SUCCESS", bytes=self._size(ctx, rel),
                           duration_s=round(dur, 3))
                manifest.setdefault("segments", {})[str(i)] = {
                    "text_sha256": want, "voice": str(voice), "provider": provider,
                    "audio": rel, "bytes": rec["bytes"], "duration_s": rec["duration_s"],
                    "generated_at": time.time(), "attempt": attempt}
                return rec
            rec["errors"].append({"code": "TTS_INVALID_AUDIO", "retryable": True, "attempt": attempt,
                                 "error": "合成文件为空或无法探测时长"})
            if attempt < max_attempts:
                time.sleep(min(backoff * attempt, 30))
                continue
            rec["status"] = "FAILED"
        return rec

    # ---------------- 辅助 ----------------

    @staticmethod
    def _max_attempts(engine) -> int:
        raw = (engine.config.get("tools", {}).get("tts") or {}).get("max_attempts")
        try:
            n = int(raw)
        except (TypeError, ValueError):
            return DEFAULT_MAX_ATTEMPTS
        return n if 1 <= n <= 10 else DEFAULT_MAX_ATTEMPTS

    @staticmethod
    def _size(ctx, rel: str):
        p = Path(ctx.project_dir) / rel
        try:
            return p.stat().st_size
        except OSError:
            return None

    @staticmethod
    def _load_manifest(project_dir: Path) -> dict:
        p = Path(project_dir) / MANIFEST_REL
        if p.is_file():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    data.setdefault("segments", {})
                    return data
            except (json.JSONDecodeError, OSError):
                pass
        return {"version": 1, "segments": {}}

    @staticmethod
    def _save_manifest(project_dir: Path, manifest: dict) -> None:
        p = Path(project_dir) / MANIFEST_REL
        p.parent.mkdir(parents=True, exist_ok=True)
        manifest["version"] = 1
        p.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")

    @staticmethod
    def _summary(expected: int, ok: int, complete: bool, contract: dict, wrote: bool) -> str:
        if contract.get("measured"):
            dur = "旁白 {:.1f}s / 时间轴 {:.1f}s（差 {:+.1f}s，容差 {:.0%}）".format(
                contract["narration_duration_s"], contract["timeline_duration_s"],
                contract["delta_s"], contract["tolerance_ratio"])
        else:
            dur = "旁白未测得（本轮未生成/未重建）/ 时间轴 {:.1f}s".format(
                contract["timeline_duration_s"])
        base = "配音{}：{}/{} 段成功，{}{}".format(
            "完成" if complete else "未完成", ok, expected, dur,
            "，narration.mp3 已重建" if wrote else "，narration.mp3 保持原文件")
        if not complete:
            base += "；不完整 → 判失败（不生成被截短的成片）"
        return base

    def _load_script(self, engine, task: dict) -> dict | None:
        for dep in task.get("dependencies", []):
            dep_task = engine.db.get_task(dep)
            for art_id in (dep_task or {}).get("artifacts", [])[::-1]:
                art = engine.db.get_artifact(art_id)
                if art["type"] == "script_output":
                    with open(art["path"], encoding="utf-8") as fh:
                        return json.load(fh)
        return None

    def _plan_only(self, engine, task, segments, provider, note=""):
        plan = {
            "voice": task["inputs"].get("voice") or "",
            "provider": provider,
            "segments": [
                {"index": i, "text": narration_text(s)[:120],
                 "duration_s": s.get("duration_s", 0), "status": "planned"}
                for i, s in enumerate(segments)
            ],
            "summary": f"配音方案：{len(segments)} 段，provider={provider}{note}",
            "confidence": 1.0,
            "note": "provider=none 或脚本无可配音段落时仅产出方案",
        }
        aid = engine.write_artifact(task["project_id"], task["task_id"], "voice_plan",
                                    plan, summary=plan["summary"])
        engine.attach_artifact(task["task_id"], aid)
        engine.db.update_task(task["task_id"], confidence=1.0)
