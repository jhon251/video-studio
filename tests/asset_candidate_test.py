# -*- coding: utf-8 -*-
"""P7-2 测试：AssetCandidate 契约 + AssetIndex（稳定身份/硬 sha256/感知身份/近重复四类/零网络）。

覆盖：
 1 schema validation · 2 stable asset_id（跨路径/顺序/进程）· 3 sha256 硬身份（内容变⇒id变）
 4 媒体事实（图像无 duration ⇒ NOT_AVAILABLE）· 5 不知道≠猜测（UNKNOWN 语义）
 6 感知身份（复用 content_identity）· 7 四类关系 A/B/C/D · 8 镜像 ⇒ UNKNOWN
 9 确定性（同输入同 artifact_hash）· 10 真实索引 + 回归兼容 + 6-G 不可变快照

运行: python tests/asset_candidate_test.py
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import sys
import tempfile

ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core import asset_candidate as AC                              # noqa: E402
from video_studio.core import materials as MAT                                   # noqa: E402
from video_studio.tools import asset_index_builder as AIB                        # noqa: E402
from video_studio.ops import asset_index as OPS                                  # noqa: E402

PASS, FAIL = [], []


def check(name, ok, detail=None):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name,
                             "" if ok else json.dumps(detail, ensure_ascii=False,
                                                      default=str)[:240]))
    return bool(ok)


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def _mk_fixtures(d: pathlib.Path):
    """合成夹具：A 完全相同 / B 同内容不同编码 / C 裁剪形变 / D 独立。"""
    from PIL import Image, ImageDraw
    import numpy as np
    # base：水平渐变 + 两个方块（dHash 非退化）
    w, h = 800, 400
    g = np.tile(np.linspace(0, 255, w, dtype=np.uint8), (h, 1))
    base = Image.fromarray(g, mode="L").convert("RGB")
    dr = ImageDraw.Draw(base)
    dr.rectangle([100, 100, 250, 250], fill=(255, 0, 0))
    dr.rectangle([500, 200, 650, 350], fill=(0, 0, 255))
    base.save(d / "base.png")
    shutil.copy2(d / "base.png", d / "base_copy.png")            # A：完全相同字节
    base.save(d / "base.jpg", quality=95)                        # B：同内容不同编码
    # wide：竖条纹 + 不同宽高比；crop 为其 full_bleed 裁剪（C 类）
    stripes = np.tile((np.arange(1600) // 20 % 2 * 255).astype(np.uint8), (600, 1))
    wide = Image.fromarray(stripes, mode="L").convert("RGB")
    wide.save(d / "wide.png")
    box = AIB.full_bleed_box(1600, 600, 16 / 9)
    wide.crop(box).save(d / "crop.png")
    # other：棋盘格（独立）
    chk = ((np.add.outer(np.arange(400) // 25, np.arange(400) // 25) % 2) * 255).astype(np.uint8)
    Image.fromarray(chk, mode="L").convert("RGB").save(d / "other.png")
    return d


tmp = pathlib.Path(tempfile.mkdtemp(prefix="p72_fixtures_"))
_mk_fixtures(tmp)

# ---------------- 1. schema validation
art = AIB.build_index(project_media=str(tmp), h5_assets=[], master_used={},
                      metadata_sources=[{"role": "test_fixture", "path": str(tmp)}],
                      media_root_label="tmp_fixtures")
cands = art["candidates"]
check("1 AssetIndex 构建成功且逐条通过契约校验",
      len(cands) == 5 and AIB.validate_index(art) == [], {"n": len(cands),
                                                          "errs": AIB.validate_index(art)[:4]})
bad = json.loads(json.dumps(cands[0]))
bad["sha256"] = "f" * 64
check("1b asset_id 与内容不一致 ⇒ 校验报错",
      any("asset_id" in e for e in AC.validate_candidate(bad)), AC.validate_candidate(bad)[:3])
bad2 = json.loads(json.dumps(cands[0]))
bad2["decode_status"] = "MAYBE"
check("1c decode_status 非法 ⇒ 报错", bool(AC.validate_candidate(bad2)))
bad3 = json.loads(json.dumps(cands[0]))
bad3["deterministic_hash"] = "0" * 64
check("1d deterministic_hash 被篡改 ⇒ 报错", bool(AC.validate_candidate(bad3)))
bad4 = json.loads(json.dumps(cands[0]))
bad4["duration_s"] = 12.0
check("1e 图像给出 duration ⇒ 报错（不得编造）", bool(AC.validate_candidate(bad4)))

# ---------------- 2. stable asset_id
by_name = {pathlib.Path(c["path"]).name: c for c in cands}
base_id = by_name["base.png"]["asset_id"]
check("2 稳定 id 由内容派生（ast- 前缀 + 16 hex）",
      base_id.startswith("ast-") and len(base_id) == 20, base_id)
check("2b 同内容不同**路径/文件名**（base_copy.png）⇒ 合并为同一候选（同 asset_id）",
      "base_copy.png" not in by_name
      and any(pathlib.Path(p).name == "base_copy.png"
              for c in cands for p in c.get("duplicate_paths", [])
              if pathlib.Path(p).name == "base_copy.png"))
tmp2 = pathlib.Path(tempfile.mkdtemp(prefix="p72_otherdir_"))
shutil.copy2(tmp / "base.png", tmp2 / "renamed_elsewhere.png")
art2 = AIB.build_index(project_media=str(tmp2), h5_assets=[], master_used={},
                       metadata_sources=[], media_root_label="tmp2")
check("2c 换目录/换文件名（不同机器场景）⇒ **相同 asset_id**",
      art2["candidates"][0]["asset_id"] == base_id,
      {"a": base_id, "b": art2["candidates"][0]["asset_id"]})
check("2d 扫描顺序无关（候选按 asset_id 排序；两次构建条目序一致）",
      [c["asset_id"] for c in cands] == sorted(c["asset_id"] for c in cands))

# ---------------- 3. sha256 硬身份（内容变 ⇒ 身份变）
p3 = tmp2 / "mutated.png"
data = bytearray((tmp / "base.png").read_bytes())
data.extend(b"\x00")                                     # 追加 1 字节（PNG 尾部垃圾，解码仍可）
p3.write_bytes(bytes(data))
art3 = AIB.build_index(project_media=str(tmp2), h5_assets=[], master_used={},
                       metadata_sources=[], media_root_label="tmp2")
by_name3 = {pathlib.Path(c["path"]).name: c for c in art3["candidates"]}
check("3 内容变化 ⇒ sha256 变 ⇒ asset_id 变（不得凭文件名认定同一素材）",
      len(art3["candidates"]) == 2
      and by_name3["renamed_elsewhere.png"]["asset_id"] == base_id
      and by_name3["mutated.png"]["asset_id"] != base_id
      and by_name3["mutated.png"]["sha256"] != by_name3["renamed_elsewhere.png"]["sha256"],
      {k: v["asset_id"] for k, v in by_name3.items()})

# ---------------- 4/5. 媒体事实与 UNKNOWN 语义
check("4 图像 duration/frame_count == NOT_AVAILABLE（类别不适用，非猜测）",
      all(c["duration_s"] == AC.NOT_AVAILABLE and c["frame_count"] == AC.NOT_AVAILABLE
          for c in cands))
dec = next((c for c in cands if pathlib.Path(c["path"]).name == "base.png"), None)
check("4b 几何实测记录（800×400）", dec and dec["width"] == 800 and dec["height"] == 400,
      {"w": dec and dec["width"], "h": dec and dec["height"]})
check("5 本地素材许可未知 ⇒ license/license_class/attribution/restricted 均 UNKNOWN（不得当 False）",
      dec["license"] == "unchecked" and dec["license_class"] == AC.UNKNOWN
      and dec["attribution"] == AC.UNKNOWN and dec["license_restricted"] == AC.UNKNOWN
      and dec["license_gate_applies"] is False)
badfile = tmp / "broken.png"
badfile.write_bytes(b"\x89PNG\r\n\x1a\nnot-a-real-png")
art_bad = AIB.build_index(project_media=str(tmp), h5_assets=[], master_used={},
                          metadata_sources=[], media_root_label="tmp")
bd = next((c for c in art_bad["candidates"] if pathlib.Path(c["path"]).name == "broken.png"), None)
check("5b 不可解码 ⇒ decode_status=FAILED、perceptual=UNKNOWN、integrity=BLOCK（不猜）",
      bd and bd["decode_status"] == "FAILED" and bd["perceptual_identity"]["status"] == AC.UNKNOWN
      and bd["integrity_status"] == "BLOCK", {"bd": bd and bd["decode_status"]})

# ---------------- 6/8. 感知身份与镜像
check("6 感知身份来自 content_identity（dHash 64 位 + md5 + 复用标注）",
      dec["perceptual_identity"]["status"] == "OK"
      and len(dec["perceptual_identity"]["dhash_hex"]) == 64
      and len(dec["perceptual_identity"]["md5"]) == 32
      and "content_identity" in dec["perceptual_identity"]["method"])
check("8 镜像不变比较 = UNKNOWN（既有实现未提供；未新造算法、未放宽阈值）",
      dec["perceptual_identity"]["mirror_invariance"]["status"] == AC.UNKNOWN
      and art["relationships"]["mirror_invariance"]["status"] == AC.UNKNOWN)
check("6b content_identity 频带未被调整（same_band=6 / suspect_band=10）",
      art["bands"]["same_band"] == 6 and art["bands"]["suspect_band"] == 10)

# ---------------- 7. 四类关系
rel = art["relationships"]
fam_ids = {c["asset_id"]: None for c in cands}
fam_of = {}
for f in rel["perceptual_families"]:
    for m in f["members"]:
        fam_of[m] = f["family_id"]
bj = by_name["base.jpg"]["asset_id"]
check("7 A 类（完全相同文件）被合并并记录副本路径",
      len(rel["exact_duplicate_groups"]) == 1
      and len(rel["exact_duplicate_groups"][0]["paths"]) == 2)
check("7b B 类（不同 sha256 + 同感知家族）被识别为同一家族",
      fam_of.get(base_id) is not None and fam_of.get(base_id) == fam_of.get(bj),
      {"base": fam_of.get(base_id), "jpg": fam_of.get(bj)})
wid = by_name["wide.png"]["asset_id"]
crop = by_name["crop.png"]["asset_id"]
check("7c C 类（裁剪/变换）产生**候选关系**并带实测证据",
      any(t["kind"] == "crop_to_aspect" and {t["a"], t["b"]} == {wid, crop}
          and t["status"] == "CANDIDATE" and t["dhash_shift"] <= AIB.CROP_MAX_SHIFT
          for t in rel["transform_relations"]),
      [t for t in rel["transform_relations"] if {t["a"], t["b"]} == {wid, crop}])
oth = by_name["other.png"]["asset_id"]
check("7d D 类（独立视觉资产）与 base/wide 均不在同一家族、无关系",
      fam_of.get(oth) not in (fam_of.get(base_id), fam_of.get(wid))
      and oth in rel["independent_asset_ids"], {"fam_other": fam_of.get(oth)})
check("7e 关系分类图例齐备（A/B/C/D 四类定义在 artifact 内）",
      set(rel["classification_legend"]) == {"A_exact_same_file", "B_same_perceptual_family",
                                            "C_crop_or_transform", "D_independent"})

# ---------------- 9. 确定性
art_a = AIB.build_index(project_media=str(tmp), h5_assets=[], master_used={},
                        metadata_sources=[{"role": "x"}], media_root_label="tmp")
art_b = AIB.build_index(project_media=str(tmp), h5_assets=[], master_used={},
                        metadata_sources=[{"role": "x"}], media_root_label="tmp")
check("9 两次构建 ⇒ 同 artifact_hash / 同 canonical（无时间戳）",
      art_a["artifact_hash"] == art_b["artifact_hash"]
      and AIB.index_hash(art_a) == art_a["artifact_hash"]
      and "created" not in json.dumps(art_a)[:200].lower())
check("9b 候选 deterministic_hash 可复算", all(c["deterministic_hash"] == AC.candidate_hash(c)
                                              for c in cands))

# ---------------- 10. 真实索引 + 回归兼容 + 6-G 快照
snap = {k: sha(v) for k, v in {
    "master": ROOT / "output/phase6g_exec_h5/20260929_151026/out/H5_rp-0ebebb71f99c.mp4",
    "ledger": ROOT / "docs/regression_2x/logs/phase6g_exec_ledger.jsonl",
    "register": ROOT / "docs/regression_2x/logs/phase6g_rebuild_proposal_register.jsonl",
    "baseline_zip": ROOT / "docs/regression_2x/baseline/6.x-final-baseline.zip",
    "material_plan": ROOT / "docs/regression_2x/phase6e_materials/phase6e_material_plan.json",
}.items()}
try:
    real = OPS.build()
    rc = {c["asset_id"]: c for c in real["candidates"]}
    # P33-2 **测试契约更新**（非业务语义变更）：素材池经**受治理获取**扩容
    # （12 → 17 张，其中 5 张落入项目媒体目录）⇒ 真实索引的候选数由 **8 增至 13**
    # （8 = 原 6 项目 + 2 H5；+5 = P33-2 新获取）。断言改为：**不少于**钉定的 8 个，
    # 且**不出现解码失败**、`visual == len(candidates)`（"全部可解码"的强度不变）。
    check("10 真实索引：视觉候选 ≥8（原 6 项目 + 2 H5，P33-2 扩容 +5），全部可解码",
          len(rc) >= 8 and real["counts"]["decode_failed"] == 0
          and real["counts"]["visual"] == len(rc), real["counts"])
    check("10b 6-G 母片实际使用的 4 件已标注 role_in_master 且 legacy id 映射完整",
          real["counts"]["used_in_6g_master"] == 4
          and all(c["legacy_asset_ids"] for c in real["candidates"]
                  if c["role_in_master"] == "USED_IN_6G_MASTER"))
    h5 = [c for c in real["candidates"] if c["source_type"] == "web"]
    check("10c H5 两件素材：许可/来源/署名来自正式记录（S05 PD-US、S11 CC BY 4.0）",
          len(h5) == 2
          and {c["license_class"] for c in h5} == {"PUBLIC_DOMAIN", "FREE_ATTRIBUTION"}
          and all(c["source_url"] != AC.UNKNOWN and c["attribution"] != AC.UNKNOWN for c in h5),
          [{c["license"]: c["source_url"][:40]} for c in h5])
    ext = [c for c in real["candidates"] if c["source_type"] == "external"]
    check("10d 外部素材：provider/source_id 有值，source_url 记为 UNKNOWN（不构造 URL）",
          len(ext) == 3 and all(c["provider"] != AC.UNKNOWN and c["source_url"] == AC.UNKNOWN
                                for c in ext), [c["provider"] for c in ext])
    check("10e 外部缓存索引记录的缺失文件已登记（cache_missing）",
          real["external_cache"]["cache_missing_count"] > 0
          and real["external_cache"]["index_entries"] >= 14,
          {"entries": real["external_cache"]["index_entries"],
           "missing": real["external_cache"]["cache_missing_count"]})
    check("10f 非视觉媒体（voice/*.mp3 等）单独登记，不混入视觉身份",
          len(real["non_visual_inventory"]) >= 20
          and all(c["media_kind"] in ("image", "video") for c in real["candidates"]))
    real2 = OPS.build()
    check("10g 真实数据两次构建 ⇒ 同 artifact_hash", real2["artifact_hash"] == real["artifact_hash"])
except OPS.SourceMissing as exc:                                        # pragma: no cover
    print("SKIP 10*（真实源不可用：{}）".format(exc))

snap2 = {k: sha(v) for k, v in {
    "master": ROOT / "output/phase6g_exec_h5/20260929_151026/out/H5_rp-0ebebb71f99c.mp4",
    "ledger": ROOT / "docs/regression_2x/logs/phase6g_exec_ledger.jsonl",
    "register": ROOT / "docs/regression_2x/logs/phase6g_rebuild_proposal_register.jsonl",
    "baseline_zip": ROOT / "docs/regression_2x/baseline/6.x-final-baseline.zip",
    "material_plan": ROOT / "docs/regression_2x/phase6e_materials/phase6e_material_plan.json",
}.items()}
check("10h 6-G 不可变快照：母片/ledger/register/baseline/冻结材料 未变", snap == snap2)
check("10i 未修改 DQ-2 口径（artifact 内显式声明；core/direction.py 未改）",
      "不修改 DQ-2" in real["dq_note"])

print("\n结果: {}/{} 通过".format(len(PASS), len(PASS) + len(FAIL)))
if FAIL:
    print("失败项:", FAIL)
sys.exit(1 if FAIL else 0)
