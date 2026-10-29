import sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, "src")
from video_studio.tools.claim_structuring import build_research_brief
from video_studio.tools.content_planning import build_content_plan
from video_studio.tools.script_planning import build_script_blueprint
from video_studio.tools.narrative_generation import build_narrative_draft
from video_studio.tools.creator_style import apply_style
from video_studio.tools.visual_planning import build_production_plan

claim = "规模与成本：成年果蝇大脑约139,255个神经元与五千万个突触；人脑约860亿神经元、百万亿级突触；OpenWorm 模拟302个神经元的线虫跑了十余年；AI 芯片功耗突破1000瓦后，散热占数据中心电费四成以上"
ev = [
    {"url": "https://www.nature.com/articles/s8m-hd-01", "title": "从线虫到人脑的规模对比", "snippet": "", "body": "成年果蝇大脑包含约139,255个神经元与约五千万个突触；人脑约860亿神经元、突触按百万亿计；OpenWorm项目模拟仅302个神经元的线虫已运行十余年。"},
    {"url": "https://www.cas.cn/s8m/hd-02", "title": "规模数据汇总", "snippet": "", "body": "规模数据：果蝇139,255神经元、五千万突触；人脑860亿神经元、百万亿突触；线虫302神经元；AI芯片功耗可突破1000瓦。"},
    {"url": "https://news.cn/s8m/hd-03", "title": "数据中心散热成本", "snippet": "", "body": "数据中心成本：AI芯片功耗突破1000瓦后，散热成本占数据中心电费四成以上。"},
]
brief = build_research_brief(claim, ev)
plan = build_content_plan(brief)
bp = build_script_blueprint(plan, brief)
draft = build_narrative_draft(bp, brief, "bilibili")
styled = apply_style(draft, brief, "casual")
p = build_production_plan(styled, brief, "bilibili")
print("paragraphs:", len(styled["paragraphs"]), "| scenes:", len(p["scenes"]))
for s in p["scenes"]:
    print(f"  {s['scene_id']} [{s['role']:12s}] {s['visual_target'][:22]:24s} src={s['source_paragraphs']} emph={s['subtitle_emphasis'][:4]}")
print("facts in scenes:", sum(1 for s in p["scenes"] if s.get("fact_refs")))
# 视觉连串
run = maxrun = 0
prev = None
for s in p["scenes"]:
    v = s["visual_target"]
    run = run + 1 if v == prev else 1
    maxrun = max(maxrun, run)
    prev = v
print("max visual run:", maxrun)
print("OK")
