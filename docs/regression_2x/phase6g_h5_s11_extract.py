# -*- coding: utf-8 -*-
"""提取 LIPIcs.ITP.2023.24 论文内嵌图（本地 PDF，pypdf），并核验首页许可声明。"""
import hashlib
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
RD = pathlib.Path(r"C:\mp4agent\h5_asset_candidates\S11\research")
pdf = RD / "LIPIcs.ITP.2023.24.pdf"
FIGS = RD / "figures"
FIGS.mkdir(parents=True, exist_ok=True)
print("pdf:", pdf.is_file(), pdf.stat().st_size if pdf.is_file() else None,
      "| sha256:", hashlib.sha256(pdf.read_bytes()).hexdigest() if pdf.is_file() else None)
from pypdf import PdfReader                                               # noqa: E402
from PIL import Image                                                     # noqa: E402
rd = PdfReader(str(pdf))
print("pages:", len(rd.pages))
t1 = rd.pages[0].extract_text() or ""
print("has CC-BY statement:",
      bool(re.search(r"Creative Commons Attribution 4\.0|CC-BY", t1 + (rd.pages[-1].extract_text() or ""))))
m = re.findall(r"[^\n]*[Cc]reative [Cc]ommons[^\n]*", t1 + "\n" + (rd.pages[-1].extract_text() or ""))
print("license text:", m[:2])
print("title:", (t1.strip().splitlines() or [""])[0][:120])
saved = []
for i, page in enumerate(rd.pages):
    try:
        for j, im in enumerate(page.images):
            ext = pathlib.Path(im.name).suffix or ".png"
            out = FIGS / "p{:02d}_{}{}".format(i + 1, j, ext)
            out.write_bytes(im.data)
            with Image.open(out) as p:
                sz, fmt = p.size, p.format
            saved.append({"page": i + 1, "file": out.name, "bytes": len(im.data),
                          "size": sz, "format": fmt,
                          "sha256": hashlib.sha256(im.data).hexdigest()})
    except Exception as exc:                                              # noqa: BLE001
        print("page", i + 1, "err", type(exc).__name__, str(exc)[:70])
print("embedded images:", len(saved))
for s in sorted(saved, key=lambda x: -x["bytes"])[:14]:
    print("  p{:>2} {} {:>8} B {:>12} {}".format(s["page"], s["file"], s["bytes"],
                                                 "x".join(map(str, s["size"])), s["sha256"][:16]))
(RD / "figures_index.txt").write_text(
    "\n".join("{} {} {} {}".format(s["page"], s["file"], s["bytes"], s["sha256"])
              for s in saved), encoding="utf-8")
