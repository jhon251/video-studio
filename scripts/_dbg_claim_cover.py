"""诊断 S2/S4 claim覆盖 FAIL：逐阶段定位缺失实体（只读诊断，不改任何代码）。"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from video_studio.tools.claim_structuring import build_research_brief          # noqa: E402
from video_studio.tools.content_planning import build_content_plan             # noqa: E402
from video_studio.tools.script_planning import build_script_blueprint          # noqa: E402
from video_studio.tools.narrative_generation import build_narrative_draft      # noqa: E402
from video_studio.tools.creator_style import apply_style                       # noqa: E402
from video_studio.production2x import run_production                           # noqa: E402

EVID_SC_HD = [
    {"url": "https://www.nature.com/articles/s8m-hd-01", "title": "规模对比", "snippet": "",
     "body": "成年果蝇大脑包含约139,255个神经元与约五千万个突触；人脑约860亿神经元、突触按百万亿计；OpenWorm项目模拟仅302个神经元的线虫已运行十余年。"},
    {"url": "https://www.cas.cn/s8m/hd-02", "title": "规模数据", "snippet": "",
     "body": "规模数据：果蝇139,255神经元、五千万突触；人脑860亿神经元、百万亿突触；线虫302神经元；AI芯片功耗可突破1000瓦。"},
    {"url": "https://news.cn/s8m/hd-03", "title": "散热成本", "snippet": "",
     "body": "数据中心成本：AI芯片功耗突破1000瓦后，散热成本占数据中心电费四成以上。"},
    {"url": "https://www.tmtpost.com/s8m/hd-04", "title": "算力散热", "snippet": "",
     "body": "从302个神经元的线虫到860亿神经元的人脑，规模差距巨大；AI芯片1000瓦功耗的散热挑战。"},
    {"url": "https://www.huxiu.com/s8m/hd-05", "title": "OpenWorm", "snippet": "",
     "body": "OpenWorm用302个神经元模拟线虫跑了十余年仍未完全达成；人脑860亿神经元的模拟更是天文数字。"},
    {"url": "https://www.sohu.com/a/s8m/hd-06", "title": "数量对比", "snippet": "",
     "body": "果蝇139,255神经元、人脑860亿神经元、线虫302神经元——数字对比。"},
]
CLAIM = ("规模与成本：成年果蝇大脑约139,255个神经元与五千万个突触；人脑约860亿神经元、"
         "百万亿级突触；OpenWorm 模拟302个神经元的线虫跑了十余年；"
         "AI 芯片功耗突破1000瓦后，散热占数据中心电费四成以上")

brief = build_research_brief(CLAIM, EVID_SC_HD)
struct = brief["structure"]
print("== 结构实体列表 ==")
print(struct.get("entities"))

plan = build_content_plan(brief)
bp = build_script_blueprint(plan, brief)
draft = build_narrative_draft(bp, brief, "bilibili")
styled = apply_style(draft, brief, "casual", final=True)

print("\n== draft（样式前）段落中实体出现情况 ==")
for e in struct.get("entities", []):
    hits = [p["text"][:60] for p in draft["paragraphs"] if e in p["text"]]
    print(f"  [{e}] 出现 {len(hits)} 次", hits[:2])

print("\n== styled（样式后）段落中实体出现情况 ==")
for e in struct.get("entities", []):
    hits = [p["text"][:60] for p in styled["paragraphs"] if e in p["text"]]
    print(f"  [{e}] 出现 {len(hits)} 次", hits[:2])

# 大小写变体检查
print("\n== 大小写变体（styled 全文）==")
joined = "\n".join(p["text"] for p in styled["paragraphs"])
for e in struct.get("entities", []):
    var = {"小写 e": e in joined, "首字母大写": e.capitalize() in joined,
           "全大写": e.upper() in joined}
    print(f"  [{e}] {var}")

pkg = run_production({"video": {"title": "规模与成本", "claims": [
    {"claim_text": CLAIM, "evidence": EVID_SC_HD}]},
    "style": "casual", "platforms": ["bilibili"]})
print("\n== 最终 balance ==")
print(json.dumps(pkg["balance"], ensure_ascii=False))
scenes = pkg["plans"]["bilibili"]["plan"]["scenes"]
for e in struct.get("entities", []):
    hits = [s["scene_id"] for s in scenes if e in s["script_text"]]
    print(f"  entity [{e}] 在镜头文本出现: {hits or '无'}")
