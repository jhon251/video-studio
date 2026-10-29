"""Stage 3.1 SEAL 前 Material Package 完整性校验（只读验证，不修改任何产物）。"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "output" / "production_002" / "material_package_31"

REQUIRED_DIRS = ["materials", "metadata", "rights", "shot_mapping", "search_log"]
PROVENANCE_FIELDS = ["material_id", "shot_id", "source_url", "original_url",
                     "source_name", "creator", "license", "rights_status",
                     "commercial_use", "attribution_required", "attribution_text",
                     "download_url", "retrieved_at", "content_type", "resolution",
                     "visual_description", "match_type", "copyright_notes"]


def main() -> int:
    checks = []

    def check(name, cond, detail=""):
        checks.append((name, cond))
        print(f"{'PASS' if cond else 'FAIL'}  {name} {detail}")

    # 1) 六件套存在
    for d in REQUIRED_DIRS:
        check(f"目录存在 {d}", (PKG / d).is_dir())
    check("README.md 存在", (PKG / "README.md").exists())

    # 2) metadata 完整 + provenance 字段
    meta = json.loads((PKG / "metadata" / "materials.json").read_text(encoding="utf-8"))
    mats = meta["materials"]
    check("metadata 有素材记录", len(mats) > 0, f"({len(mats)})")
    missing_fields = [(m["material_id"], f) for m in mats for f in PROVENANCE_FIELDS
                      if f not in m]
    check("全部素材 provenance 18 字段完整", not missing_fields, str(missing_fields[:3]))

    # 3) shot_mapping 44 镜 + 引用一致
    shots = json.loads((PKG / "shot_mapping" / "all_shots.json").read_text(encoding="utf-8"))["shots"]
    check("44 镜映射齐全", all(f"S{i:02d}" in shots for i in range(1, 45)),
          f"({len(shots)} 镜)")
    ids = {m["material_id"] for m in mats}
    dangling = []
    for sid, slot in shots.items():
        for rec in ([slot.get("primary")] + list(slot.get("alternatives") or [])):
            if rec and rec["material_id"] not in ids:
                dangling.append((sid, rec["material_id"]))
    check("映射引用的 material_id 均在 metadata 中", not dangling, str(dangling[:3]))

    # 4) 版权硬门槛：入池记录（有 match_score）不得是 UNSAFE/UNKNOWN
    bad = [m["material_id"] for m in mats if m.get("match_score") is not None
           and m["rights_status"] not in ("SAFE", "CONDITIONAL")]
    check("推荐池仅 SAFE/CONDITIONAL（硬门槛）", not bad, str(bad[:3]))

    # 5) rights 与 metadata 一一对应
    rights = json.loads((PKG / "rights" / "rights_summary.json").read_text(encoding="utf-8"))
    check("rights 条目与 metadata 一一对应",
          {r["material_id"] for r in rights} == ids,
          f"({len(rights)} vs {len(ids)})")

    # 6) NO_SAFE_MATCH 记录完整
    no_safe = json.loads((PKG / "shot_mapping" / "all_shots.json").read_text(encoding="utf-8"))["no_safe_match"]
    ok_ns = all(n.get("searched_queries") and n.get("searched_sources")
                and n.get("recommendation") for n in no_safe)
    check("NO_SAFE_MATCH 记录含检索词/来源/自制建议", ok_ns, f"({len(no_safe)} 镜)")

    # 7) search_log 覆盖 44 镜 + 来源状态
    log = json.loads((PKG / "search_log" / "search_log.json").read_text(encoding="utf-8"))
    check("search_log 覆盖 44 镜", len(log["queries"]) == 44, f"({len(log['queries'])})")
    check("search_log 有来源状态", bool(log.get("source_status")), str(log["source_status"]))

    # 8) materials/ 预览文件与 metadata.preview_file 一致
    refs = [m["preview_file"] for m in mats if m.get("preview_file")]
    missing_files = [f for f in refs if not (PKG / "materials" / f).exists()]
    check(f"预览文件齐备（{len(refs)} 个引用）", not missing_files, str(missing_files[:3]))

    failed = [c for c in checks if not c[1]]
    print(f"\n完整性校验: {len(checks) - len(failed)}/{len(checks)} 通过")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
