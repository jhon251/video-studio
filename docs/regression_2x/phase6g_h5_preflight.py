# -*- coding: utf-8 -*-
"""6-G / H5 —— **只读 preflight（素材验收）**：文件/SHA/可解码/字段/许可/绑定/语义门禁。

**不执行替换**、不联网、不自动选择候选、不改任何既有文件（仅新增本产物）。
语义门禁依据：H5 proposal `rp-0ebebb71f99c` 冻结语义要求（逐字引用，不做放宽）。

产出: docs/regression_2x/logs/phase6g_h5_preflight.json
"""
import hashlib
import json
import pathlib
import subprocess
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from PIL import Image                                                     # noqa: E402

L = R / "docs" / "regression_2x" / "logs"
CAND = pathlib.Path(r"C:\mp4agent\h5_asset_candidates")
OUT = L / "phase6g_h5_preflight.json"
FP = str(R / "bin" / "ffprobe.exe")
PKG = json.loads((L / "phase6g_rebuild_proposals.json").read_text(encoding="utf-8"))
H5 = next(p for p in PKG["proposals"] if p["label"].startswith("H5"))
REQ = ["asset_id", "path", "sha256", "license", "license_class", "source_url", "attribution"]
PASS, FAIL = [], []


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def ck(name, ok, detail=None):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name,
                             "" if ok else json.dumps(detail, ensure_ascii=False,
                                                      default=str)[:230]))
    return bool(ok)


SNAP = {"db": sha(R / "projects/video_studio.db"),
        "baseline": sorted(p.name for p in (R / "docs/regression_2x/baseline").glob("*")),
        "material_plan": sha(R / "docs/regression_2x/phase6e_materials/"
                             "phase6e_material_plan.json"),
        "ledger": sha(L / "phase6g_exec_ledger.jsonl"),
        "register": sha(L / "phase6g_rebuild_proposal_register.jsonl")}

# ---------------------------------------------------------------- 人工指定的两个候选
SPEC = {
    "S05": {"file": CAND / "S05" / "Russell_PM_1+1=2.png",
            "sha256": "65377b888b7782260c1cf3717a5eb9681b21e27d4d75473a95506bc397b9a6ff",
            "source_url": "https://commons.wikimedia.org/wiki/File:Russell_PM_1%2B1%3D2.png",
            "license_class": "PUBLIC_DOMAIN", "license": None,
            "attribution": "Whitehead & Russell, Principia Mathematica Vol. II (1912), p.86 — "
                           "via Wikimedia Commons",
            "semantic_verdict": "PASS",
            "semantic_evidence": "画面为 Principia Mathematica 原书页：`*110·643. ⊢ . 1 +c 1 = 2`、"
                                 "`Dem.`、逐步推导行（`⊢ . *110·632 . *101·21·28 . ⊃` 等）"
                                 "及注记『The above proposition is occasionally useful …』"
                                 "⇒ 属冻结要求①『论文/期刊版面（可读）』，直接服务于"
                                 "『引文/表述可被逐字检视（surveyability）』"},
    "S11": {"file": CAND / "S11" / "code-success.png",
            "sha256": "bdb50e986bc7fb982d1360157b31a2fbeb898c01fa3f16e22768fd64ce944b6a",
            "source_url": "https://github.com/leanprover/lean4/blob/master/doc/images/"
                          "code-success.png",
            "license_class": "APACHE_2.0", "license": "Apache-2.0",
            "attribution": "Copyright the Lean authors, Apache License 2.0",
            "semantic_verdict": "FAIL",
            "semantic_evidence": "画面为 Lean 编辑器（标签 `#eval Lean.versionString` / 第 1 行 "
                                 "`#eval Lean.versionString`）+ `Lean Infoview` 面板，其内容为 "
                                 "`Messages (1)` → `\"4.0.0\"`。**无定理/策略关键字**"
                                 "（无 `theorem`/`lemma`/`:= by`/`rw`/`simp`/`exact` 等），"
                                 "InfoView 展示的是 **Messages** 而非 **proof state / goals**，"
                                 "亦无依赖图/验证流程 ⇒ 不满足冻结要求①/②/③"},
}

scenes = {}
for scene, s in SPEC.items():
    p = s["file"]
    row = {"expected": {"sha256": s["sha256"], "source_url": s["source_url"],
                        "license": s["license"], "license_class": s["license_class"],
                        "attribution": s["attribution"]},
           "path": str(p), "exists": p.is_file()}
    if row["exists"]:
        b = p.read_bytes()
        row["bytes"] = len(b)
        row["sha256_actual"] = hashlib.sha256(b).hexdigest()
        row["sha256_match"] = row["sha256_actual"] == s["sha256"]
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
        row["decodable"] = bool(row.get("pil_ok")
                                and any(x["codec_type"] == "video" for x in row["ffprobe"]))
    rec = {"asset_id": None, "path": str(p), "sha256": s["sha256"], "license": s["license"],
           "license_class": s["license_class"], "source_url": s["source_url"],
           "attribution": s["attribution"]}
    row["license_record"] = rec
    row["missing_required_fields"] = [k for k in REQ if rec.get(k) in (None, "", [], {})]
    row["license_restricted"] = False
    row["license_restricted_source"] = "**人工声明**（本次指令）；工具侧无许可数据库可程序化复核"
    row["semantic_verdict"] = s["semantic_verdict"]
    row["semantic_evidence"] = s["semantic_evidence"]
    row["semantic_gate_basis"] = H5["proposed_change"]["params"]["new_assets_needed"][
        "per_scene"][scene]["semantic_spec"]
    scenes[scene] = row

# ---------------------------------------------------------------- 候选清单（仅事实盘点，不选择）
inventory = []
for d, scene in ((CAND / "S05", "S05"), (CAND / "S11", "S11")):
    for f in sorted(d.rglob("*")):
        if f.is_file():
            try:
                with Image.open(f) as im:
                    dim = list(im.size)
            except Exception:                                            # noqa: BLE001
                dim = None
            inventory.append({"scene": scene, "file": str(f), "bytes": f.stat().st_size,
                              "sha256": sha(f), "size": dim,
                              "selected_by_human": f.name in (SPEC[scene]["file"].name,)})

# ---------------------------------------------------------------- H5P 项目
print("== H5P 检查 ==")
ck("H5P-1 人工指定的两个候选文件真实存在",
   all(scenes[s]["exists"] for s in ("S05", "S11")),
   {s: scenes[s]["exists"] for s in ("S05", "S11")})
ck("H5P-2 SHA256 与人工声明**完全一致**（逐字节核验）",
   all(scenes[s].get("sha256_match") for s in ("S05", "S11")),
   {s: {"expected": scenes[s]["expected"]["sha256"],
        "actual": scenes[s].get("sha256_actual")} for s in ("S05", "S11")})
ck("H5P-3 两个文件均可解码为**真实图像**（PNG + PIL 打开成功）",
   all(scenes[s].get("decodable") for s in ("S05", "S11")),
   {s: {"pil": scenes[s].get("pil"), "ffprobe": scenes[s].get("ffprobe")}
    for s in ("S05", "S11")})
ck("H5P-4 素材记录满足 H5 要求的 7 字段（{}）".format(" / ".join(REQ)),
   all(not scenes[s]["missing_required_fields"] for s in ("S05", "S11")),
   {s: scenes[s]["missing_required_fields"] for s in ("S05", "S11")})
ck("H5P-5 license_restricted == false", all(not scenes[s]["license_restricted"]
                                            for s in ("S05", "S11")),
   {s: scenes[s]["license_restricted_source"] for s in ("S05", "S11")})
ck("H5P-6 人工绑定可写成 {S05: asset_id_S05, S11: asset_id_S11}（形式可行）",
   True, {"binding_form": "{S05: asset_id_S05, S11: asset_id_S11}",
          "note": "asset_id 尚未提供（见 H5P-4）"})
ck("H5P-7 未使用被禁止素材 asset_432cd85be6f1（IMO 合影）",
   all("asset_432cd85be6f1" not in json.dumps(scenes[s]["license_record"], ensure_ascii=False)
       for s in ("S05", "S11")))
ck("H5P-8 S05 语义门禁（冻结要求：与『可逐字检视』直接相关）",
   scenes["S05"]["semantic_verdict"] == "PASS", scenes["S05"]["semantic_evidence"])
ck("H5P-9 S11 语义门禁（冻结要求：①含可辨识定理/策略关键字 ②proof state/goal 面板 ③依赖图/验证流程）",
   scenes["S11"]["semantic_verdict"] == "PASS", scenes["S11"]["semantic_evidence"])
ck("H5P-10 未自动选择其它候选（仅事实盘点）",
   all(not x["selected_by_human"] or x["file"] in [str(SPEC["S05"]["file"]),
                                                   str(SPEC["S11"]["file"])]
       for x in inventory), {"inventory_n": len(inventory)})
ck("H5P-11 未联网、未执行替换、未修改任何既有文件（快照一致）", True)

SNAP2 = {"db": sha(R / "projects/video_studio.db"),
         "baseline": sorted(p.name for p in (R / "docs/regression_2x/baseline").glob("*")),
         "material_plan": sha(R / "docs/regression_2x/phase6e_materials/"
                              "phase6e_material_plan.json"),
         "ledger": sha(L / "phase6g_exec_ledger.jsonl"),
         "register": sha(L / "phase6g_rebuild_proposal_register.jsonl")}
ck("H5P-12 只读证明：DB / baseline / 冻结材料 / 链 均未变", SNAP == SNAP2,
   {k: SNAP[k] == SNAP2[k] for k in SNAP})

ready = (not FAIL)
out = {"schema": "phase6g-h5-preflight-v2", "stage": "6-G / H5（素材验收 + preflight）",
       "verdict": "H5_PREFLIGHT_READY" if ready else "H5_BLOCKED",
       "proposal": {"label": H5["label"], "proposal_id": H5["proposal_id"],
                    "action": H5["action"], "scenes": H5["affected_scope"]["scenes"]},
       "checks": {"pass": PASS, "fail": FAIL, "ready": ready},
       "scenes": scenes,
       "candidate_inventory_only_no_selection": inventory,
       "s11_semantic_detail": {
           "selected_by_human": "code-success.png",
           "verdict": "FAIL",
           "why": scenes["S11"]["semantic_evidence"],
           "other_candidates_factual": [
               {"file": "code-ext.png (369×280)",
                "content": "VS Code **扩展市场**页面：搜索『Lean 4』+ Install 按钮；"
                           "无任何定理/策略/证明内容 ⇒ 同样不满足 ①②③"},
               {"file": "widgets_caas.png (1234×102)",
                "content": "`▼ #check as a service` 与**类型签名** "
                           "`getType : GetTypeParams → Server.RequestM (Server.RequestTask "
                           "CodeWithInfos)` ⇒ 属 Lean 服务器 API 文档化的**类型签名**；"
                           "是三者中最接近形式内容者，但仍**不含定理/策略关键字**、非 proof state/goal、"
                           "非依赖图 ⇒ 按**冻结原文**仍不明确满足 ①②③；"
                           "是否合格属**门禁解释**（需人工明确裁定，我不会自行放宽）"}],
           "logo_note": "候选中的 `Lean_logo2.svg` / `Lean_logo2_800px.png` 为 Lean **商标/logo**；"
                        "6-E 冻结设计对该类图形有 `must_not`（『使用 Lean/mathlib 的 logo 或商标图形』）"
                        "—— 供人工决策参考（不构成我对 H5 素材要求的改写）"},
       "blocked_reasons": [
           "H5P-4：字段不齐 —— **S05 缺 `license`（仅给了 license_class）与两者都缺 `asset_id`**",
           "H5P-9：**S11 选定素材不满足冻结语义门禁**（无定理/策略关键字；InfoView 为 Messages "
           "而非 proof-state/goal）"],
       "required_from_human": [
           "① S11：另选/另供**满足冻结语义**的真实素材（例如含 `theorem … := by` 语句与策略的"
           " Lean 4 截图，或 **proof state / goals** 面板，或形式化依赖图/验证流程），并给出 sha256；"
           "**或**明确裁定 `widgets_caas.png`（类型签名）是否算满足 ①②③ —— 这属门禁解释，"
           "需人工显式授权（我不会自行放宽）",
           "② S05：给出 `license` 字符串（例如 Commons 上的 PD 模板名）并确认 PD 依据 —— "
           "**风险提示（事实）**：Whitehead 卒于 1947、Russell 卒于 1970，本书 1912 年出版 ⇒ "
           "在美国属 pre-1929 公有领域，但在『作者身后 70 年』法域可能尚未进入公有领域；"
           "`license_class=PUBLIC_DOMAIN` 的具体适用法域需人工确认",
           "③ 两个素材的 `asset_id`（或授权我按 sha256 派生**确定性 id** 并披露为簿记操作）",
           "④ （后续）明确授权执行 H5（本轮不执行）"],
       "invariants": {"read_only": True, "replacement_executed": False, "network_used": False,
                      "auto_selection": False, "converted_lean_text_to_image": False,
                      "frozen_material_modified": False, "policy_or_threshold_changed": False,
                      "panel_kind_changed": False, "dq_criteria_changed": False,
                      "promoted": False, "baseline_or_tag_changed": False,
                      "final_master_designated": False, "history_modified": False,
                      "snapshot_identical": SNAP == SNAP2}}
out["preflight_sha256"] = hashlib.sha256(json.dumps(
    out, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()
).hexdigest()
OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print("\n== H5 素材验收/preflight 结论 ==")
print("  verdict:", out["verdict"], "| checks {} PASS / {} FAIL".format(len(PASS), len(FAIL)))
for s in ("S05", "S11"):
    r = scenes[s]
    print("  {} sha_match={} decodable={} missing={} semantic={}".format(
        s, r.get("sha256_match"), r.get("decodable"), r["missing_required_fields"],
        r["semantic_verdict"]))
print("preflight ->", OUT)
sys.exit(0 if ready else 1)
