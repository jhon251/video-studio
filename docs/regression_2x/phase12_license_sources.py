# -*- coding: utf-8 -*-
"""Phase 12 / P12-1 + P12-2 产物脚本（**只读消费，唯一落盘点**）：
  · `logs/phase12_license_sources.json` —— 许可记录源清单（逐资产三态 HAS_RECORD/MISSING/CONFLICT）
  · `logs/license_overlay_v1.json`       —— 增强覆盖层 artifact（canonical JSON + sha256）
**不改 P7-2 原索引/任何 Phase 7 产物**；零 LLM、零网络、零执行。
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core import asset_license_join as ALJ                               # noqa: E402
from video_studio.core.visual_requirement import canonical, sha256_text               # noqa: E402

LOGS = ROOT / "docs" / "regression_2x" / "logs"
DB = ROOT / "projects" / "video_studio.db"
INDEX = LOGS / "asset_index.json"
PROJECT = "p_96efdc03e1aa"


def main() -> int:
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    cache_indexes = sorted((ROOT / "projects" / PROJECT / "media" / "external").glob(".index.json"))
    recs, manifest, notes = ALJ.collect_records(
        db_path=DB, project_id=PROJECT, logs_dir=LOGS,
        h5_path=LOGS / "phase6g_exec_h5.json", cache_index_paths=cache_indexes)
    overlay = ALJ.build_overlay(index=index, records=recs, sources_manifest=manifest, notes=notes)
    errs = ALJ.validate_overlay(overlay)
    if errs:
        print("FAIL-CLOSED 覆盖层自检失败:", errs[:4], file=sys.stderr)
        return 2
    out_path = LOGS / "license_overlay_v1.json"
    out_path.write_text(json.dumps(overlay, ensure_ascii=False, indent=1, sort_keys=True),
                        encoding="utf-8")
    inv = {
        "schema": "phase12-license-sources-v1",
        "generation_method": "read-only inventory（零 LLM、零网络、零执行）",
        "source_index": {"path": str(INDEX.relative_to(ROOT)),
                         "sha256": sha256_text(INDEX.read_text(encoding="utf-8")),
                         "schema": index.get("schema"),
                         "candidates": len(index.get("candidates") or [])},
        "record_sources_manifest": manifest,
        "negative_evidence": [
            "media/external/.index.json：字段仅 bytes/cached_at/file ⇒ **无许可字段**（P7-2 缺口根因）",
            "DB artifacts.license 列：全部行 NULL ⇒ 无可用记录",
            "下载缓存元数据不记录许可 ⇒ 本阶段不据此推断（保持 UNKNOWN）"],
        "records_total": len(recs),
        "records_dropped_unknown": None,
        "assets": [{"asset_id": e["asset_id"], "asset_sha256": e["asset_sha256"],
                    "index_license": e["index_license"],
                    "index_license_class": e["index_license_class"],
                    "state": e["state"], "license": e["license"],
                    "license_class": e["license_class"], "attribution": e["attribution"],
                    "record_count": e["record_count"],
                    "source_of_record": e["source_of_record"],
                    "missing_reason": e["missing_reason"],
                    "conflict": e["conflict"],
                    "record_locations": [{"source_type": r["source_type"],
                                          "locator": r["locator"],
                                          "record_sha256": r["record_sha256"]}
                                         for r in e["records"]],
                    "changes_index_license": e["changes_index_license"]}
                   for e in overlay["entries"]],
        "counts": overlay["counts"],
        "overlay": {"path": str(out_path.relative_to(ROOT)), "schema": overlay["schema"],
                    "artifact_hash": overlay["artifact_hash"],
                    "join_rule_version": overlay["join_rule_version"]},
        "unmatched_records": len(overlay["unmatched_records"]),
        "read_only": True, "zero_execution": True,
    }
    (LOGS / "phase12_license_sources.json").write_text(
        json.dumps(inv, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    print("记录源清单:", json.dumps(manifest, ensure_ascii=False)[:300])
    print("记录数:", len(recs), "| 三态计数:", overlay["counts"])
    for e in overlay["entries"]:
        print("  {:24s} index={:12s} -> state={:10s} class={:16s} src={}".format(
            e["asset_id"], str(e["index_license"])[:12], e["state"], e["license_class"],
            (e["source_of_record"] or {}).get("locator", "-")[:44]))
    print("覆盖层:", out_path.name, "| hash:", overlay["artifact_hash"][:16],
          "| 自检:", "OK" if not errs else errs)
    print("未匹配记录数:", len(overlay["unmatched_records"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
