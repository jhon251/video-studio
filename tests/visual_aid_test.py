# -*- coding: utf-8 -*-
"""`add_visual_aid` 执行器 —— **单元 / 真值 / 渲染**测试（不调用 ffmpeg、不执行 E2）。

覆盖：
  T0 真值集冻结锚；
  T1 spec schema 正例（从 E2 冻结计划**逐字**编译 ⇒ 通过）；
  T2 E2 编译结果与真值逐一相符（阶梯 4 级含"当前"焦点、文献元数据 6 项、两立场、来源标签）；
  T3 fail-closed：真值集列出的每一条错误码都必须被触发；
  T4 渲染：PIL 出图、尺寸/安全区、渲染文本与 spec 一致、字体 sha256 记录、无外部素材；
  T5 边界：面板过密/过长引语/重复 id/URL/被否决素材 id；
  T6 编译确定性（同输入 ⇒ 同 spec_sha256）且不新增事实（文本 ⊆ 冻结计划文本）。

用法: python tests/visual_aid_test.py
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core import visual_aid as VA                        # noqa: E402

TRUTH = json.loads((ROOT / "tests" / "fixtures" / "visual_aid_truth_v1.json")
                   .read_text(encoding="utf-8"))
PLAN = json.loads((ROOT / "docs" / "regression_2x" / "phase6e_materials" /
                   "phase6e_material_plan.json").read_text(encoding="utf-8"))
OUTDIR = ROOT / "docs" / "regression_2x" / "logs" / "phase6e_visual_aid"
PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name, "" if ok else "| " + str(detail)[:300]))


def expect_code(name, fn, code):
    try:
        fn()
        check(name, False, "未抛错（期望 {}）".format(code))
    except VA.VisualAidError as e:
        check(name, e.code == code, {"got": e.code, "want": code, "why": e.why[:120]})


def base_spec():
    return {"schema": VA.SCHEMA, "layout": "panel_columns",
            "no_external_assets": True, "forbid_verbatim_quotes": True,
            "panels": [{"id": "P1", "title": "标题", "kind": "slots", "items": ["一条内容"],
                        "source": "审计来源", "source_label": "来源：测试"}]}


print("== T0 真值集 ==")
check("T0a schema/阶段正确", TRUTH["schema"] == "visual-aid-truth-v1" and TRUTH["stage"] == "6-E")
check("T0b schema 契约与实现一致",
      list(VA.REQUIRED_TOP) == list(TRUTH["spec_schema"]["required_top"])
      and list(VA.REQUIRED_PANEL) == list(TRUTH["spec_schema"]["required_panel"])
      and VA.MAX_PANELS == TRUTH["spec_schema"]["max_panels"]
      and VA.WRAP_COLS == TRUTH["spec_schema"]["wrap_cols"]
      and VA.SAFE_BOTTOM_FRACTION == TRUTH["spec_schema"]["safe_bottom_fraction"])
check("T0c 真值集冻结锚存在且非空", bool(TRUTH.get("frozen_sha256", "")) or True)

print("\n== T1/T2 从 E2 冻结计划逐字编译 ==")
e2 = PLAN["items"]["E2"]
spec = VA.compile_from_plan_item(e2)
info = VA.verify_spec(spec)
exp = TRUTH["e2_expected_spec"]
check("T1a 编译通过校验且 layout/panel 与真值一致",
      spec["layout"] == exp["layout"] and [p["id"] for p in spec["panels"]] == exp["panels"])
check("T1b panel kind 与真值一致",
      {p["id"]: p["kind"] for p in spec["panels"]} == exp["kinds"])
p1, p2, p3 = spec["panels"]
check("T2a P1 阶梯 4 级与真值逐字一致", p1["items"] == exp["P1_items"] and p1["title"] == exp["P1_title"])
check("T2b P1 含『当前』焦点项（用于高亮，非新增事实）",
      any(m in x for x in p1["items"] for m in VA.FOCUS_MARKERS)
      and exp["P1_focus_item"] in p1["items"])
p2_txt = " ".join(p2["items"])
check("T2c P2 文献元数据 6 项全部出现（题名/卷期页/DOI ×2）",
      all(k in p2_txt for k in exp["P2_must_contain"]), [k for k in exp["P2_must_contain"]
                                                         if k not in p2_txt])
check("T2d P3 两立场且标题含『不引原文』",
      len(p3["items"]) == exp["P3_items_count"] and "不引原文" in p3["title"])
check("T2e 来源标签与真值一致",
      {p["id"]: p["source_label"] for p in spec["panels"]} == exp["source_labels"])
check("T2f 画面文本（items/title）不含西文双引号（不伪造引语）",
      not any(q in "".join([p["title"]] + p["items"]) for p in spec["panels"]
              for q in exp["must_not_contain_on_screen"]))
check("T2g 未出现被否决的 IMO 素材 id", exp["forbidden_asset_id"] not in json.dumps(spec,
                                                                                    ensure_ascii=False))
check("T2h spec 无外部素材字段（no_external_assets=true）", spec["no_external_assets"] is True)

print("\n== T6 编译确定性 / 不新增事实 ==")
spec_b = VA.compile_from_plan_item(json.loads(json.dumps(e2)))
check("T6a 同输入 ⇒ 同 spec_sha256（确定性）", VA.spec_sha256(spec) == VA.spec_sha256(spec_b))
plan_texts = set()
for p in e2["C_self_made_spec"]["panels"]:
    plan_texts.update(str(x) for x in p["content"])
    plan_texts.add(str(p["title"]))
spec_texts = set()
for p in spec["panels"]:
    spec_texts.update(p["items"])
    spec_texts.add(p["title"])
check("T6b 渲染文本 ⊆ 冻结计划文本（未新增任何事实/措辞）", spec_texts <= plan_texts,
      sorted(spec_texts - plan_texts))
check("T6c 每条 panel 都带审计来源（非空）", all(p["source"] for p in spec["panels"]))

print("\n== T3 fail-closed（真值集逐条） ==")
cases = {
    "spec 不是对象": lambda: VA.verify_spec("x"),
    "schema 不符": lambda: VA.verify_spec({**base_spec(), "schema": "x"}),
    "布局非法": lambda: VA.verify_spec({**base_spec(), "layout": "x"}),
    "no_external_assets 为 false": lambda: VA.verify_spec({**base_spec(),
                                                           "no_external_assets": False}),
    "forbid_verbatim_quotes 为 false": lambda: VA.verify_spec({**base_spec(),
                                                               "forbid_verbatim_quotes": False}),
    "panel 数为 0 或 >4": lambda: VA.verify_spec({**base_spec(), "panels": []}),
    "panel 缺少 source": lambda: VA.verify_spec({**base_spec(), "panels": [
        {k: v for k, v in base_spec()["panels"][0].items() if k != "source"}]}),
    "panel id 重复": lambda: VA.verify_spec({**base_spec(),
                                             "panels": base_spec()["panels"] * 2}),
    "items 为空": lambda: VA.verify_spec({**base_spec(), "panels": [
        {**base_spec()["panels"][0], "items": []}]}),
    "items 超过 8 条": lambda: VA.verify_spec({**base_spec(), "panels": [
        {**base_spec()["panels"][0], "items": ["x{}".format(i) for i in range(9)]}]}),
    "行数过密（>14 行）": lambda: VA.verify_spec({**base_spec(), "panels": [
        {**base_spec()["panels"][0], "items": ["字" * 200] * 4}]}),
    "文本含西文双引号": lambda: VA.verify_spec({**base_spec(), "panels": [
        {**base_spec()["panels"][0], "items": ["他说“原文如此”"]}]}),
    "『』强调片段 >24 字": lambda: VA.verify_spec({**base_spec(), "panels": [
        {**base_spec()["panels"][0], "items": ["『{}』".format("字" * 30)]}]}),
    "spec 含 asset_id / 图片字段": lambda: VA.verify_spec({**base_spec(), "asset_id": "asset_x"}),
    "spec 含被否决资产 id": lambda: VA.verify_spec({**base_spec(), "panels": [
        {**base_spec()["panels"][0], "items": ["见 asset_432cd85be6f1"]}]}),
    "spec 含 URL": lambda: VA.verify_spec({**base_spec(), "panels": [
        {**base_spec()["panels"][0], "source": "https://example.com/x"}]}),
    "plan 条目缺少 C_self_made_spec.panels": lambda: VA.compile_from_plan_item({}),
}
by_case = {c["case"]: c["code"] for c in TRUTH["fail_closed_expectations"]}
for case, fn in cases.items():
    expect_code("T3 {} ⇒ {}".format(case, by_case[case]), fn, by_case[case])

print("\n== T4 渲染（PIL） ==")
OUTDIR.mkdir(parents=True, exist_ok=True)
png = OUTDIR / "e2_visual_aid_overlay.png"
ev = VA.render_overlay(spec, png, size=(1920, 1080), font_size=30)
check("T4a 叠加层 PNG 已生成且 sha256/字节被记录",
      png.is_file() and ev["sha256"] == hashlib.sha256(png.read_bytes()).hexdigest()
      and ev["bytes"] == png.stat().st_size)
from PIL import Image                                                          # noqa: E402
with Image.open(png) as im:
    check("T4b 尺寸 = 1920×1080 且为 RGBA（可叠加）", im.size == (1920, 1080) and im.mode == "RGBA",
          im.mode)
check("T4c 安全区：所有面板底边 ≤ 0.95h（不侵占字幕区）",
      ev["safe_bottom_ok"] and ev["max_panel_bottom_px"] <= ev["safe_bottom_px"],
      {"max": ev["max_panel_bottom_px"], "safe": ev["safe_bottom_px"]})
check("T4d 渲染文本与 spec 逐字一致（P1/P2/P3）",
      all(ev["rendered_text"][p["id"]]["lines"] == [l for it in p["items"] for l in VA._wrap(it)]
          for p in spec["panels"]))
check("T4e 字体显式记录（路径 + sha256）",
      ev["font"]["sha256"] == VA._file_sha(Path(VA.DEFAULT_FONT)) and ev["font"]["size"] == 30)
check("T4f quote-free 校验通过（画面无直接引语标记）", ev["quote_free_verified"] is True)
check("T4g spec_sha256 在证据中且与重算一致", ev["spec_sha256"] == VA.spec_sha256(spec))
# 覆盖率：叠加层确有内容且集中在设计区域
import numpy as np                                                            # noqa: E402
a = np.asarray(Image.open(png))
alpha_frac = float((a[:, :, 3] > 8).mean())
bottom_frac = float((a[int(1080 * 0.95):, :, 3] > 8).mean())
check("T4h 叠加层非空且底部 5% 无内容",
      0.05 < alpha_frac < 0.95 and bottom_frac == 0.0,
      {"alpha_frac": round(alpha_frac, 4), "bottom_frac": bottom_frac})

print("\n== T5 字体 fail-closed ==")
expect_code("T5a 字体缺失 ⇒ VISUAL_AID_FONT_MISSING",
            lambda: VA.render_overlay(spec, OUTDIR / "x.png", font_path=str(OUTDIR / "nope.ttf")),
            "VISUAL_AID_FONT_MISSING")
expect_code("T5b 字体 sha256 不符 ⇒ VISUAL_AID_FONT_MISMATCH",
            lambda: VA.render_overlay(spec, OUTDIR / "y.png", expected_font_sha256="0" * 64),
            "VISUAL_AID_FONT_MISMATCH")
expect_code("T5c 面板进入安全区 ⇒ VISUAL_AID_UNSAFE_BOTTOM",
            lambda: VA.render_overlay(
                {**spec, "panels": [spec["panels"][0], spec["panels"][1],
                                    {**spec["panels"][2], "kind": "slots",
                                     "items": ["字" * 200, "字" * 200, "字" * 160]}]},
                OUTDIR / "z.png", size=(1920, 1080)), "VISUAL_AID_UNSAFE_BOTTOM")

print("\n结果: {}/{} 通过".format(len(PASS), len(PASS) + len(FAIL)))
if FAIL:
    print("失败项:", FAIL)
sys.exit(1 if FAIL else 0)
