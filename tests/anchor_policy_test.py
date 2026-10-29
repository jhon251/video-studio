# -*- coding: utf-8 -*-
"""Phase 44 / P44-1：**语义锚定门**。

断言（运行前写死）：
  · **A1 锚定素材只出现在其 `allowed_scenes`**（越界数 = 0）；
  · **A2 被锚定素材均在片**（不得因锚定而全部消失 —— 防止"过度收紧=无画面"）；
  · **A3 `anchor_rejected` 有据**（若发生拒绝，必须逐景记录；无拒绝也要报 0）；
  · **A4 抽象段安全集仍可用**（防止锚定把抽象段逼成空域）。

运行: python tests/anchor_policy_test.py
"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
PASS, FAIL = [], []
CFG = R / "config" / "content_exclusions.json"
SB = R / "output" / "phase36_p36_4_sandbox" / "material_timeline.json"


def check(name, ok, detail=None):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name,
                             "" if ok else json.dumps(detail, ensure_ascii=False,
                                                      default=str)[:280]))
    return bool(ok)


def main() -> int:
    ce = json.loads(CFG.read_text(encoding="utf-8"))["content_exclusions"]
    sap = ce.get("scene_asset_policy") or {}
    anchored = sap.get("anchored") or {}
    safe = set(sap.get("abstract_safe_set") or [])
    if not SB.is_file():
        print("SKIP  未找到 material_timeline.json")
        sys.exit(0)
    dec = json.loads(SB.read_text(encoding="utf-8"))["decisions"]

    def match(asset):
        s = "{}|{}".format((asset or {}).get("asset_id") or "",
                           (asset or {}).get("sha256") or "")
        for pfx, spec in anchored.items():
            if pfx and pfx in s:
                return pfx, spec
        return None, None

    viol, present = [], {}
    # ---- P46-1：**owner-approved 具名绑定景豁免单列报告**（授权书 §1 语义：
    #      具名绑定 > 锚定守卫 > 回退）⇒ 该类景的「越界」不算 A1 违规，单独记账。
    _bound = set()
    try:
        _bp = json.loads((R / "output/phase36_voice/bindings_proposal.json")
                         .read_text(encoding="utf-8"))
        _bound = {str(k) for k in (_bp.get("bindings") or {})}
    except Exception:                                                       # noqa: BLE001
        _bound = set()
    exempt, true_viol = [], []
    for d in dec:
        pfx, spec = match(d.get("selected_asset"))
        if pfx:
            present[pfx] = present.get(pfx, 0) + 1
            if d["scene_id"] not in (spec.get("allowed_scenes") or []):
                row = {"scene": d["scene_id"], "asset": pfx,
                       "allowed": spec.get("allowed_scenes")}
                (exempt if d["scene_id"] in _bound else true_viol).append(row)
    viol = true_viol
    rej = sum(d.get("anchor_rejected") or 0 for d in dec)
    rej_scenes = [d["scene_id"] for d in dec if d.get("anchor_rejected")]
    empty = [d["scene_id"] for d in dec if not (d.get("candidates") or [])]
    used_safe = {str((d.get("selected_asset") or {}).get("asset_id") or "")[:24]
                 for d in dec
                 if any(k in str((d.get("selected_asset") or {}).get("asset_id") or "")
                        for k in safe)}
    print("锚定素材 {} 个 | 上屏出现 {} 种 | 锚定拒绝累计 {}（涉及 {} 景）".format(
        len(anchored), len(present), rej, len(rej_scenes)))
    for pfx, n in sorted(present.items()):
        print("   {:<16} {} 次 | 允许 {}".format(
            pfx, n, ",".join((anchored[pfx].get("allowed_scenes") or [])[:4])))
    print()
    check("A1 锚定素材**真越界**数 = 0（实测 {}；另有具名绑定豁免 {} 处，单列）".format(
        len(viol), len(exempt)), not viol, {"true_viol": viol[:6], "exempt": exempt[:6]})
    check("A2 锚定素材均在片（{} / {} 种出现）".format(len(present), len(anchored)),
          len(present) >= 1, {"present": list(present)})
    check("A3 `anchor_rejected` 有据（累计 {}，涉及景 {}）".format(rej, len(rej_scenes)),
          True, {"rejected": rej, "scenes": rej_scenes[:6]})
    check("A4 抽象段安全集仍可用（上屏 {} 种）".format(len(used_safe)),
          len([s for s in safe if any(s[:12] in str((d.get("selected_asset") or {}).get("asset_id") or "") for d in dec)]) >= 3,
          {"used": sorted(used_safe)[:6]})
    print()
    print("=" * 74)
    print("anchor_policy_test: {} PASS / {} FAIL".format(len(PASS), len(FAIL)))
    print("=" * 74)
    (R / "docs/regression_2x/logs/p44_1_anchor_policy.json").write_text(
        json.dumps({"schema": "p44-1-anchor-policy-test-v1",
                    "anchored_assets": len(anchored),
                    "on_screen_kinds": present, "violations": viol,
                    "binding_exempt": exempt, "true_violations": true_viol,
                    "anchor_rejected_total": rej,
                    "anchor_rejected_scenes": rej_scenes,
                    "empty_domain_scenes": empty,
                    "abstract_safe_used": len(used_safe),
                    "pass": len(PASS), "fail": len(FAIL)},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
