# -*- coding: utf-8 -*-
"""5-D 调试：复现测试里对冻结产物的 temporal_report 调用并打印错误码。"""
import json
import pathlib
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
from video_studio.ops.mm_temporal import temporal_report  # noqa: E402

tmp = pathlib.Path(tempfile.mkdtemp(prefix="vs_mmt_dbg_"))
for tag, with5 in (("with5a", True), ("no5a", False)):
    rep = temporal_report(ROOT / "projects" / "video_studio.db", "p_f4b466a4a024",
                          artifact_id="a_2ed5f41d6b58", frames_dir=tmp / tag, with_five_a=with5)
    print(tag, "applied=", rep.get("applied"), "counts=", rep.get("counts"),
          "error=", rep.get("error"), "ref5_ok=", (rep.get("meta") or {}).get("five_a_reference_ok"))
    sc = (rep.get("scenes") or [{}])[0]
    print("   scene0 keys:", sorted(sc.keys())[:8], "frame_count=", sc.get("frame_count"))
