import sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, "src")
from video_studio.tools.claim_structuring import build_research_brief
from video_studio.tools.content_planning import build_content_plan
from video_studio.tools.script_planning import build_all_platform_scripts, build_script_blueprint

claim = "2023年，科学家完成了成年果蝇的全脑连接组——十四万个神经元，每条连接都画了出来，发在《科学》上"
ev = [
    {"url": "https://news.cn/a", "title": "果蝇连接组", "snippet": "",
     "body": "2023年，科学家完成成年果蝇全脑连接组，包含十四万个神经元，发表于《科学》期刊。"},
    {"url": "https://acad.cn/b", "title": "神经图谱", "snippet": "",
     "body": "研究团队绘制了成年果蝇大脑图谱，识别十四万个神经元。"},
]
brief = build_research_brief(claim, ev)
plan = build_content_plan(brief)
bp = build_script_blueprint(plan, brief)
print("Blueprint sections:", [(s["role"], len(s["evidence_refs"]), len(s["facts"])) for s in bp["sections"]])
print("references:", [(r["index"], r["source_tier"]) for r in bp["references"]])
scripts = build_all_platform_scripts(plan, brief)
print("=" * 60)
print(scripts["bilibili"]["script_text"])
print("=" * 60)
print(scripts["shipinhao"]["script_text"][:400])
print("OK")
