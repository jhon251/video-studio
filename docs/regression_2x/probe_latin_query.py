"""Retry probe: does the latin-preferred shaped query return real Commons hits?"""
import sys
from pathlib import Path

ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
from video_studio.agents.retrieval.agent import kw_tokens  # noqa: E402
from video_studio.tools.base import ToolContext  # noqa: E402
from video_studio.tools.material_provider import MaterialQuery  # noqa: E402
from video_studio.tools.provider_wikimedia import WikimediaCommonsProvider  # noqa: E402

ctx = ToolContext(role="retrieval", project_id="probe", project_dir=ROOT / "tmp_wheels", db=None,
                  config={"tools": {"ffmpeg": {"path": str(ROOT / "bin" / "ffmpeg.exe"),
                                               "ffprobe": str(ROOT / "bin" / "ffprobe.exe")}}})
TEXTS = [
    "画面并置 Quest PSVR2 PICO，以及 Valve Index、Bigscreen Beyond 等头显形态。",
    "Meta Quest 3 与 PSVR2 这类头显的佩戴形态，以及 Bigscreen Beyond 的轻量化路线。",
]
for text in TEXTS:
    prov = WikimediaCommonsProvider({"provider": "wikimedia_commons", "search_limit": 8,
                                     "min_interval_s": 1.0, "timeout_s": 40,
                                     "max_bytes": 8388608, "rate_limit_retries": 2})
    try:
        found = prov.search(MaterialQuery(text=text, keywords=kw_tokens(text), limit=8), ctx)
    except Exception as exc:                                   # noqa: BLE001
        print("ERR", type(exc).__name__, str(exc)[:100])
        continue
    print("query_used=", (prov.stats.get("query_shaping") or {}).get("used"),
          "| mode=", (prov.stats.get("query_shaping") or {}).get("mode"), "| hits=", len(found))
    for c in found[:5]:
        print("   -", c.name[:58], "|", c.license, "|", c.ext, "|", c.bytes)
