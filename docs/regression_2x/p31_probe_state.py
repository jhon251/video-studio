# -*- coding: utf-8 -*-
"""P31 侦查：列出交付候选的 artifacts，并从 render_output 复算 DQ-2 与复用分布。

只读：不写 DB、不改任何既有产物。
"""
from __future__ import annotations

import collections
import json
import pathlib
import sqlite3
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
OUT = R / "output" / "p31_probe"
OUT.mkdir(parents=True, exist_ok=True)
PIDS = ["p_8b48148d4bf3", "p_ddb17cfbacf8"]


def load_artifact(path: str):
    p = pathlib.Path(path)
    if not p.is_absolute():
        p = R / p
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:                                            # noqa: BLE001
        return {"_error": "{}: {}".format(type(exc).__name__, exc)}


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    con = sqlite3.connect("file:" + (R / "projects" / "video_studio.db").as_posix()
                          + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    result = {}
    for pid in PIDS:
        rows = con.execute(
            "select artifact_id, task_id, type, path, sha256, size, summary, created_at "
            "from artifacts where project_id=? order by created_at", (pid,)).fetchall()
        print("=== {} : {} artifacts ===".format(pid, len(rows)))
        for r in rows:
            print("   {:<22} {:<26} {}  {}B".format(
                r["artifact_id"], r["type"], str(r["path"])[:72], r["size"]))
        result[pid] = {"artifacts": [{"artifact_id": r["artifact_id"], "type": r["type"],
                                      "path": r["path"], "sha256": r["sha256"],
                                      "size": r["size"]} for r in rows]}
        # 取 render_output
        ro = [r for r in rows if r["type"] == "render_output"]
        if not ro:
            print("   (无 render_output)")
            continue
        r = ro[-1]
        payload = load_artifact(r["path"]) or {}
        tl = payload.get("material_timeline")
        if not tl:
            print("   render_output keys: {}".format(sorted(payload.keys())[:24]))
            continue
        total = 0.0
        secs, scenes, wins = collections.Counter(), collections.Counter(), {}
        for s in tl:
            d = max(float(s.get("end_s", 0)) - float(s.get("start_s", 0)), 0.0)
            a = (s.get("selected_asset") or {}).get("sha256") or "SOLID_COLOR"
            nm = (s.get("selected_asset") or {}).get("name") or "-"
            secs[a] += d
            scenes[a] += 1
            wins.setdefault(a, {"name": nm, "scenes": []})["scenes"].append(
                {"scene_id": s.get("scene_id"), "start_s": s.get("start_s"),
                 "end_s": s.get("end_s"), "binding_source": s.get("binding_source")})
            total += d
        shares = {k: v / total for k, v in secs.items()} if total else {}
        uniq = len([k for k in secs if k != "SOLID_COLOR"])
        mx = max(shares.values()) if shares else 0.0
        print()
        print("### {} total_s={:.3f} distinct={} uniq_assets={} max_share={:.4f} max_reuse={}".format(
            pid, total, len(secs), uniq, mx, max(scenes.values()) if scenes else 0))
        print("{:<14} {:<5} {:<9} {:<9} {}".format("sha12", "scn", "secs", "share", "name"))
        for k in sorted(secs, key=lambda z: -secs[z]):
            print("{:<14} {:<5} {:<9.2f} {:<9.4f} {}".format(
                str(k)[:12], scenes[k], secs[k], shares[k], wins[k]["name"][:42]))
        result[pid]["dq2"] = {
            "total_s": round(total, 3), "unique_assets": uniq,
            "max_asset_share": round(mx, 4), "max_reuse_scenes": max(scenes.values()),
            "per_asset": {str(k)[:12]: {"scenes": scenes[k], "seconds": round(secs[k], 3),
                                        "share": round(shares[k], 4), "name": wins[k]["name"],
                                        "scene_ids": [w["scene_id"] for w in wins[k]["scenes"]]}
                          for k in secs}}
        print()
    (OUT / "state.json").write_text(json.dumps(result, ensure_ascii=False, indent=1),
                                    encoding="utf-8")
    print("-> " + str(OUT / "state.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
