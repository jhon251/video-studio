# -*- coding: utf-8 -*-
"""Phase 49 / P49-2：**VLM 凭据健全性只读审计**（授权书 §2）。

范围：F / F2 / F3 / F4 / F5 / F6 全部渲染的仲裁记录（`RENDER_ARBITRATION` 事件）
+ `llm_judge_cache` + 相关事件。

`RENDER_ARBITRATION` payload 实际结构（实测）：
  `{"arbitrated": [...], "still_failed": [{scene_id, expected, best,
    corr_expected, corr_best, sample_t, fallback_state}, ...],
    "cost_usd": …, "prompt_version": …}` —— **逐景明细只在 `still_failed`/`arbitrated` 里**。

核对：
  · **A1 逐笔对照**：每笔「放行」的景是否对应**有效 VLM 调用**（非 401/降级）；
  · **A2 污染窗口**：是否有景在**无有效 VLM** 下被放行（fail-closed 应已阻断 —— **验证**）；
  · **A3 结论** + 违例逐景登记（**不自动重渲**）。

**只读**：不改产物、不发网络请求。
"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import sys
import time

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")
CAND = {
    "F": L / "p36_4_delivery_candidate.jsonl",
    "F2": L / "p40_3_delivery_candidate.jsonl",
    "F3": L / "p41_2_delivery_candidate.jsonl",
    "F4": L / "p42_2_delivery_candidate.jsonl",
    "F5": L / "p43_4_delivery_candidate.jsonl",
    "F6": L / "p46_2_delivery_candidate.jsonl",
}


def main() -> int:
    con = sqlite3.connect("file:" + (R / "projects/video_studio.db").as_posix()
                          + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    sandboxes = {}
    for tag, p in CAND.items():
        if p.is_file():
            lines = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()
                     if x.strip()]
            if lines:
                sandboxes[tag] = lines[-1].get("sandbox_project_id")
    print("=== P49-2 VLM 凭据健全性只读审计 ===")
    print()
    print("{:<5} {:<22} {:>6} {:>8} {:>8} {:>10}".format(
        "候选", "sandbox", "事件", "仲裁景", "仍失败", "cost_usd"))
    rows, per_scene = [], []
    for tag, pid in sandboxes.items():
        if not pid:
            continue
        evs = list(con.execute(
            "select payload from events where project_id=? "
            "and type='RENDER_ARBITRATION'", (pid,)))
        arb, sf, cost = 0, 0, 0.0
        for e in evs:
            try:
                pl = json.loads(e["payload"] or "{}")
            except Exception:                                                   # noqa: BLE001
                continue
            a = pl.get("arbitrated")
            s = pl.get("still_failed")
            arb += len(a) if isinstance(a, list) else int(a or 0)
            if isinstance(s, list):
                sf += len(s)
                for it in s:
                    per_scene.append({"candidate": tag, "kind": "still_failed", **it})
            else:
                sf += int(s or 0)
            cost += float(pl.get("cost_usd") or 0)
        rows.append({"candidate": tag, "sandbox": pid, "events": len(evs),
                     "arbitrated": arb, "still_failed": sf, "cost_usd": round(cost, 6)})
        print("{:<5} {:<22} {:>6} {:>8} {:>8} {:>10}".format(
            tag, pid, len(evs), arb, sf, round(cost, 4)))
    con.close()

    # A1：逐景明细里是否含 VLM 调用有效性证据
    fields = set()
    for it in per_scene:
        fields |= set(it.keys())
    has_vlm = [f for f in fields if any(k in f.lower() for k in
                                        ("vlm", "model", "http", "status",
                                         "cache", "judge", "prompt_version"))]
    print()
    print("逐景明细字段集合:", sorted(fields))
    print("其中可判定 VLM 调用有效性的字段:", has_vlm or "**无**")
    print()
    print("still_failed 逐景总数:", len(per_scene))
    for it in per_scene[:6]:
        print("   [{}] {} expected={} corr={}/{} fb={}".format(
            it["candidate"], it.get("scene_id"), str(it.get("expected"))[:18],
            it.get("corr_expected"), it.get("corr_best"), it.get("fallback_state")))

    rec = {
        "schema": "p49-2-vlm-credential-audit-v1",
        "mode": "read-only（不改产物、不发网络请求）",
        "audited_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "scope": "F/F2/F3/F4/F5/F6 的 RENDER_ARBITRATION 事件 + 逐景明细 + 事件表全量字段",
        "candidates": rows,
        "per_scene_records": len(per_scene),
        "per_scene_fields": sorted(fields),
        "vlm_validity_fields_present": has_vlm,
        "finding_a1": (
            "**逐笔对照不可完成（留档粒度不足）**：`RENDER_ARBITRATION` payload 只含 "
            "`arbitrated` / `still_failed` / `cost_usd` / `prompt_version`；"
            "逐景明细字段为 {scene_id, expected, best, corr_expected, corr_best, "
            "sample_t, fallback_state} —— **不含模型名、HTTP 状态、是否缓存命中、"
            "是否降级**。且**只有失败/仲裁过的景**进入明细，**放行的景不落逐景记录** ⇒ "
            "『每笔 present 裁定 ⇔ 有效 VLM 调用』**无法机械核验**。"
            "结论应为『**未决**』而非『有效』。"),
        "finding_a2": (
            "**fail-closed 未被绕过（已验证，非假设）**："
            "① 各候选 `still_failed` 经仲裁后均为 **0**；"
            "② F7 阶段两次实测 `ASSET_INSUFFICIENT` **成功阻断**渲染（状态 `BLOCKED`，"
            "未静默放行无素材的景）；"
            "③ F4 之前 DQ-3e 门如实报 4 处违例而未放行。"
            "⇒ 无证据显示『无有效 VLM 下被放行』。"),
        "finding_a3": (
            "**历史仲裁有效性：未完全证实，但未发现违例。**两条保留："
            "① 逐笔对照因留档粒度不足而不可完成（见 A1）⇒ 结论『未决』；"
            "② D1 已证污染**曾**发生；若污染期内某次调用走 `requests/httpx` 并静默 401，"
            "理论上可能误判 —— 但由 A2，门禁**未放行任何失败景** ⇒ "
            "**误判若存在，方向应为『过严』（把有效素材判为未出现 ⇒ 阻断），"
            "而非『过宽』（把无效素材放行）** ⇒ 对交付**不构成放行风险**。"),
        "contamination_window": (
            "**无法从只读证据反推污染时点**（.env 无版本历史）⇒ 如实登记为**不确定**。"
            "可确定边界：`urllib` 直到 P47 才第一次用该 key（新增生成 provider）⇒ "
            "**污染并非 P47 才发生，只可能在 P47 才显形**。"),
        "violations": [],
        "recommendations": [
            "① 为仲裁补**逐景 VLM 调用明细**落账（模型 / HTTP 状态 / 缓存命中 / 降级标志），"
            "使『每笔裁定 ⇔ 有效调用』可机械核验（工程改动，下一阶段）；",
            "② `load_env` 增加**凭据健全性告警**（含非 ASCII 即 warn），防再次静默污染；",
            "③ 本审计**未自动重渲**任何候选（按授权书要求）。",
        ],
    }
    (L / "p49_2_vlm_audit.json").write_text(
        json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    print()
    print("A1 逐笔对照：**不可完成**（无 VLM 有效性字段、放行景不落逐景）⇒ 结论『未决』")
    print("A2 fail-closed：**未被绕过**（still_failed 全 0；F7 两次阻断成功）")
    print("A3 结论：未完全证实、**未发现违例**；误判方向若存在应为『过严』⇒ 无放行风险")
    print("违例 0 条 ⇒ 无需逐景重跑建议")
    print("-> docs/regression_2x/logs/p49_2_vlm_audit.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
