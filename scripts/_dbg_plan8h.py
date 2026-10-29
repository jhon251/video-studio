import sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, "src")
from video_studio.tools.claim_structuring import build_research_brief
from video_studio.tools.content_planning import build_content_plan

cases = [
    ("《黑镜》里有个地方叫圣朱尼佩罗，人死了，意识搬进服务器，永远活在1987年的海滩上",
     [{"url": "https://news.cn/a", "title": "黑镜解析", "snippet": "", "body": "《黑镜》圣朱尼佩罗一集中，意识被上传到服务器，故事发生在1987年的海滩。"}]),
    ("成年果蝇大脑连接组至今尚未完成绘制",
     [{"url": "https://news.cn/b", "title": "果蝇图谱", "snippet": "", "body": "2023年科学家已完成成年果蝇全脑连接组绘制。"}]),
    ("死后上传的法律地位是什么",
     [{"url": "https://law.gov.cn/c", "title": "数字人权", "snippet": "", "body": "法律对数字人权利尚无明确规定。"}]),
]
for claim, ev in cases:
    brief = build_research_brief(claim, ev)
    plan = build_content_plan(brief)
    print("=" * 60)
    print(plan["plan_text"])
    print("angles:", [a["angle"] for a in plan["angles"]])
    print("citations:", plan["brief_citations"]["cited_source_count"], "gaps:", plan["brief_citations"]["cited_gap_count"])
print("OK")
