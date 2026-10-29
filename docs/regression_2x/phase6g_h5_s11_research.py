# -*- coding: utf-8 -*-
"""S11 候选研究（只读/仅新建研究目录）：下载 LIPIcs ITP 2023 #24 PDF，核验许可，提取内嵌图。"""
import hashlib
import io
import pathlib
import re
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
OUT = pathlib.Path(r"C:\mp4agent\h5_asset_candidates\S11\research")
OUT.mkdir(parents=True, exist_ok=True)
URLS = [
    "https://drops.dagstuhl.de/storage/01lipics/lipics-vol268-itp2023/LIPIcs.ITP.2023.24/"
    "LIPIcs.ITP.2023.24.pdf",
    "https://drops.dagstuhl.de/opus/volltexte/2023/18374/pdf/LIPIcs.ITP.2023.24.pdf",
]
pdf = OUT / "LIPIcs.ITP.2023.24.pdf"
if not pdf.is_file():
    for u in URLS:
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            if data[:4] == b"%PDF":
                pdf.write_bytes(data)
                print("downloaded:", u, len(data), "bytes")
                break
            print("not a pdf:", u, data[:40])
        except Exception as exc:                                          # noqa: BLE001
            print("fail:", u, type(exc).__name__, str(exc)[:120])
print("pdf sha256:", hashlib.sha256(pdf.read_bytes()).hexdigest(), pdf.stat().st_size, "bytes")

from pypdf import PdfReader                                              # noqa: E402
rd = PdfReader(str(pdf))
print("pages:", len(rd.pages))
head = (rd.pages[0].extract_text() or "")[:1200]
print("---- page1 head ----")
print(head)
lic = [l for l in re.findall(r"[^\n]*[Cc]reative [Cc]ommons[^\n]*", "\n".join(
    (rd.pages[i].extract_text() or "") for i in range(min(3, len(rd.pages)))))]
print("license lines:", lic[:4])
imgs = []
for i, page in enumerate(rd.pages):
    try:
        for j, im in enumerate(page.images):
            imgs.append({"page": i + 1, "idx": j, "name": im.name, "bytes": len(im.data),
                         "data": im.data})
    except Exception as exc:                                              # noqa: BLE001
        print("page", i + 1, "images error:", type(exc).__name__, str(exc)[:80])
print("embedded images:", len(imgs))
for k, im in enumerate(imgs):
    print("  [{}] page {} name {} bytes {}".format(k, im["page"], im["name"], im["bytes"]))
