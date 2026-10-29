"""汇总 Stage 3.1.3 benchmark 结果（只读分析）。"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
PKGS = ROOT / "output" / "stage31_testpkgs"

# 人工判定每个主题的"明显错误"线索词（仅用于统计展示，非系统逻辑）
ERROR_HINTS = {
    "busy": ["world war", "wwi", "war", "artificial intelligence", "hologram",
             "dall-e", "chatbot"],
    "phone": ["typewriter", "world war", "astronaut", "spacewalk", "tractor"],
    "study": ["iskendername", "manuscript", "1475", "ancient"],
    "nightcity": ["office worker", "desk", "typewriter", "ai"],
    "jarvis": ["chair", "protest", "police", "typewriter", "world war", "manuscript"],
}


def analyze(theme: str, mode: str) -> dict:
    base = PKGS / theme / f"material_pkg_{mode}"
    if not (base / "shot_mapping" / "all_shots.json").exists():
        return {"theme": theme, "mode": mode, "missing": True}
    shots = json.loads((base / "shot_mapping" / "all_shots.json").read_text(encoding="utf-8"))["shots"]
    ns = json.loads((base / "shot_mapping" / "all_shots.json").read_text(encoding="utf-8"))["no_safe_match"]
    n_total = len(shots)
    n_primary = sum(1 for s in shots.values() if s.get("primary"))
    errors, reuses, tops = [], 0, 0
    used = set()
    for sid, slot in sorted(shots.items()):
        rec = slot.get("primary")
        if not rec:
            continue
        desc = (rec.get("visual_description") or "").lower()
        if rec.get("reuse_penalty") or rec.get("diversity_penalty"):
            reuses += 1
        if any(h in desc for h in ERROR_HINTS.get(theme, [])):
            errors.append((sid, rec["material_id"], rec["rights_status"],
                           desc[:60]))
        else:
            # Primary 可用（按线索词无硬伤）
            tops += 1
    return {"theme": theme, "mode": mode, "shots": n_total,
            "primary": n_primary, "obvious_errors": len(errors),
            "errors": errors, "no_safe": len(ns),
            "reused_primaries": reuses, "usable_primary": tops}


def main():
    rows = []
    for theme in ("busy", "phone", "study", "nightcity", "jarvis"):
        for mode in ("lexical", "embedding", "hybrid"):
            r = analyze(theme, mode)
            if r.get("missing"):
                continue
            rows.append(r)
            print(f"[{r['theme']:9s}/{r['mode']:9s}] 镜 {r['shots']} | Primary {r['primary']} "
                  f"| 明显错误 {r['obvious_errors']} | NO_SAFE {r['no_safe']} "
                  f"| 复用 {r['reused_primaries']} | 可用 {r['usable_primary']}")
    print("\n--- 错误明细（hybrid 模式）---")
    for r in rows:
        if r["mode"] == "hybrid" and r["errors"]:
            for sid, mid, rights, desc in r["errors"]:
                print(f"  {r['theme']} {sid} {mid} [{rights}] {desc}")
    out = ROOT / "output" / "stage31_testpkgs" / "benchmark_summary.json"
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n已写 {out}")


if __name__ == "__main__":
    main()
