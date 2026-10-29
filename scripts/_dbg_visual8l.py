import sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, "src")
from video_studio.tools.claim_structuring import build_research_brief
from video_studio.tools.content_planning import build_content_plan
from video_studio.tools.script_planning import build_script_blueprint
from video_studio.tools.narrative_generation import build_narrative_draft
from video_studio.tools.creator_style import apply_style
from video_studio.tools.visual_planning import build_all_platform_plans

claim = "2023年，科学家完成了成年果蝇的全脑连接组——十四万个神经元，每条连接都画了出来，发在《科学》上"
ev = [
    {"url": "https://news.cn/a", "title": "果蝇连接组", "snippet": "",
     "body": "2023年，科学家完成成年果蝇全脑连接组，包含十四万个神经元，发表于《科学》期刊。"},
]
brief = build_research_brief(claim, ev)
plan = build_content_plan(brief)
bp = build_script_blueprint(plan, brief)
draft = build_narrative_draft(bp, brief, "bilibili")
styled = apply_style(draft, brief, "casual")
plans = build_all_platform_plans(styled, brief)
print(plans["bilibili"]["plan_text"][:1100])
print("=" * 40)
print("shipinhao total:", plans["shipinhao"]["total_duration_hint"],
      "| bilibili total:", plans["bilibili"]["total_duration_hint"])
print("OK")
