# -*- coding: utf-8 -*-
"""P32-1：从冻结基线 ZIP 精确复原 `config/config.json`（先校验 sha256，再落盘）。

安全约束：只有从 ZIP 取出的内容 sha256 **等于** manifest 钉定值时才写盘；
否则不写、如实报错（fail-closed）。原文件先备份到 output/p32_probe/。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import sys
import zipfile

R = pathlib.Path(r"C:\mp4agent\video-studio")
TAG = "5.x-post-final-maintenance-baseline"
ZIP = R / "docs" / "regression_2x" / "baseline" / "{}.zip".format(TAG)
MAN = R / "docs" / "regression_2x" / "baseline" / "baseline_manifest_{}.json".format(TAG)
TARGET = R / "config" / "config.json"
PROBE = R / "output" / "p32_probe"


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    PROBE.mkdir(parents=True, exist_ok=True)
    man = json.loads(MAN.read_text(encoding="utf-8"))
    want = man["files"]["config/config.json"]["sha256"]
    print("manifest 钉定 sha256 :", want)
    print("ZIP                 :", ZIP.name, "{:,}B".format(ZIP.stat().st_size))

    with zipfile.ZipFile(ZIP) as z:
        names = [n for n in z.namelist() if n.replace("\\", "/").endswith("config/config.json")]
        print("ZIP 内匹配条目      :", names)
        if not names:
            print("FAIL: ZIP 内未找到 config/config.json")
            return 1
        raw = z.read(names[0])
    got = sha_bytes(raw)
    print("ZIP 内实测 sha256   :", got)
    print("MATCH" if got == want else "MISMATCH")
    if got != want:
        print("FAIL(fail-closed): ZIP 内容与 manifest 不一致 ⇒ 不写盘")
        return 1

    cur = TARGET.read_bytes()
    print()
    print("现值 sha256         :", sha_bytes(cur), "({:,}B)".format(len(cur)))
    (PROBE / "config.json.pre_p32_backup").write_bytes(cur)
    print("已备份 ->", (PROBE / "config.json.pre_p32_backup").relative_to(R).as_posix())

    # 逐字节复原
    TARGET.write_bytes(raw)
    now = sha_bytes(TARGET.read_bytes())
    print("写入后 sha256       :", now)
    ok = now == want
    print("复原结果            :", "OK ✔" if ok else "FAIL ✘")
    (PROBE / "p32_1_config_restore.json").write_text(json.dumps({
        "schema": "p32-1-config-restore-v1",
        "tag": TAG, "zip": ZIP.name,
        "manifest_sha256": want, "zip_entry": names[0], "zip_sha256": got,
        "pre_sha256": sha_bytes(cur), "post_sha256": now,
        "restored": bool(ok), "bytes": len(raw),
        "backup": "output/p32_probe/config.json.pre_p32_backup",
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
