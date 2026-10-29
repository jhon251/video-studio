import sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, "src")
from video_studio.tools.claim_structuring import decompose_claim, build_research_brief

samples = [
    "《黑镜》里有个地方叫圣朱尼佩罗，人死了，意识搬进服务器，永远活在1987年的海滩上",
    "2023年，科学家完成了成年果蝇的全脑连接组——十四万个神经元，每条连接都画了出来，发在《科学》上",
    "杭州互联网法院审理认为虚拟数字人不是自然人、不具有作者身份",
    "死后上传的法律地位是什么",
    "构建由人类细胞驱动的生物电脑包括三个步骤：皮肤细胞转化为干细胞、培养为神经元团块类器官、连接至电极",
]
for c in samples:
    d = decompose_claim(c)
    print("=" * 60)
    print("CLAIM:", c)
    print("type:", d["claim_type"], "| entities:", d["entities"])
    print("qualifiers:", d["qualifiers"], "| numbers:", d["numbers_years"])
    print("sub_claims:", d["sub_claims"])
    print("flags:", d["flags"])

ev = [{"url": "https://news.cn/a", "title": "果蝇连接组", "snippet": "",
       "body": "2023年，科学家完成成年果蝇全脑连接组，包含十四万个神经元，发表于《科学》。",
       "source_quality": {"tier": "mainstream_media"}}]
print("=" * 60)
print(build_research_brief(samples[1], ev)["brief_text"])
print("OK")
