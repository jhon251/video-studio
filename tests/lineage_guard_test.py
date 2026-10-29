# -*- coding: utf-8 -*-
"""Phase 13-E 守卫套件：底片谱系选择（防止未来再次把修订候选绑到 v9 1532s 旧底片）。

覆盖：
 · 权威谱系常量 = DCv2/H5 978.7s（sha256 + 时长实测一致）；
 · **v9 1532s 底片必须被拒**（LINEAGE_MISMATCH + is_legacy_lineage）；
 · 底片缺失 ⇒ FILM_MISSING（不猜测）；
 · 权威时间轴（`new_production_timeline`）可加载且 S05 窗口 = 常量登记值；
 · 谱系常量与 Phase 13-E 结论 JSON 一致（防漂移）；
 · PI/DQ 阈值未被本模块触碰（源码级检查）。

运行: python tests/lineage_guard_test.py
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core import lineage_guard as LG                                     # noqa: E402

PASS, FAIL = [], []


def check(name, ok, detail=None):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name,
                             "" if ok else json.dumps(detail, ensure_ascii=False,
                                                      default=str)[:240]))
    return bool(ok)


AUTH = LG.authoritative_film(ROOT)
rec_auth = LG.check_lineage(AUTH, root=ROOT)
leg = ROOT / LG.LEGACY_LINEAGE["film"]
rec_leg = LG.check_lineage(leg, root=ROOT)

check("1 权威底片 = DCv2/H5 978.7s：sha256 与时长双匹配（LINEAGE_OK）",
      rec_auth["verdict"] == "LINEAGE_OK" and rec_auth["sha_match"]
      and rec_auth["duration_match"], rec_auth)
check("1b 权威谱系常量登记完整（id/film/sha256/duration/timeline_source/scenes/s05_window）",
      all(k in LG.AUTHORITATIVE_LINEAGE for k in ("id", "film", "sha256", "duration_s",
                                                  "timeline_source", "scenes", "s05_window"))
      and LG.AUTHORITATIVE_LINEAGE["scenes"] == 21
      and LG.AUTHORITATIVE_LINEAGE["s05_window"] == [181.776, 221.862])
check("2 v9 1532s 旧底片**必须被拒**（否则修订候选会重现 #65/#67 度量伪影）",
      rec_leg["verdict"] == "LINEAGE_MISMATCH" and rec_leg["is_legacy_lineage"]
      and not rec_leg["sha_match"], rec_leg)
raised = False
try:
    LG.assert_lineage(leg, root=ROOT)
except ValueError:
    raised = True
check("2b assert_lineage(v9) 抛错（守卫硬门生效）", raised)
ok_assert = True
try:
    LG.assert_lineage(AUTH, root=ROOT)
except ValueError:
    ok_assert = False
check("2c assert_lineage(权威底片) 不抛错（不误伤正确底片）", ok_assert)
check("3 底片缺失 ⇒ FILM_MISSING（不猜测、不推断）",
      LG.check_lineage(ROOT / "no_such_film.mp4", root=ROOT)["verdict"] == "FILM_MISSING")

tl = LG.load_authoritative_timeline(ROOT)
s05 = next((e for e in tl if str(e.get("scene_id")) == "S05"), None)
check("4 权威时间轴可加载（21 景）且 S05 窗口 = [181.776, 221.862]",
      len(tl) == 21 and s05 is not None
      and [s05.get("start_s"), s05.get("end_s")] == LG.AUTHORITATIVE_LINEAGE["s05_window"],
      {"scenes": len(tl), "s05": {"start_s": s05.get("start_s"), "end_s": s05.get("end_s")}
       if s05 else None})
conc_path = ROOT / "docs" / "regression_2x" / "logs" / "phase13e_p13e1_conclusion.json"
conc = json.loads(conc_path.read_text(encoding="utf-8")) if conc_path.is_file() else {}
check("5 与 Phase 13-E 结论 JSON 一致（防常量漂移）",
      conc.get("conclusion") == "A"
      and conc.get("authoritative_lineage", {}).get("sha256") == LG.AUTHORITATIVE_LINEAGE["sha256"]
      and conc.get("lineage_guard", {}).get("assert_lineage_on_legacy", "").startswith("REJECTED"))
src = (ROOT / "src" / "video_studio" / "core" / "lineage_guard.py").read_text(encoding="utf-8")
check("6 守卫模块不触碰 PI/DQ 阈值、不写文件、不联网（只读纯校验）",
      all(t not in src for t in ("THRESHOLDS", "PI_", "sqlite3", "requests", "open(",
                                 "write_text", "mkdir")))
check("7 两谱系在常量上互不相同（sha256/时长/S05 窗口），可机械区分",
      LG.AUTHORITATIVE_LINEAGE["sha256"] != LG.LEGACY_LINEAGE["sha256"]
      and LG.AUTHORITATIVE_LINEAGE["duration_s"] != LG.LEGACY_LINEAGE["duration_s"]
      and LG.AUTHORITATIVE_LINEAGE["s05_window"] != LG.LEGACY_LINEAGE["s05_window"])

print("\n结果: {}/{} 通过".format(len(PASS), len(PASS) + len(FAIL)))
if FAIL:
    print("失败项:", FAIL)
sys.exit(1 if FAIL else 0)
