# -*- coding: utf-8 -*-
"""P32-4 核查：生产逐景核验是否真的走了 **bank-derived-v2**。

读渲染产物 artifact，检查 scene evidence 是否含 `bank_version` / `corr_bank`，
并列出 corr_expected 与 bank 值。只读。
"""
from __future__ import annotations

import collections
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
ART = R / "projects" / "p_b9a90ed75d67" / "artifacts"
sys.stdout.reconfigure(encoding="utf-8")


def main() -> int:
    for f in sorted(ART.glob("a_*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:                                                   # noqa: BLE001
            continue
        if not isinstance(d, dict):
            continue
        keys = set(d.keys())
        if not ({"scene_evidence", "material_verification"} & keys
                or "bank_version" in json.dumps(d)[:200000]):
            continue
        mv = d.get("material_verification") or {}
        se = d.get("scene_evidence") or []
        print("=== {} ({:,}B) ===".format(f.name, f.stat().st_size))
        print("  keys:", sorted(keys)[:14])
        print("  material_verification: bank_derived={} bank_version={} source={}".format(
            mv.get("bank_derived"), mv.get("bank_version"),
            str(mv.get("bank_config_source"))[-60:]))
        print("  checked={} failed={} placeholder={}".format(
            len(mv.get("checked_scenes") or []), len(mv.get("failed_scenes") or []),
            len(mv.get("placeholder_verified") or [])))
        withbank = [r for r in se if r.get("corr_bank") is not None]
        print("  含 corr_bank 的景: {}/{}".format(len(withbank), len(se)))
        vers = collections.Counter(str(r.get("bank_version")) for r in se)
        print("  bank_version 分布:", dict(vers))
        for r in se[:40]:
            if r.get("corr_bank") is not None:
                print("    {:<8} corr_expected={:<8} corr_bank={:<8} full={}".format(
                    r.get("scene_id"), r.get("corr_expected"), r.get("corr_bank"),
                    r.get("corr")))
        return 0
    print("未找到含核验证据的 artifact")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
