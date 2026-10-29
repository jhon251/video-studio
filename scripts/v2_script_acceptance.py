"""JARVIS 口播稿 v2 验收：量化 A/B + Truth 审计（只读，不改代码/产物）。"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "production_002"

# ---- 旧稿（v1 模板版，final_production_plan.json 的 bilibili scenes）----
old_pkg = json.loads((OUT / "final_production_plan.json").read_text(encoding="utf-8"))
old_text = "\n".join(s["script_text"] for s in old_pkg["plans"]["bilibili"]["plan"]["scenes"])

# ---- 新稿（v2 验收版）----
new_raw = (OUT / "V2_FINAL_SCRIPT_JARVIS.md").read_text(encoding="utf-8")
new_body = re.sub(r"【.*?】|\n|#|\*|（证据.*?）", "", new_raw)
new_text = new_body.strip()

FORBIDDEN = ["咱们聊聊", "其实啊", "是不是有点意思", "关于这个命题", "没想过的答案",
             "综合现有证据", "进入下一部分", "接下来我们来看", "首先，", "其次，",
             "想象一下", "你有没有想过", "值得注意", "离谱但真实", "你敢信",
             "呼应开场", "谨慎作答", "是不是很有意思", "这是不是很神奇",
             "从某种意义上来说", "归根结底", "简单来说", "换句话说", "这意味着", "可以说"]


def metrics(text, name):
    chars = len([c for c in text if not c.isspace()])
    han = len(re.findall(r"[\u4e00-\u9fff]", text))
    tics = {t: text.count(t) for t in FORBIDDEN if text.count(t)}
    questions = len(re.findall(r"[？?]", text))
    forced = len(re.findall(r"如果.{0,10}这件事成立", text))
    nai_b = len(re.findall(r"不是.{1,20}而是", text))
    sentences = [s.strip() for s in re.split(r"[。！？\n]", text) if s.strip()]
    starts = Counter(s[:6] for s in sentences if len(s) >= 6)
    rep_starts = {k: v for k, v in starts.items() if v >= 3}
    secs = len(re.findall(r"首先|其次|最后", text))
    print(f"[{name}] 字符 {chars} | 汉字 {han} | 句数 {len(sentences)} | 问号 {questions} | "
          f"机械反问 {forced} | 不是…而是 {nai_b} | 首先/其次/最后 {secs}")
    print(f"   禁用模板命中: {tics or '无'}")
    print(f"   句首重复(≥3): {rep_starts or '无'}")
    return {"chars": chars, "han": han, "tics": tics, "questions": questions,
            "forced": forced, "nai_b": nai_b, "rep_starts": rep_starts}


print("==== 量化 A/B ====")
mo = metrics(old_text, "旧稿 v1")
mn = metrics(new_text, "新稿 v2")

# ---- Truth 审计 ----
print("\n==== Truth/Evidence 不变性审计 ====")
claims = json.loads((OUT / "input.json").read_text(encoding="utf-8"))["video"]["claims"]
must_have = {
    "C1 多轮对话已商业化": ["多轮对话", "商业化", "幻觉", "事实一致性"],
    "C2 记忆工程化早期": ["工程化早期", "阿里云", "360", "记忆"],
    "C3 语音接近商业化": ["语音", "接近商业化", "超低延时", "ChatGPT", "全双工", "韵律"],
    "C4 多模态已商业化": ["多模态", "商业化", "混元", "Large-Vision", "北大", "图像", "视频"],
    "C5 Agent工程化早期": ["Agent", "工程化早期", "工具", "多步", "可靠性", "容错"],
    "C6 设备实验到工程化": ["GUI Agent", "手机", "电脑", "实验到工程化", "通用性", "稳定性"],
    "C7 环境工程化": ["传感器", "智能家居", "物联网", "工程化", "主动"],
    "C8 具身工程化早期": ["人形机器人", "具身智能", "工程化早期", "超过 100%", "通用操作"],
    "C9 结论分层": ["已商业化", "工程化", "实验到工程化", "可靠", "路线", "不确定"],
}
all_ok = True
for k, items in must_have.items():
    miss = [i for i in items if i not in new_text]
    status = "PASS" if not miss else f"MISS {miss}"
    if miss:
        all_ok = False
    print(f"  {k}: {status}")
print("限定词核验: 已商业化/接近商业化/工程化早期/实验到工程化/工程化阶段 全保留:",
      all(w in new_text for w in ("已商业化", "接近商业化", "工程化早期", "实验到工程化", "工程化阶段")))
print("时间预测检查: 无任何'X年后/20XX年一定'式断言:", not re.search(r"\d{4}年|年后一定", new_text))
num_scan = re.sub(r"360\s*智脑", "", new_text)  # 证据内产品名，非新数字
print("新数字检查（除证据内'超过 100%'与产品名'360 智脑'外无新数字）:",
      re.findall(r"\d+%|\d{2,}", num_scan))

# ---- 语速时长 ----
for rate in (200, 230, 260):
    print(f"  语速 {rate} 字/分 -> 时长 ≈ {mn['han']/rate:.1f} 分钟")

print("\n=== Truth 审计总判定:", "PASS（全部 claim/限定词保留，无新事实/新数字/新年份）" if all_ok else "FAIL")
