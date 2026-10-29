# -*- coding: utf-8 -*-
"""检验：retrieval artifact 的 _p30_binding 是否只是**用合成 id 键**写的同一条绑定。

若把 `_p30_binding["S{i+1}"]` 对齐到第 i 段的真实 scene_id 后与 DB 决策一致，
则该 artifact 与生产同构（只是键名不同）；否则存在**绑定不一致**。只读。
"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
SCRIPT = R / "output" / "phase27_script_sandbox" / "script_p27_v41_40seg.json"


def main() -> int:
    segs = json.loads(SCRIPT.read_text(encoding="utf-8"))["segments"]
    retr = json.loads((R / "projects/p_8b48148d4bf3/artifacts/a_331e853a4bb9.json")
                      .read_text(encoding="utf-8"))
    b = retr.get("_p30_binding") or {}
    con = sqlite3.connect("file:" + (R / "projects" / "video_studio.db").as_posix()
                          + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    r = con.execute("select payload from events where project_id='p_8b48148d4bf3' and "
                    "type='MATERIAL_TIMELINE' order by ts desc limit 1").fetchone()
    ds = {d["scene_id"]: (d.get("selected_asset") or {}).get("sha256")
          for d in json.loads(r["payload"])["decisions"]}
    print("{:<8} {:<8} {:<14} {:<14} {}".format("idx", "real_id", "binding(合成键)", "DB决策", "一致"))
    same = diff = 0
    for i, s in enumerate(segs):
        real = str(s.get("scene_id") or "S%02d" % (i + 1))
        synth = "S%02d" % (i + 1)
        bv = b.get(synth)
        dv = ds.get(real)
        ok = (bv == dv)
        same += ok
        diff += (not ok)
        if not ok:
            print("{:<8} {:<8} {:<14} {:<14} {}".format(
                i + 1, real, str(bv)[:12] if bv else "-", str(dv)[:12] if dv else "-", "DIFF"))
    print()
    print("对齐后：一致 {} / 不一致 {}（共 {}）".format(same, diff, len(segs)))
    print("binding 键集合 = 合成键? {}".format(
        all(("S%02d" % (i + 1)) in b for i in range(len(segs)))))
    print("binding 键样例: {}".format(sorted(b.keys())[:6]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
