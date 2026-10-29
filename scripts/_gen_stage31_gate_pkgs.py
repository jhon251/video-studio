"""生成封包前 Gate 的 3 个全新主题测试包 + 44 镜全量 JARVIS 计时包。"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "stage31_testpkgs"


def sc(sid, role, beat, vt, broll, emph, dur, narration):
    return {"scene_id": sid, "role": role, "beat": beat, "visual_target": vt,
            "broll_requirement": broll, "subtitle_emphasis": emph,
            "duration_hint": dur, "evidence_refs": [], "narration": narration}


BODY = "探索过程"
NEW_THEMES = {
    "yuan": ("袁隆平与杂交水稻", [
        sc("S01", "hook", "悬念提问", "口播 + 大字标题卡", "悬念相关快切素材（2-3 镜）", ["水稻"], "10s",
           "一个农民模样的科学家，用一粒种子，喂饱了几亿人。"),
        sc("S02", "body", BODY, "数据可视化 + 证据截图", "概念动画", ["稻田"], "9s",
           "风吹过稻田，稻穗沉甸甸地弯下来，这是杂交水稻最普通的画面。"),
        sc("S03", "body", BODY, "实拍素材 + 数据角标", "证据来源截图", ["试验田"], "9s",
           "袁隆平在试验田里弯着腰，一株一株地找那株天然雄性不育株。"),
        sc("S04", "body", BODY, "实拍素材 + 数据角标", "证据来源截图", ["实验室"], "8s",
           "水稻开花的时间只有几个小时，育种的人必须守在田边，和时间赛跑。"),
        sc("S05", "body", BODY, "概念动画 + 口播", "概念动画", ["粮食"], "9s",
           "粮食安全不是一句口号，是碗里实实在在的每一粒米。"),
        sc("S06", "conclusion", "余韵收束", "结论大字卡 + 落版", "呼应开场画面", ["稻田"], "8s",
           "他把一生种进了稻田，直到最后一年还在想着产量。"),
        sc("S07", "body", BODY, "实拍素材 + 数据角标", "证据来源截图", ["杂交"], "8s",
           "杂交水稻的推广，让许多国家的稻田第一次有了丰收的颜色。"),
        sc("S08", "conclusion", "收束回应", "结论口播 + 呼应画面", "呼应开场画面", ["种子"], "9s",
           "一粒种子改变世界的说法，在他身上不是比喻。"),
    ]),
    "freedom": ("什么是真正的自由？", [
        sc("S01", "hook", "悬念提问", "口播 + 大字标题卡", "悬念相关快切素材（2-3 镜）", ["自由"], "10s",
           "如果明天你什么都不用做，你会比今天更自由吗？"),
        sc("S02", "body", BODY, "数据可视化 + 证据截图", "概念动画", ["选择"], "9s",
           "自由常常被说成想做什么就做什么，可真正难的是想不做什么，就能不做什么。"),
        sc("S03", "body", BODY, "实拍素材 + 数据角标", "证据来源截图", ["鸟"], "8s",
           "笼子里的鸟以为窗户就是天空。"),
        sc("S04", "body", BODY, "实拍素材 + 数据角标", "证据来源截图", ["奔跑"], "8s",
           "有人在旷野里奔跑，却逃不出自己定的规矩。"),
        sc("S05", "body", BODY, "概念动画 + 口播", "概念动画", ["边界"], "9s",
           "自由不是没有边界，是边界由你自己画。"),
        sc("S06", "conclusion", "余韵收束", "结论大字卡 + 落版", "呼应开场画面", ["远方"], "8s",
           "真正的自由，是选完之后不后悔。"),
        sc("S07", "body", BODY, "实拍素材 + 数据角标", "证据来源截图", ["天空"], "8s",
           "抬头看天空的人，未必比低头走路的人自由。"),
        sc("S08", "conclusion", "收束回应", "结论口播 + 呼应画面", "呼应开场画面", ["选择"], "9s",
           "自由是一种能力，不是一种状态。"),
    ]),
    "coffee": ("一杯咖啡从豆子到杯子的旅程", [
        sc("S01", "hook", "悬念提问", "口播 + 大字标题卡", "悬念相关快切素材（2-3 镜）", ["咖啡"], "10s",
           "你早上喝的那杯咖啡，出发的地方是一片海拔两千米的山坡。"),
        sc("S02", "body", BODY, "数据可视化 + 证据截图", "概念动画", ["咖啡豆"], "8s",
           "红色的咖啡果挂在枝头，摘下来只是第一步。"),
        sc("S03", "body", BODY, "实拍素材 + 数据角标", "证据来源截图", ["烘焙"], "9s",
           "烘焙炉里，豆子在高温下爆裂，颜色从青绿变成深棕。"),
        sc("S04", "body", BODY, "实拍素材 + 数据角标", "证据来源截图", ["研磨"], "8s",
           "研磨机把豆子磨成粉，香气在几秒钟内充满整个房间。"),
        sc("S05", "body", BODY, "概念动画 + 口播", "概念动画", ["冲泡"], "9s",
           "热水穿过咖啡粉，萃取出来的褐色液体，就是时间的味道。"),
        sc("S06", "conclusion", "余韵收束", "结论大字卡 + 落版", "呼应开场画面", ["拉花"], "8s",
           "咖啡师手腕一抖，杯子里开出一朵花。"),
        sc("S07", "body", BODY, "实拍素材 + 数据角标", "证据来源截图", ["烘焙"], "8s",
           "从豆子到杯子，最快也要几个月，最慢要等一整年。"),
        sc("S08", "conclusion", "收束回应", "结论口播 + 呼应画面", "呼应开场画面", ["旅程"], "9s",
           "每一杯咖啡，都是一段被压缩的旅程。"),
    ]),
}

# ---- 44 镜全量 JARVIS（v2 稿段落文本按 PRE_PRODUCTION 映射分配到各镜）----
V2_PARAS = {
    "开头": "钢铁侠里的 JARVIS，大概是最多人想要的 AI：早上把你叫醒，顺手报一遍今天的日程和股价；你说一句帮我查点东西，它几秒钟就把整理好的结果念给你听。真把 JARVIS 拆开，你会发现它其实是八项技术叠在一起，进度完全不一样。什么时候才能真正拥有一个这样的 AI 管家？",
    "会聊天": "主流大模型能跟你多轮对话，你抛给它一个话题，它能接住，还能记住你前面说了什么。但这里有个挺要命的问题：它会一本正经地胡说八道，就是大家常说的幻觉。另外还有事实一致性的毛病，聊着聊着，前面讲过的数字，后面可能就悄悄变了。能聊，和聊得靠谱，是两码事。",
    "能记住你": "真正麻烦的地方，其实在后面。JARVIS 之所以是你的 JARVIS，不是它多会聊，而是它记得你：你的习惯、你的偏好、你上周随口提过的事。记忆存储的框架已经出来了，阿里云的百炼、360 智脑，都能给 AI 挂一个长期记忆。但跨会话的稳定记忆还没解决。",
    "能听见你": "实时语音交互现在已经相当接近商业化了：超低延时的对话引擎有了，ChatGPT 也把语音直接做进了对话框。但全双工打断这一关没过；声音里的情绪、语气、韵律，机器也读不出来。一到像人一样开口对话，还差着一层。",
    "能看见": "多模态视觉理解，今天也已经商业化了。腾讯的混元 Large-Vision、北大开源的多模态模型，识别图像、处理视频任务，都没问题。但认出一张图，和看懂你眼前正在发生什么，是两回事。",
    "能自己做事": "现在的 AI Agent，能调用工具、能跑多步流程，你交给它一个任务，它会自己拆解、一步一步执行。但它还在工程化早期，可靠性、长链路的容错，是最大的限制。",
    "能操作你的设备": "现在已经有 GUI Agent 了，能操作手机界面、电脑界面，一句话让它发个红包、填个表，都能做。但它还卡在实验到工程化之间，通用性和稳定性都有缺陷，换个界面、换个版本，它可能就懵了。",
    "能理解环境": "JARVIS 得知道你房间里的灯、空调、门锁现在是什么状态，甚至主动帮你调。传感器、智能家居、物联网，都能给它喂数据。但有数据，和主动理解环境，是两回事。",
    "能拥有身体": "人形机器人、具身智能，这几年产业增长非常快。人形机器人的市场年复合增速，有机构给到超过 100%。但通用操作能力才是真正的瓶颈。让机器人拿起一个杯子递给你，对机器人来说，是全世界最难的问题之一。",
    "结尾": "聊天、语音、视觉，已商业化；长期记忆、环境感知，还在工程化；Agent、设备控制、具身执行，都还卡在实验到工程化早期。JARVIS 最难的，是整合，是可靠性。答案不是一个年份，而这条链什么时候能走通，现在还不确定。这件事，还远。",
}
SHOT_SECTION = {
    **{f"S{i:02d}": "开头" for i in range(1, 5)},
    **{f"S{i:02d}": "会聊天" for i in range(5, 9)},
    **{f"S{i:02d}": "能记住你" for i in range(9, 14)},
    **{f"S{i:02d}": "能听见你" for i in range(14, 18)},
    **{f"S{i:02d}": "能看见" for i in range(18, 22)},
    **{f"S{i:02d}": "能自己做事" for i in range(22, 26)},
    **{f"S{i:02d}": "能操作你的设备" for i in range(26, 30)},
    **{f"S{i:02d}": "能理解环境" for i in range(30, 34)},
    **{f"S{i:02d}": "能拥有身体" for i in range(34, 38)},
    **{f"S{i:02d}": "结尾" for i in range(38, 45)},
}


def main():
    for key, (title, scenes) in NEW_THEMES.items():
        d = OUT / key
        d.mkdir(parents=True, exist_ok=True)
        (d / "shotlist.json").write_text(
            json.dumps({"scenes": scenes, "references": []}, ensure_ascii=False, indent=2),
            encoding="utf-8")
        vo = "\n\n".join(f"【{s['scene_id']}】{s['narration']}" for s in scenes)
        (d / "V2_FINAL_SCRIPT_JARVIS.md").write_text(f"# {title}\n\n{vo}\n", encoding="utf-8")
        print(f"{key}: {len(scenes)} 镜")

    # 44 镜全量 JARVIS：读 2.x shotlist 骨架，逐镜填 narration
    src = json.loads((ROOT / "output" / "production_002" / "shotlist.json").read_text(encoding="utf-8"))
    full = []
    for s in src["scenes"]:
        sid = s["scene_id"]
        sec = SHOT_SECTION.get(sid, "结尾")
        full.append({**s, "narration": V2_PARAS[sec]})
    d = OUT / "jarvis_full"
    d.mkdir(parents=True, exist_ok=True)
    (d / "shotlist.json").write_text(
        json.dumps({"scenes": full, "references": src.get("references", [])},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    (d / "V2_FINAL_SCRIPT_JARVIS.md").write_text(
        "# JARVIS 44 镜全量（计时测试）\n", encoding="utf-8")
    print(f"jarvis_full: {len(full)} 镜")


if __name__ == "__main__":
    main()
