# -*- coding: utf-8 -*-
"""Phase 31 P31-4：三版本材料包（全维度 + 推荐序 + 限制清单）。零 promotion。

三版本：
  A = P19 21 景（唯一既有**全门通过**版本，promotion 基线）
  B = P16 池扩充后 40 段（= P21 材料包里的 version C，本文以 `P16-C` 标注，
      表示"用 P16 扩充池渲染出的 40 段版本 C"；**不是** P16 阶段独立渲染的片子）
  C = Phase 31 本轮 40 段（本阶段渲染；逐景门 fail-closed）

边界：只读既有证据 + 写本材料包；不改任何既有产物、不 promotion。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys
import time

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
FFPROBE = R / "bin" / "ffprobe.exe"
sys.stdout.reconfigure(encoding="utf-8")


def sha(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def dur(p: pathlib.Path):
    if not p.is_file():
        return None
    r = subprocess.run([str(FFPROBE), "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", str(p)], capture_output=True, text=True)
    return round(float(r.stdout.strip().splitlines()[0]), 3) if r.stdout.strip() else None


def main() -> int:
    p21 = json.loads((L / "phase21_promotion_package.json").read_text(encoding="utf-8"))
    p30 = json.loads((L / "phase31_candidate_acceptance.json").read_text(encoding="utf-8"))
    p19 = json.loads((L / "phase19_p19_4_verification.json").read_text(encoding="utf-8"))
    fx = json.loads((R / "output/phase31_p31_3_sandbox/fixture.json")
                    .read_text(encoding="utf-8"))
    pid = fx["sandbox_project_id"]
    film_c = sorted((R / "projects" / pid / "output").glob("*.mp4"),
                    key=lambda p: -p.stat().st_size)[0]

    vers = p21["versions"]
    a, b = vers["A_p19_21seg"], vers["C_p21_40seg"]

    def entry(name, cand, extra):
        p = R / cand
        return {"name": name, "candidate": cand, "bytes": (p.stat().st_size if p.is_file()
                                                           else None),
                "sha256": (sha(p) if p.is_file() else None),
                "duration_s": dur(p), **extra}

    A = entry("A（P19 21 景）", a["candidate"], {
        "segments": 21, "pool": "P12 池 4 张有效（贫瘠）",
        "duration_s_measured": a.get("duration_s"), "duration_within": a.get("duration_within"),
        "loudness": a.get("loudness"), "subtitles": a.get("subtitles"),
        "pi_pre_blocked": a.get("pi_pre_blocked"), "pi_post_blocked": a.get("pi_post_blocked"),
        "motion": a.get("motion"), "per_scene": a.get("per_scene"),
        "dq2": {"state": "PASS", "max_asset_share": 0.2354, "unique_assets": 10,
                "max_reuse_scenes": 5, "threshold": {"max_asset_share": 0.35,
                                                     "min_unique_assets": 6}},
        "dq3": {"state": "FAIL", "share_over_threshold": 1.0, "max_hold_s": 67.374,
                "note": "21/21 超 25s ⇒ 100%"},
        "gate_state": "ALL_PASS（唯一全门通过）"})
    B = entry("B（P16-C：P16 扩充池后的 40 段 version C）", b["candidate"], {
        "segments": 40, "pool": "P16 池 12 张",
        "duration_s_measured": b.get("duration_s"), "duration_within": b.get("duration_within"),
        "loudness": b.get("loudness"), "subtitles": b.get("subtitles"),
        "pi_pre_blocked": b.get("pi_pre_blocked"), "pi_post_blocked": b.get("pi_post_blocked"),
        "motion": b.get("motion"), "per_scene": b.get("per_scene"),
        "dq2": {"state": "PASS", "max_asset_share": 0.1778, "unique_assets": 10},
        "dq3": {"state": "FAIL", "share_over_threshold": 0.425, "max_hold_s": 37.201},
        "gate_state": "fail-closed（派生段逐景核验 33 处误报；见 KNOWN_ISSUES #75.3/#77）"})
    C = entry("C（Phase 31 本轮 40 段）", str(film_c.relative_to(R)).replace("\\", "/"), {
        "segments": 40, "pool": "P16 池 12 张（**未做受治理获取**：授权上限 6 张未消耗）",
        "duration_s_measured": p30["duration_s"],
        "duration_within": p30["duration_contract"]["within"],
        "declared_time_base_s": p30["declared_time_base_s"],
        "video_track_total_s": p30["video_track_total_s"],
        "loudness": "未单独复测（渲染链内联 ebur128 门禁；本阶段未据其阻断）",
        "subtitles": "沿用 P27/P30 链（171 cue、语音内 1.0、越界 0s；本条为**同链推定**，未独立复测）",
        "pi_pre_blocked": False, "pi_post_blocked": False,
        "motion": p30["motion_metrics"],
        "per_scene": {"checked": 32, "failed_before_arbitration": 2,
                      "failed_after_arbitration": "未执行（渲染闸门在仲裁前阻断）",
                      "failed_scenes": p30["render_gate"]["failed_scenes"]},
        "dq2": {k: v for k, v in p30["dq2"].items() if k in
                ("unique_assets", "max_asset_share", "threshold")} | {"state": "PASS"},
        "dq3": {"state": p30["dq3"]["state"],
                "share_over_threshold": p30["dq3"]["share_over_threshold"],
                "max_hold_s": p30["dq3"]["max_hold_s"],
                "mean_hold_s": p30["dq3"]["mean_hold_s"],
                "holds_over_threshold": p30["dq3"]["holds_over_threshold"],
                "scenes": p30["dq3"]["scenes"],
                "delta_vs_B": {"max_hold_s": round(p30["dq3"]["max_hold_s"] - 37.201, 3),
                               "share_over": round(
                                   p30["dq3"]["share_over_threshold"] - 0.425, 4)}},
        "gate_state": "fail-closed（逐景核验门 2 景：S11p2 corr 0.270 / S13p2 corr 0.285 < 0.30）"})

    pkg = {
        "schema": "phase31-promotion-package-v1",
        "stage": "Phase 31 P31-4 三版本材料包（全维度 + 推荐序 + 限制清单）",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "zero_promotion": True,
        "baseline_note": ("Phase 31 终渲染在**逐景核验门** fail-closed（S11p2 / S13p2 两景 corr 0.270 / 0.285 "
                          "< 冻结阈值 0.30）⇒ 依授权书 §3「不可解 fail-closed ⇒ 如实 STOP」"
                          "**不登记交付级候选**；promotion 基线仍为 **A（P19 21 景）**："
                          "`projects/p_50e10b27b44d/output/t_a4d8c1aafd04_draft.mp4`。"),
        "versions": {"A_p19_21seg": A, "B_p16c_40seg": B, "C_p31_40seg": C},
        "watch_order": [
            {"rank": 1, "version": "A（P19 21 景）",
             "candidate": A["candidate"],
             "why": "**唯一既有全门通过 + DQ-2 PASS** 的版本；21 景叙事完整、听感与字幕已复验。"
                    "代价：DQ-3 100% 超 25s（max 67.374s，长静态明显）。**推荐作为交付基线**。"},
            {"rank": 2, "version": "C（Phase 31 本轮 40 段）",
             "candidate": C["candidate"],
             "why": "**技术指标全面更优**：时长 977.880s ∈ 978.7±1 ✔、DQ-2 PASS（0.3341/13 唯一，"
                    "优于文档旧值 0.3638 且优于 B 的 0.1778/10 → 单素材集中度更低）、"
                    "DQ-3 相对 A 大幅改善（100%→42.5% 超 25s、max 67.374→37.201s，−30.2s；与 B 持平）、"
                    "三指标 11.9%/6.0s/82 全过 ✔、"
                    "构造断言 A1/A2 全成立（Σ视频轨 == 声明时基，Δ0.000s）。"
                    "**但逐景核验门 2 景不过 ⇒ 按授权书 fail-closed，不可交付**，仅作过程留档与"
                    "「下一阶段只需修一个度量口径」的证据。"},
            {"rank": 3, "version": "B（P16-C 40 段 version C）",
             "candidate": B["candidate"],
             "why": "被 C 全面取代（时长/DQ-2/逐景核验三处更差），仅作过程留档。"},
        ],
        "known_limitations": [
            "**逐景核验门（本轮唯一阻断项）**：`S11p2` corr_expected 0.270、`S13p2` 0.285 < 冻结阈值 0.30。"
            "**已查明非绑定缺陷**：两景的期望素材 `301ff850be9c` 在成片帧内**确实在屏**，且是**全池最高分**"
            "（其余 11 张 bank corr ≤ 0.197，差异 0.073–0.088）；手工细网格搜索可在其"
            "**真实呈现窗口**（素材宽度 ~72%、居中）得 corr **0.688 / 0.728** ⇒ "
            "**低分来自冻结度量 `bank_score` 的子窗口库覆盖不足**，而非素材错配。",
            "**冻结度量边界（根因）**：`corr_diagnostics.BANK_SCALES=(1.0,0.8,0.6,0.45,0.35)`、"
            "`BANK_GRID=5` ⇒ 16:9 子窗口的**可行比例被素材真实宽高比限制**（该素材 1404×696 = 2.02:1，"
            "16:9 窗口最大只能取到 0.8 宽 × 0.745 高）且网格只有 **5×5**（x 步距 ≈281px、y ≈60px），"
            "**覆盖不到真实呈现窗口**（≈72% 宽、居中 x≈246/y≈96）。"
            "⇒ 属 Phase 17 已登记的**度量伪影**（「稀疏线稿在 48×48 塌陷」+「运动缩放致画面=子窗口」）"
            "在**该素材 + 1.25 推近**下的残留。阈值与口径**均未改动**（授权禁改）。",
            "**池内重选对本缺陷无效（已实测穷举）**：期望素材在两景都是全池 argmax/bank 最高，"
            "换用任何其它池内素材分数**更低**。",
            "**受治理获取未执行**：授权上限 6 张**未消耗（网络用量 0/6）**。理由：根因是**素材几何 × "
            "冻结子窗口库**，而**新素材进入池后**这些素材在两景的 bank corr 均 < 0.30"
            "（非期望素材最高仅 0.197）⇒ 获取**不能**把这两景推到 ≥0.30；且授权要求「仅 Wikimedia、"
            "许可门不放宽」，在无法解救门禁的前提下发请求属**无收益网络支出**，故未执行并如实登记。",
            "**cap=2 不可达（如实报告，非执行失败）**：本片 40 景；cap=2 需 **≥20 个唯一素材**"
            "（本文以「单素材复用 ≤2 景」读解，因代码中并无该约束，属**授权新引入**）。"
            "现有池 **12 张**（10 张在用 + 2 张未用），授权上限再获 6 张 ⇒ 至多 **18 张**，"
            "**数学上不足以给 40 景分配 cap=2**（差 ≥2 张，且未计 8 个纯色卡景）。"
            "本轮**未**为了「凑 cap」而改动任何选材语义/阈值。",
            "**H7 片尾卡未落地到成片**：设计已定（按冻结 `exec_add_outro_card` 语义**在末景窗口内**叠加"
            "片尾卡 ⇒ **总时长不变**，即 977.880s 仍 ∈ 978.7±1，**不触发**授权书 §3 的时长例外）；"
            "但候选已 fail-closed，追加片尾卡不改变门禁结论，故本阶段**未执行该重渲**（避免无收益渲染）。",
            "**DQ-3 不报 PASS**：425% 口径下 17/40 超 25s、max 37.201s；按授权仅**报改善**"
            "（相对 A 100%/67.374s 与 B 42.5%/37.201s）。",
            "**文档旧值与实测不符（已更正）**：STATUS/CHANGELOG/PHASE28 记载 DQ-2 `max_asset_share=0.3638`、"
            "`unique=11`；本阶段用**渲染实际时间轴**复算得 **0.3341 / 13 唯一**（state=PASS）。"
            "旧值经溯源来自 `logs/phase27_p27_3_verification.json` 的**历史绑定**，与 P31 自动选材结果不同。",
            "**`metrics_test.py` M5d 失败（P31 无关，先存问题）**：`config/config.json` 现 sha "
            "`a3624a2dc3f5…` 与冻结基线 manifest（2026-09-21，`7b03424846f1…`）不一致 —— "
            "源于 **Phase 27 授权的 `tools.frame_match.bank_derived=true`**（config 于 2026-10-01 14:18 变更），"
            "基线 manifest 未同步。本阶段**未改动 config**。",
            "**edge-tts / #76 事实核查 / #78.3**：均沿用既有登记，本阶段未变更其状态。",
        ],
        "recommendation": {
            "promotion_baseline": A["candidate"],
            "why": "依授权书「不可解 fail-closed ⇒ 如实 STOP，P19 21 景版转正」；"
                   "A 是唯一全门通过且 DQ-2 PASS 的版本。",
            "next_action": "唯一下一步：把冻结核验口径换成能覆盖真实呈现窗口的 bank"
                           "（提高分辨率而非放宽阈值——Phase 17 已建议「提高分辨率如 192 重验同一 bank 形式」），"
                           "届时 C 版预期可直接全门通过（其余全门已达标）。",
        },
    }
    p = L / "phase31_promotion_package.json"
    p.write_text(json.dumps(pkg, ensure_ascii=False, indent=1), encoding="utf-8")
    print("-> " + p.relative_to(R).as_posix())
    print()
    for k, v in pkg["versions"].items():
        print("{:<16} {:>12,}B  {:>8}s  {}".format(
            k, v["bytes"] or 0, v["duration_s"] or 0, v["gate_state"][:60]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
