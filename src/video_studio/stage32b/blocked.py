"""P0-4 BLOCKED / NO_SAFE_MATCH 缺口处理。

安全边界（只读 3.1.4，绝不修改/重检索/降阈值）：
- sem >= 50 且 rights in (SAFE,CONDITIONAL) -> USE_MATERIAL
- 45 <= sem < 50 -> MARGINAL（不自动接受，TEXT_CARD fallback + 人工待审）
- NO_SAFE_MATCH / 无 primary -> TEXT_CARD fallback（SELF_CREATED，不伪造外部素材）
- 绝不使用 UNKNOWN/UNSAFE；绝不为画面完整度塞弱匹配。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

GEN_VERSION = "3.2b-p04"
ACCEPT_SEM = 50.0   # P0-4 自动接受线（严于 3.1.4 阈值 45，只升不降）


def _sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def build_blocked(pkg_dir: Path, alignment_path: Path,
                  out_dir: Path, force: bool = False) -> dict:
    shots_path = pkg_dir / "shot_mapping" / "all_shots.json"
    meta_path = pkg_dir / "metadata" / "materials.json"
    al = json.loads(alignment_path.read_text(encoding="utf-8"))
    shots = json.loads(shots_path.read_text(encoding="utf-8"))["shots"]
    in_fp = hashlib.sha256(
        (shots_path.read_text(encoding="utf-8")
         + meta_path.read_text(encoding="utf-8")
         + alignment_path.read_text(encoding="utf-8")).encode("utf-8")).hexdigest()[:16]
    out_path = out_dir / "manifests" / "blocked_manifest.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists() and not force:
        m = json.loads(out_path.read_text(encoding="utf-8"))
        if m.get("input_fingerprint") == in_fp:
            print(f"blocked manifest 已存在（指纹一致），跳过：{out_path}")
            return m

    rows, nar_texts = [], {}
    for sh in al["shots"]:
        nar_texts[sh["shot_id"]] = "".join(s["text"] for s in sh["segments"])

    for sid in sorted(shots):
        slot = shots[sid]
        rec = slot.get("primary")
        narration = nar_texts.get(sid, "")
        if rec and rec.get("rights_status") in ("SAFE", "CONDITIONAL"):
            sem = (rec.get("score_detail") or {}).get("semantic_match", 0)
            if sem >= ACCEPT_SEM:
                rows.append({
                    "shot_id": sid, "original_status": "PRIMARY",
                    "selected_action": "USE_MATERIAL",
                    "action_type": rec["rights_status"],
                    "reason": f"semantic {sem} >= {ACCEPT_SEM}，rights {rec['rights_status']}",
                    "source_material": rec.get("material_id"),
                    "source_url": rec.get("source_url", ""),
                    "license": rec.get("license", ""),
                    "attribution": rec.get("attribution_text", ""),
                    "narration": narration,
                })
                continue
            rows.append({
                "shot_id": sid, "original_status": "PRIMARY(MARGINAL)",
                "selected_action": "TEXT_CARD",
                "action_type": "SELF_CREATED",
                "reason": f"semantic {sem} < {ACCEPT_SEM}，按 P0-4 边界不自动接受弱匹配（原: "
                          f"{(rec.get('visual_description') or '')[:40]}）",
                "source_material": None, "source_url": "", "license": "",
                "attribution": "", "narration": narration,
                "human_action_required": True,
            })
        else:
            rows.append({
                "shot_id": sid, "original_status": "NO_SAFE_MATCH",
                "selected_action": "TEXT_CARD",
                "action_type": "SELF_CREATED",
                "reason": "3.1.4 NO_SAFE_MATCH（不重检索/不硬凑）",
                "source_material": None, "source_url": "", "license": "",
                "attribution": "", "narration": narration,
                "human_action_required": True,
            })

    manifest = {
        "input_fingerprint": in_fp,
        "narration_sha": al.get("narration_sha", ""),
        "material_package_sha": _sha256_file(shots_path),
        "alignment_manifest_sha": _sha256_file(alignment_path),
        "generator_version": GEN_VERSION,
        "accept_sem": ACCEPT_SEM,
        "shots": rows,
    }
    out_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                        encoding="utf-8")

    # 人工检查清单
    md = ["# BLOCKED Review（《珊瑚礁正在消失》20 镜）", "",
          "| 镜 | 处理 | 类型 | 原因/来源 |", "|---|---|---|---|"]
    for r in rows:
        src = r.get("source_material") or r.get("reason", "")
        md.append(f"| {r['shot_id']} | {r['selected_action']} | {r['action_type']} "
                  f"| {src[:60]} |")
    (out_dir / "blocked_review.md").write_text("\n".join(md), encoding="utf-8")

    use = sum(1 for r in rows if r["selected_action"] == "USE_MATERIAL")
    block = len(rows) - use
    print(f"blocked 完成：USE_MATERIAL {use} / 20，TEXT_CARD fallback {block}")
    return manifest


def gate_blocked(manifest: dict) -> dict:
    checks = []

    def check(name, cond, detail=""):
        checks.append((name, cond))
        print(f"{'PASS' if cond else 'FAIL'}  {name} {detail}")

    rows = manifest["shots"]
    check("20/20 镜均有明确处理状态", len(rows) == 20, f"({len(rows)})")
    check("0 个 NO_SAFE_MATCH 被改成 SAFE/USE_MATERIAL", all(
        not (r["original_status"] == "NO_SAFE_MATCH"
             and r["selected_action"] == "USE_MATERIAL") for r in rows))
    check("0 个 UNKNOWN/UNSAFE 进入", all(
        r["action_type"] in ("SAFE", "CONDITIONAL", "SELF_CREATED") for r in rows))
    check("0 个弱匹配被强制接受", all(
        not (r.get("original_status") == "PRIMARY(MARGINAL)"
             and r["selected_action"] == "USE_MATERIAL") for r in rows))
    check("fallback 均明确标记 SELF_CREATED", all(
        r["action_type"] == "SELF_CREATED" or r["selected_action"] == "USE_MATERIAL"
        for r in rows))
    check("narration↔shot 映射完整", all(r.get("narration") for r in rows))
    check("provenance 完整", all(k in manifest for k in
                                 ("narration_sha", "material_package_sha",
                                  "alignment_manifest_sha", "generator_version",
                                  "input_fingerprint")))
    ok = all(c[1] for c in checks)
    print(f"\nP0-4 Gate: {'PASS' if ok else 'FAIL'}")
    return {"gate": "PASS" if ok else "FAIL",
            "fails": [c[0] for c in checks if not c[1]]}
