"""Phase 4-B 测试：离线、只读、三态语义验证器（MATCH / MISMATCH / UNKNOWN）。

验收要求（授权逐字）：
  · S04/S06 必须识别为 `MISMATCH`；
  · S01/S02/S03/S05 不得误报；
  · 无法判断必须是 `UNKNOWN`，不得当作 `MATCH`。

本套件另外自动断言：
  · **确定性**：同一输入两次运行逐字节一致（无随机、无时间戳）；
  · **离线**：在禁止 socket 连接的环境下仍能完成核验（不访问网络）；
  · **只读**：运行前后 DB sha256/行数不变，且只读连接写操作被拒绝；
  · **可解释**：每条判定都带规则 ID、命中关键词/标记与共享词分类（词级桥 vs 字面碎片）；
  · **无数值阈值**：判据只有类别式规则（域交集 / 域不相交 / 同形词义冲突），无可调阈值。

用法：python tests/semantic_check_test.py
"""
import hashlib
import json
import socket
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core.semantics import (classify_bridge,  # noqa: E402
                                         domain_votes, load_lexicon, resolve_sense,
                                         verify_scene, verify_scenes)
from video_studio.ops.metrics import semantic_report  # noqa: E402
from video_studio.ops.report import readonly_connection  # noqa: E402

DB = ROOT / "projects" / "video_studio.db"
TRUTH_PID = "p_f4b466a4a024"          # 3-A 真实链路项目（已知真值：S04/S06 为语义误选）
# **真值钉在这一版冻结产物上**：3-A 的真值表属于"当时那一版成片"（`a_2ed5f41d6b58`）。
# 4-C 之后项目的最新成片已被人工替换（S04/S06 已修好），因此**不能**用"最新成片"当载体——
# 否则真值会随修复漂移（那等于改真值凑通过）。append-only 保证这一版产物仍在。
TRUTH_ARTIFACT = "a_2ed5f41d6b58"
MUST_MISMATCH = {"S04", "S06"}
MUST_NOT_MISMATCH = {"S01", "S02", "S03", "S05"}
PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(("PASS  " if ok else "FAIL  ") + name + (" | " + str(detail)[:200] if detail else ""))


def db_fp() -> dict:
    con = sqlite3.connect("file:{}?mode=ro".format(DB.as_posix()), uri=True)
    counts = {t: con.execute("select count(*) from {}".format(t)).fetchone()[0]
              for t in ("projects", "tasks", "artifacts", "events")}
    con.close()
    return {"sha256": hashlib.sha256(DB.read_bytes()).hexdigest(),
            "size": DB.stat().st_size, "counts": counts}


LEX = load_lexicon()

# ---------------- A. 词典/原语（可解释性） ----------------
check("A1 词典加载且带版本与 sha256",
      LEX.get("version") == "semantics-v1" and len(LEX.get("sha256") or "") == 64,
      (LEX.get("version"), (LEX.get("sha256") or "")[:12]))
check("A2 同形词本身不计入任何域（避免自相矛盾投票）",
      all("pico" not in v["latin"] and "quest" not in v["latin"]
          for v in LEX["domains_resolved"].values()),
      [k for k, v in LEX["domains_resolved"].items() if "pico" in v["latin"]])
check("A3 域投票可解释（返回命中的关键词）",
      domain_votes("VR headset 头显 佩戴", LEX).get("xr_device", [])[:3] != []
      and "vr" in domain_votes("VR headset", LEX)["xr_device"],
      domain_votes("VR headset 头显", LEX))
check("A4 同形词义解析：pico 在品牌语境 → brand_xr",
      resolve_sense("pico", "PICO 4 官方产品图 VR 头显", LEX)["sense"] == "brand_xr",
      resolve_sense("pico", "PICO 4 官方产品图 VR 头显", LEX))
check("A5 同形词义解析：pico 在地理语境 → place_nature",
      resolve_sense("pico", "canal Fayal-Pico, islas Azores", LEX)["sense"] == "place_nature",
      resolve_sense("pico", "canal Fayal-Pico, islas Azores", LEX))
check("A6 无标记时 sense=None（不猜）",
      resolve_sense("pico", "pico", LEX)["sense"] is None, resolve_sense("pico", "pico", LEX))
_b = classify_bridge("Quest 3 VR 头显 官方图", "Tiburón azul, canal Fayal-Pico, Azores", LEX)
check("A7 桥分类：拉丁 2 字符碎片记为噪声、不算语义支持",
      "es" in _b["fragment_bridge"] and _b["word_bridge"] == [], _b)

# ---------------- B. 单元判定（构造样本） ----------------
_v = verify_scene("X1", "VR 头显 佩戴 方式", "Someone wearing a VR headset.jpg", LEX)
check("B1 域支持 → MATCH", _v["verdict"] == "MATCH" and _v["rule"] == "R4_DOMAIN_SUPPORT",
      (_v["verdict"], _v["rule"]))
_v = verify_scene("X2", "VR 头显 佩戴 方式", "Blue shark in the Azores islands.jpg", LEX)
check("B2 域不相交且无词级桥 → MISMATCH",
      _v["verdict"] == "MISMATCH" and _v["rule"] == "R3_DOMAIN_DISJOINT", (_v["verdict"], _v["rule"]))
_v = verify_scene("X3", "PICO 4 官方产品图", "Tiburón azul, canal Fayal-Pico, islas Azores.jpg", LEX)
check("B3 同形词义冲突 → MISMATCH",
      _v["verdict"] == "MISMATCH" and _v["rule"] == "R2_SENSE_CONFLICT", (_v["verdict"], _v["rule"]))
_v = verify_scene("X4", "随便说点什么", "IMG_1234.jpg", LEX)
check("B4 覆盖不足 → UNKNOWN（不得当作 MATCH）",
      _v["verdict"] == "UNKNOWN" and _v["rule"] == "R5_NO_POSITIVE_SUPPORT", (_v["verdict"], _v["rule"]))
_v = verify_scene("X5", "VR 头显", None, LEX)
check("B5 无素材（占位） → UNKNOWN", _v["verdict"] == "UNKNOWN" and _v["rule"] == "R0_NO_ASSET",
      (_v["verdict"], _v["rule"]))
_v = verify_scene("X6", "", "a.jpg", LEX)
check("B6 空输入 → UNKNOWN", _v["verdict"] == "UNKNOWN" and _v["rule"] == "R1_MISSING_INPUT",
      (_v["verdict"], _v["rule"]))
_v = verify_scene("X7", "Quest for the Holy Grail painting", "Meta Quest 3 front View.jpg", LEX)
check("B7 同形词另一实例（'quest'=寻找圣杯 vs 品牌）→ MISMATCH（设计上就该抓）",
      _v["verdict"] == "MISMATCH" and _v["rule"] == "R2_SENSE_CONFLICT",
      (_v["verdict"], _v["rule"], _v["reason"][:70]))
_v = verify_scene("X8", "Night view of the bridge over the river",
                  "Mars surface view from orbit.jpg", LEX)
check("B8 有词级桥但域不相交且无同形冲突 → 保守 UNKNOWN（不误报）",
      _v["verdict"] == "UNKNOWN" and _v["rule"] == "R5_NO_POSITIVE_SUPPORT"
      and "view" in _v["signals"]["word_bridge"] and _v["signals"]["domain_disjoint"],
      (_v["verdict"], _v["rule"], _v["signals"]["word_bridge"],
       sorted(_v["signals"]["query_domains"]), sorted(_v["signals"]["asset_domains"])))
# 已知限制（**不**作为验收条件，只把观察到的行为固定下来）：lexicon v1 未收录 "keyboard" 的
# 同形（电脑键盘 / 乐器键盘），因此这类样本会被域交集误支持为 MATCH。已在报告"未完成项/已知问题"登记。
_v = verify_scene("X9", "Laptop computer keyboard closeup product photo",
                  "Keyboard instrument concert performance.jpg", LEX)
check("B9 已知限制（记录用）：lexicon v1 未收录 keyboard 同形 → 该样本被误支持为 MATCH",
      _v["verdict"] == "MATCH" and _v["rule"] == "R4_DOMAIN_SUPPORT",
      (_v["verdict"], _v["rule"], _v["signals"]["word_bridge"]))

# ---------------- C. 3-A 真值表（授权验收；钉在冻结产物上） ----------------
before = db_fp()
rep = semantic_report(DB, TRUTH_PID, artifact_id=TRUTH_ARTIFACT)
after = db_fp()
by_scene = {s["scene_id"]: s for s in rep["scenes"]}
got_mismatch = {sid for sid, s in by_scene.items() if s["verdict"] == "MISMATCH"}
check("C0 真值表载体为 3-A 冻结产物（钉住，不随 4-C 修复漂移）",
      rep.get("pinned_artifact") == TRUTH_ARTIFACT and len(by_scene) == 6,
      (rep.get("pinned_artifact"), sorted(by_scene)))
check("C1 真值表：S04/S06 全部识别为 MISMATCH",
      MUST_MISMATCH <= got_mismatch, sorted(got_mismatch))
check("C2 真值表：S01/S02/S03/S05 无误报（不得出现在 MISMATCH）",
      not (MUST_NOT_MISMATCH & got_mismatch),
      {sid: by_scene[sid]["verdict"] for sid in sorted(MUST_NOT_MISMATCH)})
check("C3 真值表：S01/S02/S03/S05 均为 MATCH（域支持成立）",
      all(by_scene[sid]["verdict"] == "MATCH" for sid in MUST_NOT_MISMATCH),
      {sid: by_scene[sid]["verdict"] for sid in sorted(MUST_NOT_MISMATCH)})
check("C4 真值表：本样本 UNKNOWN 数为 0（六镜都有判定）",
      rep["counts"]["UNKNOWN"] == 0, rep["counts"])
check("C5 每条判定都带规则 ID + 理由 + 信号（可解释）",
      all(s["rule"] and s["reason"] and s["signals"] for s in rep["scenes"]),
      [s["rule"] for s in rep["scenes"]])
check("C6 判定口径写明'类别式、无数值阈值'（无可调阈值）",
      "无数值阈值" in rep["policy"], rep["policy"])
check("C7 证据含共享词分类与域命中关键词（可人工复核）",
      all("fragment_bridge" in s["signals"] and "query_domains" in s["signals"]
          and "asset_domains" in s["signals"] for s in rep["scenes"]),
      rep["scenes"][3]["signals"]["fragment_bridge"])

# ---------------- D. 确定性 / 离线 / 只读 ----------------
rep2 = semantic_report(DB, TRUTH_PID, artifact_id=TRUTH_ARTIFACT)
check("D1 确定性：同一输入两次运行结果逐字节一致",
      json.dumps(rep, ensure_ascii=False, sort_keys=True)
      == json.dumps(rep2, ensure_ascii=False, sort_keys=True),
      rep["summary"])
_orig = socket.socket

class _NoNet(socket.socket):                     # 断言"离线"：禁止任何 socket 连接
    def connect(self, *a, **k):
        raise AssertionError("语义验证器不应访问网络")

try:
    socket.socket = _NoNet
    rep_off = semantic_report(DB, TRUTH_PID, artifact_id=TRUTH_ARTIFACT)
finally:
    socket.socket = _orig
check("D2 离线：禁止 socket 连接后仍能完成核验（不访问网络）",
      rep_off["counts"] == rep["counts"], rep_off["counts"])
check("D3 只读：DB sha256/大小/行数在核验前后不变",
      before == after, "{} -> {}".format(before["sha256"][:12], after["sha256"][:12]))
try:
    con = readonly_connection(DB)
    con.execute("insert into decisions (decision_id, project_id, node, made_by, state, "
                "rationale, artifact_snapshot, created_at) values ('x','x','x','x','x','x','x',0)")
    con.close()
    ro_blocked = False
except sqlite3.OperationalError as exc:
    ro_blocked = "readonly" in str(exc).lower()
check("D4 只读连接写操作被 SQLite 拒绝", ro_blocked, "OperationalError(readonly)")

# ---------------- E. 独立样本（非 3-A 项目；描述性，不作准确率声明） ----------------
INDEPENDENT = [p for p in ("p_a2fe33da8739", "p_ab2b352e06b8") if (ROOT / "projects" / p).is_dir()]
spot = {}
for pid in INDEPENDENT:
    r = semantic_report(DB, pid)
    if r.get("found"):
        spot[pid] = r["counts"]
check("E1 独立样本可运行且给出三态计数（描述性记录，不声称准确率）",
      bool(spot), spot)
print("   独立样本计数（如实记录，未用于调参）：{}".format(json.dumps(spot, ensure_ascii=False)))

print("\n结果: {}/{} 通过".format(len(PASS), len(PASS) + len(FAIL)))
if FAIL:
    print("失败项:", FAIL)
sys.exit(0 if not FAIL else 1)
