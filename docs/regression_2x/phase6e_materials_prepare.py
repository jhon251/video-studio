# -*- coding: utf-8 -*-
"""6-E 素材准备（**只做素材/证据准备**，不执行、不调用 ffmpeg、不碰成片）。

用法:
    python docs/regression_2x/phase6e_materials_prepare.py search
    python docs/regression_2x/phase6e_materials_prepare.py download

search  : 用 Wikimedia Commons API 检索候选（打印许可证/尺寸/来源页），不落盘；
download: 按 CURATED 清单下载到 phase6e_materials/<item>/，并写 provenance JSON（含 sha256）。

许可策略：只接受 **PD / CC0 / CC BY / CC BY-SA**；PD/CC0 优先；需要署名者记录署名要求。
"""
import hashlib
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
MAT = ROOT / "docs" / "regression_2x" / "phase6e_materials"
API = "https://commons.wikimedia.org/w/api.php"
UA = ("video-studio-6e-material-prep/1.0 (offline research; contact: local) "
      "python-urllib/3")
OK_LICENSES = ("cc0", "public domain", "cc by", "cc by-sa", "pd")

SEARCHES = {
    "e4_kepler": ["sphere packing", "cannonball stack pyramid", "close packing of spheres",
                  "hexagonal close packed lattice", "face centered cubic lattice",
                  "Kepler conjecture", "cannon balls pile"],
    "e3_lean": ["Lean theorem prover", "mathematical proof assistant screenshot",
                "formal verification mathematics", "Coq proof assistant"],
    "e5_formalization": ["AlphaGeometry", "International Mathematical Olympiad 2024",
                         "automated theorem proving"],
    "e2_tymoszko": ["four color theorem map", "Thomas Tymoczko", "mathematical proof manuscript"],
}

# 人工核定后的下载清单（search 结果出来后填写；license 必须为 OK_LICENSES 之一）
CURATED = [
    {"item": "e4_kepler", "title": "File:(View of rows of stacked cannon balls.) - NARA - 528102.jpg",
     "why": "美国国家档案馆藏 19 世纪实拍：等球（炮弹）堆垛 —— 开普勒猜想的现实来源",
     "usage": "E4 信息槽①『等球最密堆积』的现实示例（P1 层，真实照片，PD）"},
    {"item": "e4_kepler", "title": "File:Close packing.svg",
     "why": "PD 图解：密堆积/面心立方与六方最密堆积的层间关系（结构对比）",
     "usage": "E4 信息槽②『FCC/HCP 候选结构对比』（P2 层，PD 图解）"},
    {"item": "e4_kepler", "title": "File:Kepler conjecture 1.jpg",
     "why": "PD：开普勒 1611 年《六角雪花》中的堆垛示意（历史锚点）",
     "usage": "E4 信息槽① 历史锚点（P1 层小图，PD）"},
    {"item": "e4_kepler", "title": "File:Close packing of spheres by William Barlow 1883 figs. 1-4.png",
     "why": "PD：Barlow 1883 年提出的球密堆积图示（历史文献）",
     "usage": "E4 信息槽② 历史锚点（P2 层小图，PD）"},
]

# E3：真实公开、可核验、许可明确的**代码/许可**文件（不自造内容）
E3_FILES = [
    {"url": "https://raw.githubusercontent.com/leanprover-community/mathlib4/master/LICENSE",
     "name": "mathlib4_LICENSE.txt",
     "why": "mathlib4 的许可证原文（Apache-2.0），用于合规署名与许可核验",
     "usage": "E3 许可依据（不自造）"},
    {"url": ("https://raw.githubusercontent.com/leanprover-community/mathlib4/master/"
             "Mathlib/Algebra/Group/Defs.lean"),
     "name": "mathlib4_Algebra_Group_Defs.lean",
     "why": "mathlib4 真实源码（含 def/theorem/`:= by` 策略证明；5,442 B）——用于逐字引用",
     "usage": "E3 视觉中的真实代码引用（逐字、附许可与来源 URL）"},
]


def api_get(params: dict, tries: int = 4) -> dict:
    """Commons API 调用（带退避重试：429/5xx 时等待 15/45/90/150 秒）。"""
    import time
    params = {**params, "format": "json", "formatversion": "2"}
    url = API + "?" + urllib.parse.urlencode(params)
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:                                            # noqa: BLE001
            last = e
            wait = (15, 45, 90, 150)[min(i, 3)]
            print("     [api retry {}] {} -> sleep {}s".format(i + 1, e, wait), flush=True)
            time.sleep(wait)
    raise last


def search(term: str, limit: int = 8) -> list:
    d = api_get({"action": "query", "generator": "search", "gsrsearch": term,
                 "gsrnamespace": "6", "gsrlimit": str(limit), "prop": "imageinfo",
                 "iiprop": "url|size|mime|extmetadata|sha1"})
    out = []
    for page in ((d.get("query") or {}).get("pages") or []):
        ii = (page.get("imageinfo") or [{}])[0]
        em = ii.get("extmetadata") or {}
        lic = (em.get("LicenseShortName") or {}).get("value") or ""
        out.append({"title": page.get("title"), "license": lic,
                    "artist": (em.get("Artist") or {}).get("value", "")[:80],
                    "mime": ii.get("mime"), "width": ii.get("width"), "height": ii.get("height"),
                    "bytes": ii.get("size"), "url": ii.get("url"),
                    "page": ii.get("descriptionurl"),
                    "license_url": (em.get("LicenseUrl") or {}).get("value"),
                    "attribution_required": (em.get("AttributionRequired") or {}
                                             ).get("value")})
    return out


def ok_license(lic: str) -> bool:
    low = (lic or "").lower()
    return any(k in low for k in OK_LICENSES)


def sha_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def download() -> None:
    prov_path = MAT / "phase6e_material_provenance.json"
    prov = json.loads(prov_path.read_text(encoding="utf-8")) if prov_path.is_file() else {
        "schema": "phase6e-material-provenance-v1", "stage": "6-E",
        "policy": "只接受 PD / CC0 / CC BY / CC BY-SA；需要署名者逐条记录；禁止 IMO 合影",
        "files": []}
    for item in CURATED:
        import time
        time.sleep(6)                      # 遵守 API 礼貌速率，避免 429
        d = search(item["title"].replace("File:", ""), limit=3)
        meta = next((x for x in d if x["title"] == item["title"]), None)
        if not meta:
            d2 = api_get({"action": "query", "titles": item["title"], "prop": "imageinfo",
                          "iiprop": "url|size|mime|extmetadata|sha1"})
            pg = ((d2.get("query") or {}).get("pages") or [{}])[0]
            ii = (pg.get("imageinfo") or [{}])[0]
            em = ii.get("extmetadata") or {}
            meta = {"title": pg.get("title"),
                    "license": (em.get("LicenseShortName") or {}).get("value") or "",
                    "artist": (em.get("Artist") or {}).get("value", "")[:120],
                    "mime": ii.get("mime"), "width": ii.get("width"), "height": ii.get("height"),
                    "bytes": ii.get("size"), "url": ii.get("url"),
                    "page": ii.get("descriptionurl"),
                    "license_url": (em.get("LicenseUrl") or {}).get("value"),
                    "attribution_required": (em.get("AttributionRequired") or {}).get("value")}
        if not ok_license(meta.get("license", "")):
            print("SKIP(license) ", meta.get("title"), meta.get("license"))
            continue
        dst = MAT / item["item"] / urllib.parse.unquote(
            Path(urllib.parse.urlsplit(meta["url"]).path).name)
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.is_file():
            req = urllib.request.Request(meta["url"], headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=180) as r, open(dst, "wb") as f:
                f.write(r.read())
        rec = {"item": item["item"], "title": meta["title"], "why": item["why"],
               "usage": item["usage"], "local_path": str(dst.relative_to(ROOT)),
               "bytes": dst.stat().st_size, "sha256": sha_file(dst),
               "source_page_url": meta["page"], "file_url": meta["url"],
               "license": meta["license"], "license_url": meta["license_url"],
               "artist": meta["artist"],
               "attribution_required": meta["attribution_required"],
               "dimensions": [meta["width"], meta["height"]], "mime": meta["mime"]}
        prov["files"] = [f for f in prov["files"] if f["local_path"] != rec["local_path"]] + [rec]
        print("SAVED", rec["local_path"], rec["bytes"], "B", rec["sha256"][:16], rec["license"])
    prov_path.write_text(json.dumps(prov, ensure_ascii=False, indent=1), encoding="utf-8")
    print("provenance ->", prov_path.relative_to(ROOT))


def download_e3() -> None:
    """下载 E3 需要的真实公开文件（Apache-2.0 许可的 mathlib4 源码与许可证原文）。"""
    prov_path = MAT / "phase6e_material_provenance.json"
    prov = json.loads(prov_path.read_text(encoding="utf-8")) if prov_path.is_file() else {
        "schema": "phase6e-material-provenance-v1", "stage": "6-E",
        "policy": "只接受 PD / CC0 / CC BY / CC BY-SA；需要署名者逐条记录；禁止 IMO 合影",
        "files": []}
    for f in E3_FILES:
        dst = MAT / "e3_lean" / f["name"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.is_file():
            req = urllib.request.Request(f["url"], headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=180) as r, open(dst, "wb") as fh:
                fh.write(r.read())
        rec = {"item": "e3_lean", "title": f["name"], "why": f["why"], "usage": f["usage"],
               "local_path": str(dst.relative_to(ROOT)), "bytes": dst.stat().st_size,
               "sha256": sha_file(dst), "source_page_url": f["url"], "file_url": f["url"],
               "license": "Apache-2.0", "license_url": "https://www.apache.org/licenses/LICENSE-2.0",
               "artist": "The mathlib Community", "attribution_required": "yes",
               "dimensions": None, "mime": "text/plain",
               "note": "引用该源码片段时必须保留『mathlib4 (Apache-2.0)』署名并附文件 URL"}
        prov["files"] = [x for x in prov["files"] if x["local_path"] != rec["local_path"]] + [rec]
        print("SAVED", rec["local_path"], rec["bytes"], "B", rec["sha256"][:16], rec["license"])
    prov_path.write_text(json.dumps(prov, ensure_ascii=False, indent=1), encoding="utf-8")
    print("provenance ->", prov_path.relative_to(ROOT))


mode = sys.argv[1] if len(sys.argv) > 1 else "search"
if mode == "download":
    download()
elif mode == "download_e3":
    download_e3()
else:
    for item, terms in SEARCHES.items():
        print("=" * 20, item)
        for t in terms:
            try:
                rows = search(t, limit=6)
            except Exception as e:                                        # noqa: BLE001
                print("  [{}] ERR {}".format(t, e))
                continue
            print("  --", t)
            for r in rows:
                print("     {:58s} | {:16s} | {}x{} | {} | {}".format(
                    (r["title"] or "")[:58], (r["license"] or "")[:16], r["width"], r["height"],
                    r["mime"], "OK" if ok_license(r["license"]) else "--"))
