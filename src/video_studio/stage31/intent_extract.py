"""Stage 3.1.2 确定性视觉意图提取层（主题无关）。

能力边界（诚实声明）：本层是"词库 + 启发式"，不具备真正的自然语言语义理解。
它只做：从当前镜头口播文本中识别视觉概念族（手机/时钟/办公室/夜景…）、
动作、抽象/隐喻/情绪/时间标记，并映射到通用视觉概念（英文检索词、概念域、
媒体偏好、查询阶梯）。不包含任何主题词表；JARVIS 等任何主题都不在此层出现。

优先级（用户裁决）：当前镜头口播语义 > shot purpose(role) > 上下文 > 视频主题 > 通用知识。
"""
from __future__ import annotations

import re

# ---- 通用视觉概念族（跨主题；绝不含具体视频主题先验）----
FAMILIES = {
    "手机": dict(core="smartphone", pos=["smartphone", "phone", "screen", "mobile", "app", "notification"],
                 lit=["smartphone screen notifications", "hands holding phone"],
                 con=["mobile app interface", "phone notification popup"],
                 met=["glowing phone screen night"], video=1),
    "电脑": dict(core="computer", pos=["computer", "laptop", "keyboard", "monitor", "screen", "desk", "typing"],
                 lit=["laptop keyboard typing", "computer screen office"],
                 con=["person working computer desk", "office monitor screen"],
                 met=["screen glow dark room"], video=1),
    "时钟": dict(core="time", pos=["clock", "watch", "time", "hourglass", "calendar", "schedule"],
                 lit=["clock watch time", "calendar schedule"],
                 con=["busy schedule calendar", "hourglass sand time"],
                 met=["clock ticking time pressure"], video=0),
    "办公室": dict(core="office", pos=["office", "desk", "workspace", "worker", "employee"],
                   lit=["office worker desk", "open office interior"],
                   con=["busy office people working", "cubicle office"],
                   met=["empty office late night"], video=1),
    "骑手": dict(core="delivery", pos=["delivery", "courier", "bicycle", "scooter", "street"],
                 lit=["food delivery courier bicycle", "scooter street delivery"],
                 con=["courier riding city street", "traffic street rush"],
                 met=["blur motion city street"], video=1),
    "人群": dict(core="crowd", pos=["crowd", "street", "people", "pedestrian", "rush"],
                 lit=["crowded street people", "city street pedestrians"],
                 con=["rush hour crowd walking", "busy crosswalk people"],
                 met=["motion blur crowd street"], video=1),
    "通知": dict(core="notification", pos=["notification", "alert", "badge", "popup", "message"],
                 lit=["smartphone notification alert", "message popup screen"],
                 con=["phone notifications many", "app badge alerts"],
                 met=["screen glow dark"], video=1),
    "眼睛": dict(core="eye", pos=["eye", "eyes", "closeup"],
                 lit=["human eye macro", "eye closeup dark"],
                 con=["tired eye closeup", "eye staring darkness"],
                 met=["eye reflection screen light"], video=0),
    "夜": dict(core="night", pos=["night", "city", "skyline", "dark", "lights", "street"],
               lit=["city skyline night", "street lights night"],
               con=["empty street night", "window night city"],
               met=["lonely street lamp night", "night city blur"], video=1),
    "疲惫": dict(core="fatigue", pos=["tired", "fatigue", "exhausted", "rest", "sleep", "head in hands"],
                 lit=["tired person resting", "exhausted worker desk"],
                 con=["person head in hands desk", "tired face closeup"],
                 met=["silhouette tired person window"], video=0),
    "奔跑": dict(core="chase", pos=["running", "chase", "rush", "hurry", "race"],
                 lit=["person running street", "rushing crowd"],
                 con=["man running stairs", "hurry commuters"],
                 met=["motion blur running"], video=1),
    "网": dict(core="net", pos=["net", "network", "mesh", "rope", "web"],
               lit=["net mesh closeup", "fishing net texture"],
               con=["tight net ropes", "web trap concept"],
               met=["net tightening abstract"], video=0),
    "学习": dict(core="study", pos=["book", "study", "reading", "library", "notebook", "student"],
                 lit=["books library study", "student reading book"],
                 con=["stack of books desk", "person studying night"],
                 met=["open book light"], video=0),
    "旅行": dict(core="travel", pos=["travel", "journey", "map", "luggage", "road", "train"],
                 lit=["travel map planning", "luggage journey"],
                 con=["road trip landscape", "train window travel"],
                 met=["endless road horizon"], video=1),
    "历史": dict(core="history", pos=["history", "ancient", "museum", "ruins", "old", "architecture"],
                 lit=["ancient ruins architecture", "museum artifacts"],
                 con=["old town historical street", "ancient building"],
                 met=["time eroded stone"], video=0),
    "机器人": dict(core="ai", pos=["robot", "ai", "artificial", "intelligence", "chatbot", "machine"],
                   lit=["humanoid robot", "chatbot interface"],
                   con=["ai assistant concept", "robot arm task"],
                   met=["circuit abstract"], video=1),
}

# 关键字 → 概念族（叙述文本子串匹配）
FAMILY_KEYS = {
    "手机": "手机", "电话": "手机", "屏幕": "手机", "通知": "通知", "红点": "通知",
    "消息": "通知", "弹出": "通知",
    "电脑": "电脑", "键盘": "电脑", "打字": "电脑",
    "时钟": "时钟", "时间": "时钟", "分钟": "时钟", "小时": "时钟", "日程表": "时钟",
    "日历": "时钟", "倒计时": "时钟",
    "办公室": "办公室", "写字楼": "办公室", "工位": "办公室",
    "骑手": "骑手", "外卖": "骑手", "闯红灯": "骑手",
    "人群": "人群", "街道": "人群", "路人": "人群", "通勤": "人群",
    "眼睛": "眼睛", "眨眼": "眼睛",
    "夜": "夜", "凌晨": "夜", "深夜": "夜", "夜景": "夜",
    "疲惫": "疲惫", "累": "疲惫", "喘": "疲惫", "忙": "疲惫",
    "奔跑": "奔跑", "追": "奔跑", "跑": "奔跑", "赶": "奔跑",
    "网": "网",
    "学习": "学习", "书": "学习", "课程": "学习", "坚持": "学习", "知识": "学习",
    "旅行": "旅行", "旅": "旅行", "远方": "旅行", "出发": "旅行",
    "历史": "历史", "古迹": "历史", "古": "历史", "博物馆": "历史",
    "机器人": "机器人", "AI": "机器人", "人工智能": "机器人", "语音助手": "机器人",
    "助手": "机器人", "聊天": "机器人",
}

ACTION_MARKERS = ["打开", "弹出", "点击", "发送", "奔跑", "闯", "行驶", "打字", "安排",
                  "录制", "举起", "递", "盯", "追", "滑动", "操作", "回复", "按下",
                  "启动", "运行", "抓取", "骑行"]
METAPHOR_MARKERS = ["像", "变成", "仿佛", "如同", "一张网", "越来越", "不是…而是", "而是"]
ABSTRACT_MARKERS = ["效率", "焦虑", "依赖", "坚持", "自由", "价值", "时间", "空间",
                    "意志", "习惯", "意义", "孤独", "迷茫", "压力", "选择"]
MOOD_MAP = {"疲惫": "fatigue", "迷茫": "lost", "孤独": "loneliness", "焦虑": "anxiety",
            "忙": "busy", "安静": "quiet", "温暖": "warm", "陌生": "unfamiliar"}
TIME_MAP = {"凌晨": "3am", "深夜": "late night", "早晨": "morning", "傍晚": "dusk",
            "一天": "day", "分钟": "minute", "小时": "hour", "夜晚": "night"}

# 通用错误域（跨主题的"垃圾域"，用于负向惩罚与搜索否定）
GLOBAL_NEG = ["space", "astronaut", "nasa", "spacecraft", "planet", "rocket",
              "sim card", "handset", "satellite", "vintage phone", "telephony"]

_ROLE_VIDEO = ("hook", "conclusion", "transition")


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def extract(narration: str, role: str = "body", purpose: str = "",
            duration_hint: float = 8.0) -> dict:
    """从单镜口播文本推导主题无关的视觉意图。"""
    text = _clean(narration)
    fams: list[dict] = []
    for key, fname in FAMILY_KEYS.items():
        if key.lower() in text.lower() and all(f["core"] != FAMILIES[fname]["core"]
                                               for f in fams):
            fams.append(FAMILIES[fname])
    if not fams:  # 兜底：无概念命中时按 role 给通用视觉
        fams.append(FAMILIES["办公室"] if role in ("body", "hook") else FAMILIES["夜"])

    pos: set = set()
    lit, con, met = [], [], []
    video_hint = 0
    for f in fams:
        pos.update(f["pos"])
        lit += f["lit"]
        con += f["con"]
        met += f["met"]
        video_hint = max(video_hint, f["video"])

    has_action = any(a in text for a in ACTION_MARKERS)
    has_metaphor = any(m in text for m in METAPHOR_MARKERS)
    has_abstract = any(a in text for a in ABSTRACT_MARKERS)

    if has_metaphor:
        abstraction = "metaphorical"
    elif has_abstract:
        abstraction = "conceptual"
    else:
        abstraction = "literal"

    if has_action or role in _ROLE_VIDEO:
        media = "video" if video_hint else "image"
    elif abstraction in ("conceptual", "metaphorical"):
        media = "image"
    else:
        media = "video" if video_hint else "image"

    mood = next((MOOD_MAP[k] for k in MOOD_MAP if k in text), "neutral")
    temporal = next((TIME_MAP[k] for k in TIME_MAP if k in text), "")
    subject = ", ".join(f["core"] for f in fams[:2])
    queries = [lit, con, met]
    concepts_negative = list(GLOBAL_NEG)
    rationale = (
        f"口播命中概念族: {', '.join(f['core'] for f in fams)}；"
        f"动作={has_action} 隐喻={has_metaphor} 抽象={has_abstract}；"
        f"role={role} → media={media}, abstraction={abstraction}")
    return {
        "subject": subject,
        "action": "；".join(a for a in ACTION_MARKERS if a in text) or f"showing {subject}",
        "object": subject,
        "environment": f["environment"] if (f := fams[0]).get("environment") else "",
        "concept": " | ".join(f["core"] for f in fams[:2]),
        "visual_relationship": "",
        "mood": mood,
        "temporal_context": temporal,
        "abstraction_level": abstraction,
        "preferred_media_type": media,
        "concepts_positive": sorted(pos),
        "concepts_negative": concepts_negative,
        "search_queries": queries,
        "avoid_queries": list(GLOBAL_NEG[:6]),
        "rationale": rationale,
    }
