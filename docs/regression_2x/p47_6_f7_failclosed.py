# -*- coding: utf-8 -*-
"""Phase 47：**F7 落账（FAIL-CLOSED：家族门未达标）** + 本轮真实缺陷清单。

结论：文生图能力**已建成并出图**（15 张概念插图全部上屏），渲染**成功**；
但 **G 家族份额门未达标**（实测 72.2% ≫ 33%），且**生产路径与独立求解路径结果不一致**
（同一约束下独立调用 `AL.satisfy` 可得 `pass=True`、G=11=30.6%）。
⇒ 按授权书「任一环节不可行 ⇒ STOP 报告选项」，**F7 不作为交付候选接受**，
落账「能力建成 + 门未达标 + 定位未完成」。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sqlite3
import subprocess
import sys
import time

R = pathlib.Path(r"C:\mp4agent\video-studio")
SB = R / "output" / "phase36_p36_4_sandbox"
L = R / "docs" / "regression_2x" / "logs"
FFPROBE = str(R / "bin" / "ffprobe.exe")
sys.stdout.reconfigure(encoding="utf-8")


def dur(p, sel=False):
    cmd = [FFPROBE, "-v", "error"]
    if sel:
        cmd += ["-select_streams", "v:0"]
    cmd += ["-show_entries", "stream=duration" if sel else "format=duration",
            "-of", "default=nw=1:nk=1", str(p)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    v = (r.stdout or "").strip().splitlines()
    return round(float(v[0]), 3) if v and v[0] else None


def main() -> int:
    fx = json.loads((SB / "fixture.json").read_text(encoding="utf-8"))
    pid = fx["sandbox_project_id"]
    pdir = R / "projects" / pid / "output"
    final = next((f for f in sorted(pdir.glob("*_with_outro_v2.mp4"))), None)
    con = sqlite3.connect("file:" + (R / "projects/video_studio.db").as_posix()
                          + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    p = json.loads(con.execute("select payload from events where project_id=? and "
                               "type='MATERIAL_TIMELINE'", (pid,)).fetchone()["payload"])
    con.close()
    dec, al = p["decisions"], (p.get("material_allocation") or {})
    gs = al.get("global_satisfy") or {}
    fam = json.loads((R / "config/family_map.json").read_text(encoding="utf-8"))["family_map"]
    gb = json.loads((L / "p47_2_gen_batch.json").read_text(encoding="utf-8"))
    sm = json.loads((L / "p47_1_gen_samples.json").read_text(encoding="utf-8"))
    feas = {"solver_pass_isolated": True, "G_isolated": 11, "G_share_isolated": 0.3056}
    gsh = set(x["sha256"][:12] for x in gb["items"] if x.get("ok"))
    on = [d["scene_id"] for d in dec
          if str((d.get("selected_asset") or {}).get("asset_id"))[6:18] in gsh]
    fc = gs.get("family_counts") or {}
    tot = sum(fc.values()) or 1
    rec = {
        "schema": "p47-f7-failclosed-v1",
        "stage": "Phase 47（文生图能力 + 抽象段视觉重做）—— FAIL-CLOSED，未登记交付候选",
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "capability_built": {
            "provider": "src/video_studio/tools/provider_gen.py（DashScope/wanx 异步文生图）",
            "model": "wanx2.1-t2i-turbo", "size": "1024*1024",
            "credential": "DASHSCOPE_API_KEY（缺则回退同平台 VLM_API_KEY）",
            "frozen_style": {"id": "a_黑板粉笔线稿",
                             "sha256": json.loads((R / "config/gen_style.json")
                                                  .read_text(encoding="utf-8"))
                             ["gen_style"]["frozen_style_sha256"],
                             "selected_by": "human:project-owner"},
            "samples": {"count": sm["ok_count"], "scene": sm["scene"],
                        "styles": [x["style_id"] for x in sm["samples"]]},
            "batch": {"generated": gb["generated"], "requests": gb["requests_used"],
                      "request_cap": gb["request_cap"]},
            "generated_on_screen_scenes": len(on),
        },
        "target_count_discrepancy": {
            "supervisor_estimate": "~21 抽象景",
            "measured_targets": json.loads((L / "p47_2_gen_targets.json")
                                           .read_text(encoding="utf-8"))["target_count"],
            "reason": ("本机口径把『语境限位景』（82d1e3ba 白名单）也算作实体占用 ⇒ "
                       "抽象景 15 个；若只算锚定表 allowed_scenes 则为 20 个。"
                       "**如实登记差异**，生成按保守的 15 景执行。"),
        },
        "blocking_defect": {
            "gate": "家族份额门 G ≤33%",
            "measured": {"G_count": fc.get("G_生成概念插图"), "G_share": round(
                fc.get("G_生成概念插图", 0) / tot, 4),
                "limit": (fam.get("max_share_by_family") or {}).get("G_生成概念插图")},
            "also_failing": {"cap": gs.get("cap_violations"),
                             "gap": gs.get("gap_violations"),
                             "adjacent_same_family": gs.get("adjacent_same_family"),
                             "family_share_violations": gs.get("family_share_violations")},
            "isolated_contradiction": feas,
            "diagnosis": ("**生产路径与独立求解路径不一致**：同一份 `family_map`/`cap`/"
                          "`gap`/options 语义下，独立调用 `AL.satisfy(restarts=40,"
                          "iters=1500)` 得 `pass=True`、G=11（30.6%）；而渲染路径恒得 "
                          "G=26（72.2%），且**对 seed 与预算均不敏感**（改 seed 丢弃/"
                          "不丢弃、restarts 20→40、iters 600→1500，结果逐位相同）"
                          "⇒ 强烈提示**渲染路径传入求解器的参数与独立路径不等价**"
                          "（尚未定位到具体差异）。**未完成定位，如实登记。**"),
        },
        "defects_found_and_fixed_this_phase": [
            {"id": "D1", "severity": "high",
             "what": ".env 里 VLM_API_KEY 的值被粘上中文注释（多 23 个非 ASCII 字符，总长 162）",
             "impact": "urllib 报 UnicodeEncodeError；HTTP 客户端可能发坏凭据静默 401",
             "fix": "core/env.py 新增 _clean_value()：取最后一个非 ASCII 之后的 ASCII 尾巴",
             "evidence": "清理后 len 116、非 ASCII 0；wanx 提交立即成功"},
            {"id": "D2", "severity": "high",
             "what": "检索池 **12 张历史素材 asset_id 为 None**（只有 sha256）",
             "impact": "`_family_of(None,…)` 恒 None ⇒ 这些素材**完全绕过家族约束**；"
                       "**F5/F6 报的家族份额其实只统计了有 id 的那部分**（F7 出现 "
                       "`\"null\": 24~25` 才暴露）",
             "fix": "agent 边界处按 asset_<sha12> 归一化 asset_id（归一化全池）"},
            {"id": "D3", "severity": "medium",
             "what": "家族 G 按 `asset_gen_*` 前缀标定，但时间轴的 asset_id 是 `asset_<sha12>`",
             "impact": "G 家族匹配数为 0（`\"null\"` 泛滥、G 上屏计 0）",
             "fix": "G 改按 sha256 前缀标定（15 个 sha12）"},
            {"id": "D4", "severity": "medium",
             "what": "wanx 返回 **PNG**，而获取脚本按 `.jpg` 命名",
             "impact": "扩展名与字节不符（本仓图片读取器拒读、下游按 jpg 处理有风险）",
             "fix": "provider 按 magic bytes 定扩展名；已把 3 张样片改名为 .png"},
            {"id": "D5", "severity": "medium",
             "what": "把「自动选材」结果直接当求解器 `initial` 种子，而该种子可能**已违反份额门**",
             "impact": "局部搜索被困在种子附近，可行解搜不到",
             "fix": "新增种子可行性检查；种子越门则丢弃（记 alloc.seed_rejected）"},
            {"id": "D6", "severity": "medium",
             "what": "锚定/内容过滤后**候选为空的景不进 `_opts`**",
             "impact": "求解器视其为「固定空」，可用面被压缩（G 反被推到 72%）",
             "fix": "空候选域回填全池（仍过锚定/排除过滤）"},
            {"id": "D7", "severity": "low",
             "what": "生成素材原以**硬绑定**表达「抽象景优先 G」（15 条）",
             "impact": "15/36 = 41.7% ⇒ 与「G ≤33%」**数学上冲突**，门不可能通过",
             "fix": "改为**候选择序**（G 置首）+ 分配器 tie-break；硬绑定撤销"},
        ],
        "current_state": {
            "render": "SUCCEEDED（残留卡景 0、full_cover=True、音轨一致）",
            "final_film": (str(final.relative_to(R)).replace("\\", "/") if final else None),
            "duration_s": (dur(final) if final else None),
            "sha256": (hashlib.sha256(final.read_bytes()).hexdigest() if final else None),
            "delivery_candidates_unchanged": ["F", "F2", "F3", "F4", "F5", "F6"],
            "F7": "已渲染但**未登记为交付候选**（家族门未达标）",
            "zero_promotion": True,
        },
        "options_for_supervisor": [
            {"id": "O1", "what": "授权我继续定位生产/独立求解路径的差异（不改门限）",
             "effect": "最可能直接让 F7 达标（独立路径已证可行）"},
            {"id": "O2", "what": "把 G 份额门放宽到 ≤75%（本轮实测 72.2%）",
             "effect": "F7 可立即交付；但抽象段将由 G 主导"},
            {"id": "O3", "what": "减少生成本数（如 11 景）以天然满足 33%",
             "effect": "门自动达标；但抽象段视觉覆盖变少"},
            {"id": "O4", "what": "扩池补非 G 素材，稀释 G 份额",
             "effect": "结构性缓解；需网络获取授权"},
        ],
        "budget": {"llm_usd": 0.0, "gen_requests": gb["requests_used"] + 3,
                   "gen_budget_cny_cap": 10.0 + 2.0, "network": "DashScope 生成接口"},
    }
    pth = L / "p47_f7_failclosed.json"
    pth.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    print("F7 落账（FAIL-CLOSED）")
    print("  能力建成：provider_gen + 样式冻结 + 样片 {} 张 + 批量 {} 张（{} 景上屏）".format(
        sm["ok_count"], gb["generated"], len(on)))
    print("  阻断：家族份额门 G 实测 {:.1%}（限 33%）；cap={} gap={} 家族相邻={}".format(
        fc.get("G_生成概念插图", 0) / tot, gs.get("cap_violations"),
        gs.get("gap_violations"), gs.get("adjacent_same_family")))
    print("  已定位并修复真实缺陷 {} 条（含 2 条高危）".format(
        len(rec["defects_found_and_fixed_this_phase"])))
    print("  未完成：生产/独立求解路径差异定位")
    print("-> " + str(pth.relative_to(R)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
