"""P0-2 VO 对齐（timeline/alignment manifest 生成）。

设计契约（docs/STAGE32B_DESIGN.md §5/§7）：
- 实测 VO duration 为主要依据；shotlist 名义时长仅 fallback；
- 冻结稿顺序不变；segment↔shot 映射可追踪；不出现负时长/意外重叠；
- 不修改 narration / Material Package / 上游任何产物。
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

SHOT_GAP = 0.0   # 暂不强制镜间缝（Remediation 裁决）；gap 仅物化时计入


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def parse_shotlist(shotlist_path: Path) -> list[dict]:
    data = json.loads(shotlist_path.read_text(encoding="utf-8"))
    out = []
    for s in data.get("scenes", []):
        m = re.search(r"(\d+)", str(s.get("duration_hint", "")))
        out.append({"shot_id": s["scene_id"], "nominal": float(m.group(1)) if m else 0.0})
    return out


def build_alignment(vo_manifest_path: Path, shotlist_path: Path,
                    out_dir: Path, force: bool = False) -> dict:
    vo = json.loads(vo_manifest_path.read_text(encoding="utf-8"))
    shots = parse_shotlist(shotlist_path)
    seg_by_shot: dict[str, list[dict]] = {}
    for s in vo["segments"]:
        seg_by_shot.setdefault(s["shot_id"], []).append(s)

    in_fp = _sha256(vo_manifest_path.read_text(encoding="utf-8")
                    + shotlist_path.read_text(encoding="utf-8"))
    out_path = out_dir / "manifests" / "alignment_manifest.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists() and not force:
        m = json.loads(out_path.read_text(encoding="utf-8"))
        if m.get("input_fingerprint") == in_fp:
            print(f"alignment 已存在（指纹一致），跳过：{out_path}")
            return m

    warnings, shots_out, t = [], [], 0.0
    for sh in shots:
        sid = sh["shot_id"]
        segs = seg_by_shot.get(sid, [])
        shot_start = t
        seg_out = []
        for s in segs:
            d = float(s.get("duration", 0.0))
            if s.get("status") != "OK":
                warnings.append(f"{sid}: segment {s['id']} 非 OK（{s.get('error','')}）")
                continue
            seg_out.append({"segment_id": s["id"], "text": s["text"],
                            "start": round(t, 3), "end": round(t + d, 3),
                            "duration": round(d, 3)})
            t += d
        measured = round(sum(x["duration"] for x in seg_out), 3)
        nominal = sh["nominal"]
        if measured > 0:
            adopted, reason = measured, "vo_measured"
            if nominal > 0 and abs(measured - nominal) / nominal > 0.3:
                warnings.append(f"{sid}: 实测 {measured}s 与名义 {nominal}s 偏差>30%")
        else:
            adopted = max(nominal, 4.0)
            reason = "nominal_fallback"
            warnings.append(f"{sid}: 无有效 VO 段，采用名义时长 {adopted}s（fallback）")
        shots_out.append({"shot_id": sid, "segments": seg_out,
                          "measured_vo_duration": measured,
                          "nominal_duration": nominal,
                          "adopted_duration": adopted,
                          "adopted_reason": reason,
                          "start": round(shot_start, 3),
                          "end": round(shot_start + adopted, 3)})
        t = shot_start + adopted + SHOT_GAP
    manifest = {
        "input_fingerprint": in_fp,
        "vo_manifest_sha": _sha256(vo_manifest_path.read_text(encoding="utf-8")),
        "shotlist_sha": _sha256(shotlist_path.read_text(encoding="utf-8")),
        "narration_sha": vo.get("narration_sha", ""),
        "shot_gap": SHOT_GAP,
        "timeline_contract": "production_duration = SUM(adopted) + SUM(actual_gap)；gap 当前=0",
        "total_duration": round(sum(sh["adopted_duration"] for sh in shots_out), 3),
        "shots": shots_out,
        "warnings": warnings,
        "vo_speed_review": "RESOLVED: 4.33字/s ≈ 260字/分（人工裁决目标带 240-300）",
    }
    out_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(f"alignment 完成：{len(shots_out)} 镜，总时长 {manifest['total_duration']}s，"
          f"警告 {len(warnings)}")
    for w in warnings:
        print("  [WARN]", w)
    return manifest


def gate_alignment(manifest: dict) -> dict:
    """P0-2 Gate 检查。"""
    checks = []
    segs = [s for sh in manifest["shots"] for s in sh["segments"]]

    def check(name, cond, detail=""):
        checks.append((name, cond))
        print(f"{'PASS' if cond else 'FAIL'}  {name} {detail}")

    check("segment↔shot 映射完整（20 段全覆盖）", len(segs) == 20, f"({len(segs)})")
    check("无负时长", all(s["duration"] >= 0 for s in segs))
    check("无镜内重叠", all(
        sh["segments"][i]["start"] == sh["segments"][i - 1]["end"]
        for sh in manifest["shots"] for i in range(1, len(sh["segments"]))))
    check("镜序与 shotlist 一致（S01..S20）",
          [sh["shot_id"] for sh in manifest["shots"]]
          == [f"S{i:02d}" for i in range(1, 21)])
    check("每镜 adopted 时长可追溯（reason 合法）", all(
        sh["adopted_reason"] in ("vo_measured", "nominal_fallback")
        for sh in manifest["shots"]))
    check("输入指纹存在", bool(manifest.get("input_fingerprint")))
    ok = all(c[1] for c in checks)
    print(f"\nP0-2 Gate: {'PASS' if ok else 'FAIL'}")
    return {"gate": "PASS" if ok else "FAIL",
            "checks": [c[0] for c in checks], "fails": [c[0] for c in checks if not c[1]]}
