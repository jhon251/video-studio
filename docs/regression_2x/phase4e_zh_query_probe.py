"""4.x Phase 4-E：**真实网络**中文查询探针（环境相关，失败即如实记 PENDING，不伪造）。

目的：在真实 Wikimedia Commons 上量化"中文查询"在**扩展前/后**的候选差异：
  形状 A：`shape_queries(原中文查询)`            → 通常 `cjk_only`（中文整块）
  形状 B：`shape_queries(原中文查询 + 4-E 扩展词)` → 拉丁词簇（英文查询）
对两种形状各做一次真实检索，记录候选条数与（如果检索到）命中的素材名。

纪律：本探针**只读、只记录**；网络不可用时输出 `status=PENDING(环境)` 并以 rc=0 结束（不掩盖为 PASS）。
用法：python docs/regression_2x/phase4e_zh_query_probe.py
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core.retrieval_quality import expand_query_latin, load_retrieval_lexicon  # noqa: E402
from video_studio.tools.base import ToolContext  # noqa: E402
from video_studio.tools.material_provider import MaterialQuery, TransportError  # noqa: E402
from video_studio.tools.provider_wikimedia import WikimediaCommonsProvider  # noqa: E402

LOGS = ROOT / "docs" / "regression_2x" / "logs"
LOGS.mkdir(parents=True, exist_ok=True)
FFMPEG = ROOT / "bin" / "ffmpeg.exe"
FFPROBE = ROOT / "bin" / "ffprobe.exe"

QUERIES = ["虚拟现实头显的镜片特写", "蓝鲨在亚速尔群岛海域", "量子计算机芯片的结构"]
POLICY = {"provider": "wikimedia_commons", "timeout_s": 20, "search_limit": 8,
          "min_interval_s": 2.0, "max_requests": 10, "license_required": True}
LEX = load_retrieval_lexicon()
OUT = {"phase": "4-E", "kind": "real_network_zh_query_probe", "status": None,
       "queries": [], "note": ("真实网络探针：仅记录候选条数与形状变化，不做结论外推；"
                               "网络不可用时记 PENDING(环境)。")}


def make_ctx():
    return ToolContext(role="retrieval", project_id="p_4e_probe", project_dir=ROOT / "tmp_wheels",
                       db=None, config={"tools": {"ffmpeg": {"path": str(FFMPEG),
                                                             "ffprobe": str(FFPROBE)}}})


def try_search(provider, text, ctx):
    try:
        found = provider.search(MaterialQuery(text=text[:500], limit=8), ctx)
    except TransportError as exc:
        return {"error_code": exc.code, "detail": exc.detail[:160], "n": None, "names": []}
    except Exception as exc:                      # noqa: BLE001
        return {"error_code": "PROVIDER_SEARCH_FAILED",
                "detail": "{}: {}".format(type(exc).__name__, str(exc)[:120]), "n": None, "names": []}
    return {"error_code": None, "n": len(found), "names": [c.name for c in found[:5]]}


def main():
    ctx = make_ctx()
    pending = 0
    for q in QUERIES:
        expanded = expand_query_latin(q, LEX, limit=3)
        row = {"query": q, "expanded_terms": expanded, "shapes": {}}
        # 形状 A：原样（中文）
        prov_a = WikimediaCommonsProvider(dict(POLICY))
        text_a = q
        row["shapes"]["A_original"] = {"text": text_a, "shape": prov_a.shape_queries(text_a)[1],
                                       **try_search(prov_a, text_a, ctx)}
        time.sleep(2.5)
        # 形状 B：附加 4-E 扩展词
        prov_b = WikimediaCommonsProvider(dict(POLICY))
        text_b = (q + " " + " ".join(expanded)).strip() if expanded else q
        row["shapes"]["B_expanded"] = {"text": text_b, "shape": prov_b.shape_queries(text_b)[1],
                                       **try_search(prov_b, text_b, ctx)}
        for side in ("A_original", "B_expanded"):
            if row["shapes"][side]["error_code"]:
                pending += 1
        print("[{}] A n={} ({}) | B n={} ({}) | 扩展词={}".format(
            q, row["shapes"]["A_original"]["n"], row["shapes"]["A_original"]["error_code"],
            row["shapes"]["B_expanded"]["n"], row["shapes"]["B_expanded"]["error_code"],
            expanded), flush=True)
        OUT["queries"].append(row)
        time.sleep(2.5)
    OUT["status"] = "PENDING(环境)" if pending else "OK"
    (LOGS / "phase4e_network_probe.json").write_text(
        json.dumps(OUT, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nstatus:", OUT["status"], "-> logs/phase4e_network_probe.json")


if __name__ == "__main__":
    main()
