# -*- coding: utf-8 -*-
"""P33：把被 5.x 基线 manifest **钉定**的 `core/materials.py` 逐字节复原（sha256 校验后写盘）。

原因（实测踩坑）：`core/materials.py` 属 `tests/maintenance_fixes_test.py::M8a` 的
"thresholds" 守卫组，被 manifest **逐字节钉定**；P33-2 曾在其 `DEFAULT_POLICY` 与
`policy_from_config` 中加键 ⇒ **破坏冻结不变式**（M8a FAIL）。
分配纪律改为**在 agent 层从 `config.editing` 读取**，从而无需改动该冻结文件。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import zipfile

R = pathlib.Path(r"C:\mp4agent\video-studio")
TAG = "5.x-post-final-maintenance-baseline"
ZIP = R / "docs" / "regression_2x" / "baseline" / "{}.zip".format(TAG)
MAN = R / "docs" / "regression_2x" / "baseline" / "baseline_manifest_{}.json".format(TAG)
REL = "src/video_studio/core/materials.py"
TARGET = R / REL


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    man = json.loads(MAN.read_text(encoding="utf-8"))
    want = man["files"][REL]["sha256"]
    with zipfile.ZipFile(ZIP) as z:
        names = [n for n in z.namelist() if n.replace("\\", "/").endswith(REL)]
        if not names:
            print("FAIL: ZIP 内未找到", REL)
            return 1
        raw = z.read(names[0])
    got = hashlib.sha256(raw).hexdigest()
    now = hashlib.sha256(TARGET.read_bytes()).hexdigest()
    print("manifest 钉定 :", want)
    print("ZIP 内实测    :", got, "MATCH" if got == want else "MISMATCH")
    print("当前磁盘      :", now, "MATCH" if now == want else "MISMATCH")
    if got != want:
        print("FAIL(fail-closed): ZIP 与 manifest 不一致 ⇒ 不写盘")
        return 1
    if now == want:
        print("已是钉定值 ⇒ 无需复原")
        return 0
    (R / "output" / "p33_probe").mkdir(parents=True, exist_ok=True)
    (R / "output" / "p33_probe" / "materials.py.pre_restore").write_bytes(TARGET.read_bytes())
    TARGET.write_bytes(raw)
    after = hashlib.sha256(TARGET.read_bytes()).hexdigest()
    print("写入后        :", after, "OK" if after == want else "FAIL")
    return 0 if after == want else 1


if __name__ == "__main__":
    raise SystemExit(main())
