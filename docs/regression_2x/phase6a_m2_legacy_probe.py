# -*- coding: utf-8 -*-
"""6-A/M2 取证（只读）：真实 `voice_output` 产物的"逐段时长"可得性统计。

用途：说明 PI-6（段落边界漂移）为什么按"正式完整性检查"接线——
明确违约（漂移超阈值）阻断；仅"逐段真实 TTS 时长缺失"导致不可评估时只记 UNKNOWN 不阻断。
依据：若对"缺逐段时长"的既有产物 fail-closed 阻断，会让**旁白完整、时长达标**的成片无法重渲染。

只读：DB 以 `mode=ro` 打开，只读产物 JSON，不写任何项目文件。
用法: python docs/regression_2x/phase6a_m2_legacy_probe.py
产出: logs/phase6a_m2_legacy_probe.json
"""
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
LOGS = ROOT / "docs" / "regression_2x" / "logs"
DB = ROOT / "projects" / "video_studio.db"

con = sqlite3.connect("file:{}?mode=ro".format(DB.as_posix()), uri=True)
con.execute("PRAGMA query_only=ON")
rows = con.execute("select artifact_id, project_id, path from artifacts "
                   "where type='voice_output' order by created_at").fetchall()
con.close()

shapes, with_segd, without_segd, unreadable = Counter(), 0, 0, 0
samples_missing = []
for aid, pid, path in rows:
    p = Path(path)
    if not p.is_absolute():
        p = ROOT / path
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:                                            # noqa: BLE001
        unreadable += 1
        continue
    segd = d.get("segment_details") or []
    if segd:
        with_segd += 1
    else:
        without_segd += 1
        if len(samples_missing) < 8:
            samples_missing.append({"artifact_id": aid, "project_id": pid,
                                    "complete": d.get("complete"),
                                    "narration_duration_s": d.get("narration_duration_s"),
                                    "has_segments_field": bool(d.get("segments"))})
    shapes[(bool(segd), bool(d.get("narration_duration_s")), d.get("complete"))] += 1

out = {
    "schema": "m2-legacy-voice-probe-v1", "read_only": True,
    "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "db": str(DB.relative_to(ROOT)), "voice_output_total": len(rows),
    "with_segment_details": with_segd, "without_segment_details": without_segd,
    "unreadable": unreadable,
    "ratio_without": round(without_segd / len(rows), 4) if rows else None,
    "shapes_(has_segd,has_narration_duration,complete)": {
        "{}/{}/{}".format(*k): v for k, v in shapes.items()},
    "samples_without_segment_details": samples_missing,
    "note": "PI-6 的输入是『逐段真实 TTS 时长』；历史产物大量缺失该字段（见上计数），"
            "但 PI-6 不可评估并不代表成品违约（旁白覆盖/时长由 PI-1/PI-2 独立 fail-closed 把关），"
            "故 M2 把 PI-6 定为：FAIL 阻断、UNKNOWN 只记录（仍绝不记 PASS）。",
}
(LOGS / "phase6a_m2_legacy_probe.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                                   encoding="utf-8")
print("voice_output 总数:", len(rows), "| 带逐段时长:", with_segd,
      "| 缺:", without_segd, "| 不可读:", unreadable)
print("json ->", LOGS / "phase6a_m2_legacy_probe.json")
