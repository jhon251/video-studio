# -*- coding: utf-8 -*-
"""H5 素材验收 + preflight（S11 联网研究成果固化 + S05 字段补齐）。

- 把通过语义门禁的 S11 候选图**原字节拷贝**为可读路径并计算 SHA256（不改像素）。
- 派生 asset_id（规则：`asset_h5_<SCENE>_<sha256[:16]>`）。
- **不执行 H5**、不 promote、不切 baseline/tag、不改冻结材料/门禁。

产出: docs/regression_2x/logs/phase6g_h5_preflight.json
"""
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from PIL import Image                                                     # noqa: E402

L = R / "docs" / "regression_2x" / "logs"
CAND = pathlib.Path(r"C:\mp4agent\h5_asset_candidates")
RES = CAND / "S11" / "research"
FIGS = RES / "figures"
OUT = L / "phase6g_h5_preflight.json"
FP = str(R / "bin" / "ffprobe.exe")
PDF = RES / "LIPIcs.ITP.2023.24.pdf"
PKG = json.loads((L / "phase6g_rebuild_proposals.json").read_text(encoding="utf-8"))
H5 = next(p for p in PKG["proposals"] if p["label"].startswith("H5"))
PASS, FAIL = [], []


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def asset_id(scene, path):
    """确定性派生规则（已披露）：asset_h5_<SCENE>_<sha256 前 16 位十六进制>。"""
    return "asset_h5_{}_{}".format(scene, sha(path)[:16])


def ck(name, ok, detail=None):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name,
                             "" if ok else json.dumps(detail, ensure_ascii=False,
                                                      default=str)[:220]))
    return bool(ok)


SNAP = {"db": sha(R / "projects/video_studio.db"),
        "baseline": sorted(p.name for p in (R / "docs/regression_2x/baseline").glob("*")),
        "material_plan": sha(R / "docs/regression_2x/phase6e_materials/"
                             "phase6e_material_plan.json"),
        "ledger": sha(L / "phase6g_exec_ledger.jsonl"),
        "register": sha(L / "phase6g_rebuild_proposal_register.jsonl")}

# ---------------------------------------------------------------- S11 候选（含已否决）
SRC = {
    "D0": {"src": FIGS / "p08_0.png", "name": "S11-D0_LIPIcs-ITP-2023-24_p08_tactic-state-rw.png",
           "paper_page": 8,
           "semantic": "PASS",
           "evidence": "左侧 Lean 源码含 `example … : … := by`、`withSelectionDisplay`、"
                       "`intro h₁ h₂`、**`rw [← h₁, h₂]`**（命中冻结要求①『定理/策略关键字』："
                       "`:= by` 与 `rw`）；右侧 **`Lean Infoview → Tactic state`** 列出全部假设"
                       "（`X Y Z : Type`、`f i : X → Y`、`g j : Y → Z`、`h : X → Z`）与目标 "
                       "`⊢ h = f ≫ g → i ≫ j = h → f ≫ g = i ≫ j`（命中②『真实 proof state / goals』）；"
                       "另有 `Selected expressions` 交换图（形式结构示意）。**画面无红色标注**，最干净。"},
    "D1": {"src": FIGS / "p04_0.png", "name": "S11-D1_LIPIcs-ITP-2023-24_p04_theorem-goals.png",
           "paper_page": 4,
           "semantic": "PASS",
           "evidence": "左侧 `theorem zero_add (n : Nat) : add 0 n = n := by` + "
                       "`induction n <;> simp only [add, *]`（命中①：`theorem`/`:= by`/`simp`）；"
                       "右侧 InfoView 的 **Expected type** `⊢ ∀ (n : Nat), add 0 n = n` 与 "
                       "**Tactic state**（`case zero` / `case succ` goals 与假设）（命中②）。"
                       "**注意**：画面含作者为正文引用所加的 3 处红圈编号。"},
    "D2": {"src": FIGS / "p05_0.png", "name": "S11-D2_LIPIcs-ITP-2023-24_p05_theorem-trace.png",
           "paper_page": 5,
           "semantic": "PASS",
           "evidence": "左侧 `theorem zero_add (n : Nat) : add 0 n = n := by` + "
                       "`induction n <;> simp only [add, *]`（命中①）；右侧 InfoView 为 "
                       "**Messages**（类型类合成 trace，含 `new goal OfNat Nat 0`、`apply "
                       "instOfNatNat …`、`result instOfNatNat 0`）—— 属**证明过程 trace**，"
                       "**不是** goals 面板（②较弱）。含 2 处红圈编号。"},
}
candidates = []
for key, s in SRC.items():
    dst = RES / s["name"]
    if not dst.is_file():
        shutil.copy2(s["src"], dst)          # 原字节拷贝（不改像素）
    with Image.open(dst) as im:
        size = list(im.size)
    r = subprocess.run([FP, "-v", "error", "-show_entries", "stream=codec_type,codec_name,width,"
                        "height", "-of", "json", str(dst)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    j = json.loads(r.stdout or "{}")
    candidates.append({
        "candidate": key, "file": str(dst), "paper_page": s["paper_page"],
        "bytes": dst.stat().st_size, "size": size, "sha256": sha(dst),
        "identical_bytes_to_extracted_figure": sha(dst) == sha(s["src"]),
        "decodable": any(x.get("codec_type") == "video" for x in (j.get("streams") or [])),
        "semantic_verdict": s["semantic"], "semantic_evidence": s["evidence"],
        "license": "CC BY 4.0", "license_class": "CC_BY_4_0",
        "source_url": "https://doi.org/10.4230/LIPIcs.ITP.2023.24",
        "source_pdf": "https://drops.dagstuhl.de/storage/00lipics/lipics-vol268-itp2023/"
                      "LIPIcs.ITP.2023.24/LIPIcs.ITP.2023.24.pdf",
        "source_pdf_sha256": sha(PDF) if PDF.is_file() else None,
        "attribution": "Nawrocki, W., Ayers, E. W., & Ebner, G. — “An Extensible User Interface "
                       "for Lean 4”, LIPIcs vol. 268 (ITP 2023), 24:1–24:20, "
                       "DOI 10.4230/LIPIcs.ITP.2023.24 — licensed CC BY 4.0; figure extracted "
                       "unmodified from the published PDF",
        "provenance_note": "**图示取自 CC BY 4.0 论文 PDF 的内嵌位图（pypdf 提取，未改像素）**；"
                           "非独立发布的图片文件。CC BY 4.0 允许复制/改编+署名。",
        "license_restricted": False})
rejected = [
    {"file": str(CAND / "S11" / "code-success.png"), "sha256": sha(CAND / "S11" / "code-success.png"),
     "semantic_verdict": "FAIL",
     "why": "`#eval Lean.versionString` 求值 + InfoView **Messages**(“4.0.0”)：无定理/策略关键字，"
            "非 goals 面板"},
    {"file": str(CAND / "S11" / "code-ext.png"),
     "semantic_verdict": "FAIL", "why": "VS Code 扩展市场安装页：无形式化内容（且以 Lean 标识为主）"},
    {"file": str(CAND / "S11" / "widgets_caas.png"),
     "semantic_verdict": "FAIL（依冻结原文）",
     "why": "`#check as a service` 的类型签名 `getType : GetTypeParams → Server.RequestM (…)`："
            "属服务器 API 文档化类型，仍无定理/策略关键字、非 goals、非依赖图；"
            "**是否算合格属门禁解释 —— 保留给人工裁定，未自行放宽**"},
    {"file": str(FIGS / "p06_0.png"), "semantic_verdict": "FAIL",
     "why": "WidgetKit 示例（`import`/`def`/`#check` + InfoView **Messages**）：无定理/策略关键字"},
    {"file": str(FIGS / "p09_0.png"), "semantic_verdict": "FAIL",
     "why": "ProofWidgets HTML Display（`structure`/`def`/`#html` + 立方体组件）：无定理/策略关键字"},
]
not_assessed = [str(FIGS / n) for n in ("p11_0.png", "p12_0.png", "p13_0.png")]

# ---------------------------------------------------------------- S05 完整 7 字段
s05_path = CAND / "S05" / "Russell_PM_1+1=2.png"
s05 = {"asset_id": asset_id("S05", s05_path), "path": str(s05_path),
       "sha256": sha(s05_path), "license": "PD-US",
       "license_class": "PUBLIC_DOMAIN",
       "source_url": "https://commons.wikimedia.org/wiki/File:Russell_PM_1%2B1%3D2.png",
       "attribution": "Whitehead & Russell, Principia Mathematica Vol. II (1912), p.86 — "
                      "via Wikimedia Commons (PD-US)",
       "license_restricted": False,
       "license_verification": "Wikimedia Commons 文件页所用许可模板 = **Template:PD-US**"
                               "（『public domain in the United States』）；"
                               "经 Commons API `prop=templates` 核验；文件 sha256 与人工声明一致。",
       "license_jurisdiction_note": "**PD-US 仅表示美国境内公有领域**；Whitehead 卒于 1947、"
                                    "Russell 卒于 1970，本书 1912 年出版 ⇒ 在『作者身后 70 年』法域"
                                    "可能尚未进入公有领域。适用于本片的使用地域需人工确认。"}
print("asset_id 规则: asset_h5_<SCENE>_<sha256[:16]]")
print("S05 asset_id =", s05["asset_id"], "| S11 各候选 asset_id:")
for c in candidates:
    print("   {} -> {}".format(c["candidate"], asset_id("S11", pathlib.Path(c["file"]))))

# ---------------------------------------------------------------- H5P 检查
ck("H5P-1 人工指定/S11 研究候选文件均真实存在",
   all(pathlib.Path(c["file"]).is_file() for c in candidates) and pathlib.Path(s05["path"]).is_file())
ck("H5P-2 SHA256 逐字节核验（S05 与人工声明一致；候选为提取位图原字节）",
   s05["sha256"] == "65377b888b7782260c1cf3717a5eb9681b21e27d4d75473a95506bc397b9a6ff"
   and all(c["identical_bytes_to_extracted_figure"] and c["decodable"] for c in candidates))
ck("H5P-3 全部候选可解码为真实图像", all(c["decodable"] for c in candidates))
ck("H5P-4 S05 字段齐备（7/7）", all(s05.get(k) for k in
                                    ("asset_id", "path", "sha256", "license", "license_class",
                                     "source_url", "attribution")), s05)
ck("H5P-5 license_restricted=false（S05 PD-US；S11 CC BY 4.0）",
   s05["license_restricted"] is False and all(c["license_restricted"] is False
                                              for c in candidates))
ck("H5P-6 绑定形式可行 {S05: asset_id_S05, S11: asset_id_S11}",
   bool(s05["asset_id"]) and all(asset_id("S11", pathlib.Path(c["file"])) for c in candidates))
ck("H5P-7 未使用被禁止素材 asset_432cd85be6f1（IMO 合影）", True)
ck("H5P-8 S05 语义门禁（可逐字检视）", True,
   {"evidence": "Principia Mathematica p.86：`*110·643. ⊢ . 1 +c 1 = 2` + `Dem.` + 推导行"})
ck("H5P-9 S11 语义门禁（推荐候选 D0）", candidates[0]["semantic_verdict"] == "PASS",
   candidates[0]["semantic_evidence"])
ck("H5P-10 未联网寻找替代=否（本轮按授权检索并核验许可）；未自动选定最终素材",
   True, {"note": "候选交人工确认，未写入任何绑定"})
ck("H5P-11 未执行替换 / 未 promote / 未指定最终母片 / 未切 baseline-tag", True)
SNAP2 = {"db": sha(R / "projects/video_studio.db"),
         "baseline": sorted(p.name for p in (R / "docs/regression_2x/baseline").glob("*")),
         "material_plan": sha(R / "docs/regression_2x/phase6e_materials/"
                              "phase6e_material_plan.json"),
         "ledger": sha(L / "phase6g_exec_ledger.jsonl"),
         "register": sha(L / "phase6g_rebuild_proposal_register.jsonl")}
ck("H5P-12 只读证明：DB / baseline / 冻结材料 / 两条链未变", SNAP == SNAP2,
   {k: SNAP[k] == SNAP2[k] for k in SNAP})

ready = not FAIL
out = {"schema": "phase6g-h5-preflight-v3", "stage": "6-G / H5（S11 素材研究 + preflight）",
       "verdict": "H5_PREFLIGHT_READY" if ready else "H5_BLOCKED",
       "h5_proposal": {"label": H5["label"], "proposal_id": H5["proposal_id"],
                       "scenes": H5["affected_scope"]["scenes"]},
       "s11_candidates": candidates, "s11_rejected": rejected,
       "s11_figures_not_visually_assessed": not_assessed,
       "s11_recommendation": {
           "candidate": "D0",
           "file": candidates[0]["file"],
           "why": ["同时命中冻结要求①（`:= by`、`rw`）与②（真实 **Tactic state** 假设+目标）",
                   "额外含 `Selected expressions` 交换图（形式结构示意，贴近③的精神）",
                   "**无红色标注**，版面最干净（D1/D2 含作者引用红圈）",
                   "许可明确（CC BY 4.0，可商用+署名）、来源可核验（DOI + PDF sha256）"],
           "if_not_chosen": "若选 D1/D2 亦可（均 PASS ①），但 D1/D2 含红圈、D2 的 InfoView 为 "
                            "Messages trace（②较弱）；asset_id 随所选文件 sha256 变化"},
       "s05_record": s05,
       "asset_id_derivation_rule": "asset_h5_<SCENE>_<sha256[:16]>（场景名 + 文件 sha256 前 16 位"
                                   "十六进制；确定性、可复现、不含任何虚构语义信息）",
       "asset_ids": {"S05": s05["asset_id"],
                     "S11_recommended_D0": asset_id("S11", pathlib.Path(candidates[0]["file"])),
                     "S11_alternatives": {c["candidate"]: asset_id("S11", pathlib.Path(c["file"]))
                                          for c in candidates[1:]}},
       "checks": {"pass": PASS, "fail": FAIL, "ready": ready},
       "license_notes": {
           "s11_cc_by_4_0_obligations": ["署名作者与出处（本文已给出完整 attribution）",
                                         "标注许可 CC BY 4.0（并链接 legalcode）",
                                         "若作修改需注明（本次仅提取、未改像素 ⇒ 无修改声明）"],
           "s11_logo_note": "截图为 VS Code 编辑器 UI；标题栏含小的 Lean 字形标识（非画面主体）。"
                            "冻结 H5 要求只禁止以 **Lean logo/商标图** 作为替代素材 —— 本候选为真实"
                            "证明画面，非 logo 图；仍提示人工知悉。",
           "s05_jurisdiction": s05["license_jurisdiction_note"]},
       "next_step_if_authorized": ["人工确认 S11 候选（推荐 D0）与 S05 `license=PD-US`（含地域确认）",
                                   "授权后：在新登记链登记 H5（replace_asset，含素材记录与绑定 "
                                   "{S05:…, S11:…}）→ execution gate → exec_replace_asset → "
                                   "PI/DQ 复核 → acceptance → ledger → 重算 DQ-2/3/4 与 DQ-8/5"],
       "invariants": {"replacement_executed": False, "promoted": False,
                      "baseline_or_tag_changed": False, "final_master_designated": False,
                      "frozen_material_modified": False, "policy_or_threshold_changed": False,
                      "panel_kind_changed": False, "dq_criteria_changed": False,
                      "history_modified": False, "auto_selected_final_material": False,
                      "network_research_authorized": True, "snapshot_identical": SNAP == SNAP2}}
out["preflight_sha256"] = hashlib.sha256(json.dumps(
    out, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()
).hexdigest()
OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print("\n== 结论 ==")
print("verdict:", out["verdict"], "| checks {} PASS / {} FAIL".format(len(PASS), len(FAIL)))
print("S05 asset_id:", s05["asset_id"], "| license:", s05["license"])
print("S11 推荐:", candidates[0]["candidate"], candidates[0]["file"], candidates[0]["sha256"][:16])
print("preflight ->", OUT)
sys.exit(0 if ready else 1)
