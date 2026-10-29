"""把 config.sao10.json 的文案写手 mock 响应升级为新规范完整格式（示范）。"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
cfg_path = ROOT / "config" / "config.sao10.json"

NEW_FORMAT_FIELDS = {
    "topic_understanding": "《刀剑神域》的完全潜行不是'高级VR'，而是双向神经交互——真正的问题是人类离'意识进入游戏'还有多远的工程与伦理距离。",
    "core_viewpoint": "视觉沉浸已经商品化，身体沉浸正在路上，意识沉浸没有时间表；人们高估了VR的接近程度，也低估了脑机接口已经取得的真实进展。",
    "narrative_route": "动画场景切入 → 定义问题（双向神经交互）→ 视觉线历史 → 身体线（触觉/运动）→ 神经线（BCI原理→人体试验）→ 行业态度 → 四道墙 → 伦理 → 三情景预测 → 回扣问题。",
    "titles": [
        "《刀剑神域》的完全潜行，现实还要多久？",
        "戴上头盔就能进游戏？SAO 距离现实还差三道墙",
        "Neuralink 之后，我们离艾恩葛朗特还有多远",
        "为什么 2026 年了，'完全潜行'依然没有时间表",
        "从达摩克利斯之剑到脑机接口：一部完全潜行简史",
    ],
    "opening_alternatives": [
        "2022年，桐人戴上NerveGear，说了一句Link Start，意识就沉进了艾恩葛朗特。此后二十年，完全潜行成了无数观众心里的一个坐标。但坐标归坐标，现实归现实。",
        "很多人以为，完全潜行差的只是一块更轻的头显。但如果把时间线往前拉六十年，你会发现真正卡住我们的，从来不是屏幕。",
        "一家公司把芯片植入了人脑，受试者用意念下棋。这件事听起来像动画剧情，但它的用途，恰恰离动画最远。",
    ],
    "fact_risks": [
        "Neuralink 首例人体植入（2024年1月）为机构自报信息，长期安全数据有限，需标注来源时效",
        "'完全潜行无公认时间表'属综述性判断，不同研究者乐观程度不一",
        "三情景预测（2030s/2040s）为本视频推断，需在口播中明确'预测非承诺'，避免被截取为事实",
        "Gabe Newell 表态为企业愿景而非技术路线图，引用时需保留'愿景'限定语",
    ],
    "recommended_title": "《刀剑神域》的完全潜行，现实还要多久？",
    "recommended_opening": "2022年，桐人戴上NerveGear，说了一句Link Start，意识就沉进了艾恩葛朗特。此后二十年，完全潜行成了无数观众心里的一个坐标。但坐标归坐标，现实归现实。",
}


def main() -> None:
    config = json.loads(cfg_path.read_text(encoding="utf-8"))
    script_resp = config["llm"]["mock"]["responses"]["文案写手"]
    script_resp.update(NEW_FORMAT_FIELDS)
    cfg_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已升级文案响应为新规范格式（+{len(NEW_FORMAT_FIELDS)} 个字段）")


if __name__ == "__main__":
    main()
