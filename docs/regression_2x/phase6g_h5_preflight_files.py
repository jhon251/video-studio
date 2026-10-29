# -*- coding: utf-8 -*-
"""H5 只读 preflight（A 部分）：文件存在性 / SHA256 / 可解码 / 尺寸 / 字段与许可核验。"""
import hashlib
import json
import pathlib
import subprocess
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from PIL import Image                                                     # noqa: E402

FP = str(R / "bin" / "ffprobe.exe")
FF = str(R / "bin" / "ffmpeg.exe")
CAND = pathlib.Path(r"C:\mp4agent\h5_asset_candidates")
OUT = R / "docs" / "regression_2x" / "logs" / "phase6g_h5_preflight_files.json"

SPEC = {
    "S05": {"file": CAND / "S05" / "Russell_PM_1+1=2.png",
            "sha256": "65377b888b7782260c1cf3717a5eb9681b21e27d4d75473a95506bc397b9a6ff",
            "source_url": "https://commons.wikimedia.org/wiki/File:Russell_PM_1%2B1%3D2.png",
            "license_class": "PUBLIC_DOMAIN", "license": None,
            "attribution": "Whitehead & Russell, Principia Mathematica Vol. II (1912), p.86 — "
                           "via Wikimedia Commons", "asset_id": None},
    "S11": {"file": CAND / "S11" / "code-success.png",
            "sha256": "bdb50e986bc7fb982d1360157b31a2fbeb898c01fa3f16e22768fd64ce944b6a",
            "source_url": "https://github.com/leanprover/lean4/blob/master/doc/images/"
                          "code-success.png",
            "license_class": "APACHE_2.0", "license": "Apache-2.0",
            "attribution": "Copyright the Lean authors, Apache License 2.0", "asset_id": None},
}
REQ = ["asset_id", "path", "sha256", "license", "license_class", "source_url", "attribution"]

out = {"schema": "phase6g-h5-preflight-files-v1", "candidates_root": str(CAND), "scenes": {}}
for scene, s in SPEC.items():
    p = s["file"]
    row = {"expected": {k: s[k] for k in ("sha256", "source_url", "license", "license_class",
                                          "attribution", "asset_id")},
           "path": str(p), "exists": p.is_file()}
    if row["exists"]:
        b = p.read_bytes()
        row["bytes"] = len(b)
        row["sha256_actual"] = hashlib.sha256(b).hexdigest()
        row["sha256_match"] = row["sha256_actual"] == s["sha256"]
        row["magic"] = b[:8].hex()
        r = subprocess.run([FP, "-v", "error", "-show_entries",
                            "stream=codec_type,codec_name,width,height", "-of", "json", str(p)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        j = json.loads(r.stdout or "{}")
        row["ffprobe"] = [{"codec_type": x.get("codec_type"), "codec_name": x.get("codec_name"),
                           "width": x.get("width"), "height": x.get("height")}
                          for x in (j.get("streams") or [])]
        try:
            with Image.open(p) as im:
                row["pil"] = {"format": im.format, "mode": im.mode, "size": list(im.size)}
                row["pil_ok"] = True
        except Exception as exc:                                          # noqa: BLE001
            row["pil"] = {"error": "{}: {}".format(type(exc).__name__, str(exc)[:120])}
            row["pil_ok"] = False
        row["decodable"] = bool(row["pil_ok"]
                                and any(x["codec_type"] == "video" for x in row["ffprobe"]))
    rec = {"asset_id": s["asset_id"], "path": str(p), "sha256": s["sha256"],
           "license": s["license"], "license_class": s["license_class"],
           "source_url": s["source_url"], "attribution": s["attribution"]}
    row["license_record"] = rec
    row["missing_fields"] = [k for k in REQ
                             if rec.get(k) in (None, "", [], {})
                             or (k in ("sha256", "path") and not row.get("exists"))]
    row["license_restricted"] = False
    out["scenes"][scene] = row
    print("== {} ==".format(scene))
    print("   path exists:", row["exists"], "| bytes:", row.get("bytes"))
    print("   sha256:", row.get("sha256_actual"), "| match:", row.get("sha256_match"))
    print("   decodable:", row.get("decodable"), "| pil:", row.get("pil"), "| ffprobe:", row["ffprobe"]
          if row["exists"] else "-")
    print("   missing required fields:", row["missing_fields"])

OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print("\nfiles preflight ->", OUT)
