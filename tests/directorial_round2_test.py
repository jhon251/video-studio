# -*- coding: utf-8 -*-
"""6-E —— **Evidence-Grounded Directorial Revision Round 2** 冻结真值集回归（只生成/登记，禁止执行）。

覆盖：
  T0 冻结与登记链：真值锚、审片台账 6 条（5 REJECT + 1 ACCEPT）、proposal 5 条、两条哈希链完整；
  T1 审片绑定：每条 proposal 绑定 [人审决策 → candidate → scene/window → 原始 evidence]；
  T2 schema 与局部化：必需字段齐备、`verify_proposal` 通过、≤6 镜 / 占比 ≤0.30；
  T3 禁止素材：E2/E3 显式声明禁止 IMO 合影；`affected_scope.assets` 为空；
  T4 无虚构 asset_id / CLIP 非充分依据；
  T5 信息增量：E4/E5 禁止 punch-in 且 ≥4 个可核对信息槽；E1 字体修复参数；E2/E3 差异化视觉；
  T6 冲突：6-E 内部 0 对；跨批次 4 对**显式声明**（含处理方式）；
  T7 保留记录：aS18 为已验证正向，**未生成**方案；
  T8 DEFER/UNKNOWN 守卫：驱动决策全部可证 REJECT；不可证项调用 make_proposal 必须抛错；
  T9 不执行证明：DB/v9/沙箱产物/C1–C4 均未变；脚本静态无 ffmpeg/subprocess。

用法: python tests/directorial_round2_test.py
"""
import ast
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core import execution as EX            # noqa: E402
from video_studio.core import human_review as HR         # noqa: E402
from video_studio.core import revision as core_revision  # noqa: E402

TRUTH_PATH = ROOT / "tests" / "fixtures" / "directorial_round2_truth_v1.json"
R2 = ROOT / "docs" / "regression_2x" / "logs" / "phase6e_round2.json"
REVIEW = ROOT / "docs" / "regression_2x" / "logs" / "phase6e_review_ledger_r2.jsonl"
REGISTER = ROOT / "docs" / "regression_2x" / "logs" / "phase6e_proposal_register_r2.jsonl"
M6C = ROOT / "docs" / "regression_2x" / "logs" / "phase6c_batch.json"
SCRIPT = ROOT / "docs" / "regression_2x" / "phase6e_round2_proposals.py"
DB = ROOT / "projects" / "video_studio.db"
FILM = ROOT / "projects" / "p_96efdc03e1aa" / "output" / "t_d0a54bdf1810_draft.mp4"
V9_SHA = "22705c7d7ea20b40d91120146066b89ab2b5fa5c1a1cab18f5346d4c66497651"

PASS, FAIL, SKIP = [], [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name, "" if ok else "| " + str(detail)[:340]))


def skip(name, why):
    SKIP.append(name)
    print("SKIP  {} | {}".format(name, why))


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


TRUTH = json.loads(TRUTH_PATH.read_text(encoding="utf-8"))
_canon = json.dumps({k: v for k, v in TRUTH.items() if k != "frozen_sha256"},
                    sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
truth_sha = hashlib.sha256(_canon).hexdigest()

print("== T0 冻结与登记链 ==")
check("T0a schema/阶段正确（directorial-round2-truth-v1 / 6-E）",
      TRUTH.get("schema") == "directorial-round2-truth-v1" and TRUTH.get("stage") == "6-E")
check("T0b 规范化 sha256 与文件内冻结锚点一致", TRUTH.get("frozen_sha256") == truth_sha,
      {"live": truth_sha, "frozen": TRUTH.get("frozen_sha256")})
if not R2.is_file():
    skip("T0c..T9", "缺少 {}（先运行 phase6e_round2_proposals.py）".format(R2.name))
    print("\n结果: {}/{} 通过   SKIP={}".format(len(PASS), len(PASS) + len(FAIL), SKIP))
    sys.exit(1)
d = json.loads(R2.read_text(encoding="utf-8"))
rev = HR.load_ledger(REVIEW)
reg = core_revision.load_register(REGISTER)
props = {p["label"].split("-")[0]: p for p in d["proposals"]}
check("T0c 审片台账 6 条且哈希链完整", len(rev) == 6 and HR.verify_chain(rev)["ok"],
      {"entries": len(rev), "chain": HR.verify_chain(rev)})
check("T0d 审片决策与真值一致（5 REJECT + 1 ACCEPT，逐条 kind/scene/window）",
      [(x["seq"], x["decision"], x["kind"], x["scene_id"], x["window"])
       for x in d["human_review_round2"]]
      == [(x["seq"], x["decision"], x["kind"], x["scene_id"], x["window"])
          for x in TRUTH["review_expect"]])
_v2_entries = [r for r in reg if r.get("version") == 2]
check("T0e proposal 5 条（+1 条 append-only 的 E2 v2 取代版本）且登记哈希链完整",
      len(reg) == 6 and len(_v2_entries) == 1
      and _v2_entries[0].get("supersedes", {}).get("proposal_id") == "rp-f3f8548602fa"
      and core_revision.verify_register_chain(reg)["ok"]
      and d["proposal_count"] == len(TRUTH["proposal_expect"]) == 5,
      {"register": len(reg), "v2": [r["proposal_id"] for r in _v2_entries],
       "chain": core_revision.verify_register_chain(reg)})
check("T0f 登记项 sha 与当前重算一致（方案未被改写）",
      all(EX.proposal_sha256(p) == r.get("proposal_sha256") if "proposal_sha256" in r else True
          for p, r in zip(d["proposals"], reg)))

print("\n== T1 证据链绑定 ==")
for p in d["proposals"]:
    ec = p.get("evidence_chain") or {}
    check("T1 {} 绑定[人审决策→candidate→scene/window→原始证据]".format(p["label"][:2]),
          bool(ec.get("human_review", {}).get("entry_sha256"))
          and bool(ec.get("human_review", {}).get("reason"))
          and bool(ec.get("candidate", {}).get("sha256"))
          and bool(ec.get("candidate", {}).get("label"))
          and bool(ec.get("scene_window", {}).get("scenes"))
          and bool(ec.get("scene_window", {}).get("window"))
          and bool(ec.get("original_evidence")),
          {"keys": sorted(ec)})
    cand = (ROOT / (ec.get("candidate", {}).get("film") or "x"))
    check("T1 {} 绑定的 candidate 成片存在且 sha256 与记录一致".format(p["label"][:2]),
          cand.is_file() and sha(cand) == ec["candidate"]["sha256"])
check("T1 每条证链都记录了 narration（旁白原文）作为原始证据",
      all(p["evidence_chain"]["scene_window"].get("narration") for p in d["proposals"]))

print("\n== T2 schema 与局部化 ==")
for p in d["proposals"]:
    check("T2 {} verify_proposal 通过（必需字段 + executed=False + decision_ref=REJECT）".format(
        p["label"][:2]), core_revision.verify_proposal(p) == [],
        core_revision.verify_proposal(p))
    sc = p["affected_scope"]
    check("T2 {} 局部化：≤6 镜且占比 ≤0.30".format(p["label"][:2]),
          len(sc["scenes"]) <= core_revision.DEFAULT_POLICY["max_scenes_per_proposal"]
          and sc["share_of_film"] <= core_revision.DEFAULT_POLICY["max_share_of_film_per_proposal"],
          {"scenes": len(sc["scenes"]), "share": sc["share_of_film"]})
    exp = next(x for x in TRUTH["proposal_expect"] if x["label_prefix"] == p["label"][:2])
    check("T2 {} action/scenes/window/share 与真值一致".format(p["label"][:2]),
          p["action"] == exp["action"] and sc["scenes"] == exp["scenes"]
          and sc["window"] == exp["window"] and sc["share_of_film"] == exp["share_of_film"],
          {"action": p["action"], "scenes": sc["scenes"], "window": sc["window"]})
check("T2 所有方案均为 PROPOSED_AWAITING_HUMAN_APPROVAL 且 approved/executed 为 false",
      all(p["status"] == "PROPOSED_AWAITING_HUMAN_APPROVAL" and p["approved"] is False
          and p["executed"] is False for p in d["proposals"]))

print("\n== T3/T4 禁止素材 · 无虚构 id · CLIP 非充分 ==")
imo = TRUTH["forbidden_material"]["asset_id"]
for key in ("E2", "E3"):
    p = props[key]
    forb = p["material_requirement"]["forbidden_material"]
    check("T3 {} 显式声明禁止 IMO 合影（{}）".format(key, imo),
          any(f.get("asset_id") == imo for f in forb)
          and any(f.get("asset_id") == imo
                  for f in (p["proposed_change"]["params"].get("forbidden_material") or [])), forb)
    check("T3 {} semantic_spec 中明确『不得使用 IMO/竞赛合影』".format(key),
          "不得" in p["proposed_change"]["params"]["semantic_spec"])
check("T3 所有方案 affected_scope.assets 为空（不把素材 id 写进范围）",
      all(p["affected_scope"]["assets"] == [] for p in d["proposals"]))
check("T4 无虚构 asset_id：material_requirement.asset_id 全为 None",
      all(p["material_requirement"]["asset_id"] is None for p in d["proposals"]))
check("T4 E2/E3 只声明 semantic_spec + sourcing（不写 id）",
      all(props[k]["proposed_change"]["params"].get("semantic_spec")
          and props[k]["proposed_change"]["params"].get("sourcing")
          and props[k]["material_requirement"]["no_fabricated_asset_id"] for k in ("E2", "E3")))
check("T4 每条方案都记录 clip_similarity_sufficient=false 且给出 why_not_clip",
      all(p["evidence_chain"]["clip_similarity_sufficient"] is False
          and len(p["evidence_chain"]["why_not_clip"]) > 10 for p in d["proposals"]))
check("T4 依据中不出现『仅因 CLIP 提升』式表述（basis 含具体缺陷/叙事证据）",
      all("CLIP" not in (p["expected_effect"].get("basis") or "")
          for p in d["proposals"]))

print("\n== T5 信息增量 ==")
for key in ("E4", "E5"):
    p = props[key]
    prm = p["proposed_change"]["params"]
    check("T5 {} 显式禁止仅 punch-in 且给出 ≥4 个可核对信息槽".format(key),
          prm.get("punch_in_only_forbidden") is True and prm.get("self_created") is True
          and len(prm.get("content_slots") or []) >= 4
          and prm.get("each_number_must_cite_source") is True
          and prm.get("no_unverified_numbers") is True, prm.get("content_slots"))
    check("T5 {} 不允许未核实数字（no_unverified_numbers）".format(key),
          prm.get("no_unverified_numbers") is True)
    check("T5 {} information_gain.punch_in_only_forbidden_and_avoided=True".format(key),
          p["information_gain"]["punch_in_only_forbidden_and_avoided"] is True)
check("T5 E1 字体修复参数齐备（font_file + fontsdir + 复用字幕字体 + 时长不变）",
      props["E1"]["proposed_change"]["params"]["font_file"] == "msyh.ttc"
      and props["E1"]["proposed_change"]["params"]["fontsdir"] == "C:/Windows/Fonts"
      and props["E1"]["proposed_change"]["params"]["reuse_subtitle_font"] is True
      and props["E1"]["proposed_change"]["params"]["keep_total_duration"] is True)
check("T5 E2/E3 要求与旁白论点直接对应（semantic_spec 含叙事关键词）",
      "可检视" in props["E2"]["proposed_change"]["params"]["semantic_spec"]
      and all(k in props["E3"]["proposed_change"]["params"]["semantic_spec"]
              for k in ("Lean", "mathlib")))

print("\n== T6 冲突与跨批次重叠 ==")
check("T6 6-E 内部冲突 0 对", d["conflict_matrix_6e"]["conflict_pair_count"] == 0
      == TRUTH["conflict_expect"]["internal_conflict_pairs"],
      d["conflict_matrix_6e"]["pairs"])
got_cross = sorted([c["new"].split("-")[0], c["executed"], tuple(c["kinds"])]
                   for c in d["cross_batch_overlaps"])
exp_cross = sorted([x[0], x[1], tuple(x[2])] for x in TRUTH["conflict_expect"]["cross_batch_overlaps"])
check("T6 跨批次重叠 4 对且与真值一致（显式声明，不静默）", got_cross == exp_cross,
      {"expect": exp_cross, "got": got_cross})
check("T6 每条跨批次重叠都记录了处理方式（需人工批准时确认）",
      all("需人工" in c["note"] for c in d["cross_batch_overlaps"]))

print("\n== T7 保留记录（aS18）==")
ret = d["retention_records"][0]
check("T7 aS18 保留记录 schema/kind/scene 正确且**未生成方案**",
      ret["schema"] == TRUTH["retention_expect"]["schema"]
      and ret["kind"] == TRUTH["retention_expect"]["kind"]
      and ret["scene_id"] == TRUTH["retention_expect"]["scene_id"]
      and ret["no_proposal_generated"] is True)
check("T7 保留依据为人审 ACCEPT（决策不可证=false）",
      ret["human_review"]["decision"] == TRUTH["retention_expect"]["decision"])
check("T7 没有任何 proposal 以 S18/1245–1330 为目标（不重复生成无必要方案）",
      all("S18" not in p["affected_scope"]["scenes"] for p in d["proposals"]))

print("\n== T8 DEFER/UNKNOWN 守卫 ==")
check("T8 驱动决策全部为**可证**（unprovable=False）的人工 REJECT",
      all(x["decision"] == "REJECT" and x["unprovable"] is False
          for x in d["human_review_round2"] if x["decision"] == "REJECT")
      and all(x["unprovable"] is False for x in d["human_review_round2"]))
try:
    bad_item = HR.human_audit_item("p_x", "unprovable_kind", "s", "prov", unprovable=True)
    bad_dec = HR.make_decision(bad_item, "REJECT", "r", "human:t", "p")
    core_revision.make_proposal(bad_item, bad_dec, "replace_asset", {"scene_id": "S05"},
                                {"what": "w", "how": "h", "params": {}},
                                {"scenes": ["S05"], "window": [0.0, 1.0], "share_of_film": 0.1},
                                {"metric": "DQ-8", "basis": "b", "assumption": "a"})
    check("T8 不可证（UNKNOWN/DEFER 类）项**禁止**生成确定性修改", False, "未抛错")
except ValueError as e:
    check("T8 不可证（UNKNOWN/DEFER 类）项**禁止**生成确定性修改（抛 DEFER_MUST_NOT_BECOME_CHANGE）",
          "DEFER_MUST_NOT_BECOME_CHANGE" in str(e), str(e)[:120])

print("\n== T9 不执行证明 ==")
ig = d["integrity"]
check("T9 未执行任何东西：executed_anything=False 且 ffmpeg_invocations=0",
      ig["executed_anything"] is False and ig["ffmpeg_invocations"] == 0)
check("T9 v9 母版未变（且等于 M1 记录值）", ig["v9_unchanged"] and sha(FILM) == V9_SHA)
check("T9 DB 未变", ig["db_unchanged"])
check("T9 沙箱产物目录未变（无新成片、无修改）", ig["sandbox_output_unchanged"],
      ig["sandbox_output_files"])
check("T9 C1–C4 候选成片 sha256 与 6-C 记录一致（未修改）",
      ig["c1_c4_sha_unchanged"]
      and all(sha(ROOT / c["film"]) == c["film_sha256"]
              for c in json.loads(M6C.read_text(encoding="utf-8"))["candidates"]))
src = SCRIPT.read_text(encoding="utf-8")
tree = ast.parse(src)
_imports = sorted({(n.module or "").split(".")[-1] for n in ast.walk(tree)
                   if isinstance(n, ast.ImportFrom)} | {a.name.split(".")[-1] for n in ast.walk(tree)
                                                         if isinstance(n, ast.Import)
                                                         for a in n.names})
check("T9 静态：6-E 脚本不 import subprocess/os.system（不做进程调用）",
      not ({"subprocess", "os"} & set(_imports)), _imports)
_bad_call_lits = []
for n in ast.walk(tree):
    if isinstance(n, ast.Call):
        for a in list(n.args) + [k.value for k in n.keywords]:
            if isinstance(a, ast.Constant) and isinstance(a.value, str) \
                    and ("ffmpeg.exe" in a.value or a.value.strip().endswith(".mp4")):
                _bad_call_lits.append(a.value[:40])
check("T9 静态：6-E 脚本无任何 ffmpeg 可执行路径 / .mp4 写目标（不做渲染、不产成片）",
      _bad_call_lits == [], _bad_call_lits)
check("T9 静态：脚本以显式声明『未执行』（positive claim 而非沉默）",
      "未执行" in src or "禁止执行" in src)
check("T9 静态：脚本声明的产物只有台账/登记/证据 JSON",
      all(x in src for x in ("phase6e_review_ledger_r2.jsonl",
                             "phase6e_proposal_register_r2.jsonl", "phase6e_round2.json")))

print("\n结果: {}/{} 通过   SKIP={}".format(len(PASS), len(PASS) + len(FAIL), SKIP))
if FAIL:
    print("失败项:", FAIL)
sys.exit(1 if FAIL else 0)
