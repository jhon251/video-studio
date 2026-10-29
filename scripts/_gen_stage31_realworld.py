"""最终真实制作验收：生成《珊瑚礁正在消失》测试包（20 镜，测试数据）。"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "stage31_realworld" / "coral"


def sc(sid, role, vt, broll, dur, narration):
    return {"scene_id": sid, "role": role, "beat": "探索过程", "visual_target": vt,
            "broll_requirement": broll, "subtitle_emphasis": [],
            "duration_hint": dur, "evidence_refs": [], "narration": narration}


BODY, HOOK, CONC = "body", "hook", "conclusion"
H = "口播 + 大字标题卡"
B1 = "实拍素材 + 数据角标"
B2 = "概念动画 + 口播"
C1 = "结论大字卡 + 落版"
C2 = "结论口播 + 呼应画面"

SCENES = [
    sc("S01", HOOK, H, "悬念相关快切素材（2-3 镜）", "10s", "在海水下面，有一座正在慢慢褪色的城市。"),
    sc("S02", BODY, B2, "概念动画", "9s", "珊瑚不是石头，也不是植物，而是千千万万只小虫子的家。"),
    sc("S03", BODY, B1, "证据来源截图", "9s", "潜水员下到十米深的地方，眼前是大片雪白的珊瑚骨架。"),
    sc("S04", BODY, B1, "证据来源截图", "9s", "健康的珊瑚礁是彩色的，鱼群像彩带一样从缝隙里穿过去。"),
    sc("S05", BODY, B1, "证据来源截图", "8s", "白化不是死亡，而是珊瑚把体内的藻类赶了出去。"),
    sc("S06", BODY, B2, "概念动画", "9s", "海水温度只要升高一两度，珊瑚就会开始发烧。"),
    sc("S07", BODY, B1, "证据来源截图", "8s", "海洋吸收了大气里多余的二氧化碳，海水正在变酸。"),
    sc("S08", CONC, C1, "呼应开场画面", "8s", "珊瑚礁只占海底不到百分之一，却养活了四分之一的海洋生物。"),
    sc("S09", BODY, B1, "证据来源截图", "9s", "海龟从白化的珊瑚旁游过，像穿过一片雪的森林。"),
    sc("S10", BODY, B1, "证据来源截图", "8s", "科学家用绳子把珊瑚苗绑在架子上，像在水下种树。"),
    sc("S11", BODY, B2, "概念动画", "9s", "珊瑚修复是一场和温度赛跑的接力。"),
    sc("S12", BODY, B1, "证据来源截图", "8s", "渔民的网掠过水面，海面之下的变化却很少有人看见。"),
    sc("S13", CONC, C2, "呼应开场画面", "9s", "如果珊瑚消失了，很多人的饭碗也会跟着消失。"),
    sc("S14", BODY, B1, "证据来源截图", "8s", "小丑鱼躲在海葵里，海葵也在慢慢失去颜色。"),
    sc("S15", BODY, B1, "证据来源截图", "9s", "洋流带来营养，也带来越来越热的海水。"),
    sc("S16", BODY, B2, "概念动画", "8s", "海洋不是离我们很远的地方，它每天都在改变天气。"),
    sc("S17", BODY, B1, "证据来源截图", "8s", "有些珊瑚挺过了白化，重新长回了颜色。"),
    sc("S18", CONC, C1, "呼应开场画面", "9s", "珊瑚礁的生死，取决于我们接下来十年的选择。"),
    sc("S19", BODY, B1, "证据来源截图", "8s", "海边的小孩第一次戴上潜水面镜，看见了水下另一个世界。"),
    sc("S20", CONC, C2, "呼应开场画面", "9s", "那是一座会呼吸的城市，而它正在等待降温。"),
]

d = OUT
d.mkdir(parents=True, exist_ok=True)
(d / "shotlist.json").write_text(
    json.dumps({"scenes": SCENES, "references": []}, ensure_ascii=False, indent=2),
    encoding="utf-8")
vo = "\n\n".join(f"【{s['scene_id']}】{s['narration']}" for s in SCENES)
(d / "V2_FINAL_SCRIPT_JARVIS.md").write_text(
    "# 珊瑚礁正在消失\n\n" + vo + "\n", encoding="utf-8")
print(f"coral: {len(SCENES)} 镜 -> {d}")
