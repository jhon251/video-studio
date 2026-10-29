# -*- coding: utf-8 -*-
"""P32-1：把 `bank_derived` 从被钉定的 `config.json` 迁移到外部文件链
`config/frame_match.json`（同 `render_motion.json` 模式）。

`config.json` 已按基线 ZIP 逐字节复原（sha 7b03424846f1…），本脚本**不再触碰它**。
默认关闭语义不变：外部文件缺失 ⇒ bank_derived=False。
"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
PROBE = R / "output" / "p32_probe"
BACKUP = PROBE / "config.json.pre_p32_backup"
EXT = R / "config" / "frame_match.json"
MAN = R / "docs" / "regression_2x" / "baseline" / \
    "baseline_manifest_5.x-post-final-maintenance-baseline.json"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    # 从复原前的备份里取回原 note 原文（避免手工重打的编码误差）
    block = {}
    if BACKUP.is_file():
        old = json.loads(BACKUP.read_text(encoding="utf-8"))
        block = ((old.get("tools") or {}).get("frame_match") or {})
    note = str(block.get("_note_p27") or "").strip()
    if not note:
        note = ("P27-1：派生段核验口径（子窗口 bank 最大 corr）。默认应为 false；"
                "本阶段按授权开启。")
    doc = {
        "frame_match": {
            "bank_derived": "v2",
            "_note_p27": note,
            "_note_p32": ("P32-2：`bank_derived` 自 config.json 迁移至本外部文件（同 "
                          "render_motion.json 模式）。`config.json` 为基线 manifest 钉定文件"
                          "（sha 7b03424846f1…），**不得**再承载运行期开关。"
                          "取值：false/缺失=关闭；\"v1\"=冻结口径(48,5×5)；"
                          "\"v2\"=P32-2 修复口径(192,步进≤170px)。**默认关闭**。"),
            "version": "bank-derived-v2",
        }
    }
    EXT.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("已写出 ->", EXT.relative_to(R).as_posix())
    print(json.dumps(doc, ensure_ascii=False, indent=2))
    # 复核 config.json 仍为钉定值
    import hashlib
    want = json.loads(MAN.read_text(encoding="utf-8"))["files"]["config/config.json"]["sha256"]
    now = hashlib.sha256((R / "config" / "config.json").read_bytes()).hexdigest()
    print()
    print("config.json sha256 :", now)
    print("基线钉定值         :", want)
    print("一致               :", "OK ✔" if now == want else "FAIL ✘")
    return 0 if now == want else 1


if __name__ == "__main__":
    raise SystemExit(main())
