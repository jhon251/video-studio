# -*- coding: utf-8 -*-
"""Phase 8 交叉核验：把 A/B 真实产物送入 v3 校验器与下游隔离口径，出一份机器可读核验记录。"""
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.path.insert(0, str(R / "tests"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core.narration import narration_text                           # noqa: E402

# 与 tests/creator_style_v3_test.py **逐字同源**的校验规则（此处复制以避免执行整个测试模块；
# 若测试内规则变更，本脚本需同步——已在 PHASE8_REPORT.md 声明该维护点）。
EMOTION_BEATS = ("curiosity", "tension", "payoff", "calm", "surprise")
V3_FIELD_NAMES = ("emotion_beat", "retention_device", "cta_plan", "hook_map", "hook_type",
                  "at_segment", "hook_interval_ok")
BARE_CTA = ("感谢观看", "一键三连", "记得点赞", "点赞关注", "关注我", "我们下期再见", "评论区告诉我",
            "别忘了三连", "求个三连")


def validate_script_v3(script: dict) -> list[dict]:
    out = []
    segs = script.get("segments") or []
    beats = [s.get("emotion_beat") for s in segs]
    for i, b in enumerate(beats):
        if b is not None and b not in EMOTION_BEATS:
            out.append({"code": "V3_BEAT_ENUM", "at": i, "value": b})
    run = 1
    for i in range(1, len(beats)):
        if beats[i] is not None and beats[i] == beats[i - 1]:
            run += 1
            if run >= 3:
                out.append({"code": "V3_BEAT_RUN3", "at": i, "value": beats[i]})
        else:
            run = 1
    cta = script.get("cta_plan") or []
    if len(cta) > 2:
        out.append({"code": "V3_CTA_TOO_MANY", "count": len(cta)})
    for c in cta:
        line = str((c or {}).get("line") or "")
        hit = [p for p in BARE_CTA if p in line]
        if hit:
            out.append({"code": "V3_CTA_BARE", "line": line[:40], "hit": hit})
        if not str((c or {}).get("type") or "").strip():
            out.append({"code": "V3_CTA_NO_TYPE", "line": line[:40]})
    hm = script.get("hook_map") or []
    if len(hm) != 3:
        out.append({"code": "V3_HOOK_MAP_SIZE", "count": len(hm)})
    for i, s in enumerate(segs):
        text = str(s.get("narration") or "")
        for name in V3_FIELD_NAMES:
            if name in text:
                out.append({"code": "V3_META_IN_NARRATION", "at": i, "field": name})
        for beat in EMOTION_BEATS:
            if beat in text:
                out.append({"code": "V3_BEAT_NAME_IN_NARRATION", "at": i, "beat": beat})
    return out

out = {"schema": "phase8-ab-crosscheck-v1", "arms": {}}
for arm in ("v2", "v3"):
    log = json.loads((R / "docs" / "regression_2x" / "logs" /
                      "phase8_ab_{}.json".format(arm)).read_text(encoding="utf-8"))
    script = log.get("script") or {}
    segs = script.get("segments") or []
    beats = [s.get("emotion_beat") for s in segs]
    cta = script.get("cta_plan") or []
    narr = [str(s.get("narration") or "") for s in segs]
    tts = [narration_text(s) for s in segs]
    out["arms"][arm] = {
        "json_valid": log.get("json_valid"), "segments": len(segs),
        "beats": beats,
        "beat_enum_ok": all((b in ("curiosity", "tension", "payoff", "calm", "surprise"))
                            for b in beats if b is not None),
        "beat_run3": any(beats[i] == beats[i - 1] == beats[i - 2] is not None
                         for i in range(2, len(beats))),
        "v3_validator_violations": validate_script_v3(script),
        "cta_plan": cta, "cta_bare_hits": [t for t in (c.get("line") or "" for c in cta)
                                           if any(m in t for m in BARE_CTA)],
        "metadata_in_narration": [n for n in V3_FIELD_NAMES if any(n in x for x in narr)],
        "tts_text_equals_narration_only": all(
            t == (s.get("narration") or "").strip() for t, s in zip(tts, segs)),
        "cost_usd": log.get("cost_usd"), "reasoning_tokens": log.get("reasoning_tokens"),
        "output_truncated": log.get("output_truncated"),
        "first_segment_narration": (narr[0][:180] if narr else ""),
        "hook_map": script.get("hook_map") or [],
    }
p = R / "docs" / "regression_2x" / "logs" / "phase8_ab_crosscheck.json"
p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
for arm, d in out["arms"].items():
    print("[{}] json_valid={} segs={} beats_enum_ok={} run3={} violations={} cta={} "
          "metadata_in_narration={} tts_only_narration={}".format(
              arm, d["json_valid"], d["segments"], d["beat_enum_ok"], d["beat_run3"],
              d["v3_validator_violations"], len(d["cta_plan"]), d["metadata_in_narration"],
              d["tts_text_equals_narration_only"]))
print("crosscheck ->", p.relative_to(R))
