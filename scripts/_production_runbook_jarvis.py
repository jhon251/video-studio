"""JARVIS 人工执行包（Runbook）生成器（只读 2.x 蓝图，不生成视频/TTS/剪辑/发布）。"""
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "production_002"
pkg = json.loads((OUT / "final_production_plan.json").read_text(encoding="utf-8"))
plan = pkg["plans"]["bilibili"]["plan"]
scenes = plan["scenes"]
refs = pkg["references"]


def narration(text: str) -> str:
    """把场景脚本文本转成口播文案（去掉引用/编辑标记/备选开场）。"""
    t = text
    t = re.sub(r"（证据 [^）]*）", "", t)          # 去引用标注
    t = re.sub(r"\[EDIT[^\]]*\]", "", t)           # 去编辑标记
    t = re.sub(r"\[待补[^\]]*\]", "", t)
    t = t.replace("；离谱但真实，备选开场：", "\n备选开场：")  # 备选另起
    t = re.sub(r"离谱但真实，", "", t)             # 去风格包装词
    return t.strip()


# ---- 口播全文（逐镜） ----
lines = [
    "# 《什么时候才能拥有真正的 JARVIS？》人工执行包",
    "",
    f"- 版本：{pkg['production_version']} / 链 {pkg['chain_version']}",
    f"- 参考平台：B站 ｜ 目标时长 {plan['total_duration_hint']}s（11 分钟）｜ 总镜数 {len(scenes)}",
    f"- 输入指纹：{pkg['input_fingerprint']}（provenance 可复核）",
    "",
    "> 本文件是 2.x 的最终人工交付物：真人按此逐镜拍摄/录制/剪辑。",
    "> 2.x 不生成视频/配音/剪辑/发布——成片由人工完成。",
    "",
    "## 一、口播全文（逐镜）",
    "",
]
for s in scenes:
    role = s["role"]
    if role in ("fact", "gap"):
        continue  # 事实核查/待补为字幕卡，非口播
    n = narration(s["script_text"])
    lines.append(f"【{s['scene_id']}】{n}")
    lines.append("")

# ---- 逐镜分镜表 ----
lines.append("## 二、逐镜分镜表（Storyboard）")
lines.append("")
lines.append("| 镜号 | 画面 | B-roll | 字幕重点 | 时长 | 口播/文本 | 证据引用 |")
lines.append("|---|---|---|---|---|---|---|")
for s in scenes:
    n = narration(s["script_text"]).replace("|", "／")
    emph = "、".join(s["subtitle_emphasis"]) or "—"
    ev = "、".join(f"[{pkg['references']}]" if False else re.findall(r"\[(\d+)\]", s["script_text"]))
    ev = "、".join(f"[{x}]" for x in re.findall(r"\[(\d+)\]", s["script_text"])) or "—"
    lines.append(f"| {s['scene_id']} | {s['visual_target']} | {s['broll_requirement'] or '—'} | "
                 f"{emph} | {s['duration_hint']} | {n} | {ev} |")

# ---- 素材清单 ----
lines.append("")
lines.append("## 三、素材清单（按视觉类型汇总）")
lines.append("")
from collections import Counter
vt = Counter(s["visual_target"] for s in scenes)
for k, v in sorted(vt.items()):
    lines.append(f"- {k}：{v} 镜")

# ---- 字幕全文 ----
lines.append("")
lines.append("## 四、字幕全文（口播 + 重点标注）")
lines.append("")
for s in scenes:
    n = narration(s["script_text"])
    if not n:
        continue
    emph = "、".join(s["subtitle_emphasis"])
    lines.append(f"[{s['scene_id']}] {n}" + (f"  （重点：{emph}）" if emph else ""))

# ---- 参考来源 ----
lines.append("")
lines.append("## 五、参考来源（Evidence，共 {} 条）".format(len(refs)))
lines.append("")
for r in refs:
    lines.append(f"[{r['index']}] {r['title'][:60]}  {r['url']}")

# ---- 成本估算 ----
lines.append("")
lines.append("## 六、制作成本估算")
lines.append("")
cost = pkg["calibrated_cost"]
lines.append(f"- 逐镜内容工时：{cost['content_min']} 分钟")
for std, v in cost["per_standard"].items():
    lines.append(f"- {std}（含生命周期开销）：{v['hours']} 小时")
lines.append(f"- 素材难度：困难 {pkg['material']['hard_ratio']:.0%} ｜ 中+困难 {pkg['material']['midhard_ratio']:.0%}")

# ---- 核对表 ----
lines.append("")
lines.append("## 七、逐镜核对表（QA）")
lines.append("")
lines.append("- [ ] 每镜口播与字幕重点一致（数字/实体/限定词不漂移）")
lines.append("- [ ] 每镜证据引用 [n] 与参考来源一一对应")
lines.append("- [ ] 画面/B-roll 已按分镜表落实（数据可视化/证据截图/动画）")
lines.append("- [ ] 待补镜（entity:jarvis）已标注「切勿凭空断言」，未编造内容")
lines.append("- [ ] 总时长 660s ±10%（B站 6s/镜节奏）")
lines.append("- [ ] 视觉连串 ≤3（同画面不连续超过 3 镜）")

(OUT / "RUNBOOK_JARVIS.md").write_text("\n".join(lines), encoding="utf-8")
# 机器可读 shotlist
(OUT / "shotlist.json").write_text(json.dumps({
    "scenes": [{k: s.get(k) for k in ("scene_id", "role", "beat", "visual_target",
                                       "broll_requirement", "subtitle_emphasis", "duration_hint",
                                       "evidence_refs")} for s in scenes],
    "references": refs}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"RUNBOOK_JARVIS.md 与 shotlist.json 已写入 {OUT}")
print(f"总镜数 {len(scenes)} ｜ 口播镜 {sum(1 for s in scenes if s['role'] not in ('fact','gap'))}")
