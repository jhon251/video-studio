import sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, "src")
from video_studio.tools.claim_structuring import build_research_brief
from video_studio.tools.content_planning import build_content_plan
from video_studio.tools.script_planning import build_script_blueprint
from video_studio.tools.narrative_generation import build_narrative_draft, build_all_narrative_drafts

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
draft = build_narrative_draft(bp, brief, "bilibili")
print(draft["draft_text"])
print("=" * 50)
drafts = build_all_narrative_drafts(bp, brief)
print("shipinhao paragraphs:", len(drafts["shipinhao"]["paragraphs"]),
      "| bilibili paragraphs:", len(drafts["bilibili"]["paragraphs"]))
print("OK")
