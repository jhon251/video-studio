"""JARVIS 生产：curation + 构建 input.json（据 research.json 真实证据，保留 provenance）。"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "production_002"
research = json.loads((OUT / "research.json").read_text(encoding="utf-8"))

# 每维度保留的候选索引（剔除误命中/目录站/弱相关）
KEEP = {
    "nlp": [0, 1, 2],          # 去掉 [3] AI伴侣上瘾（偏离）
    "memory": [0, 1, 2, 3],
    "voice": [1, 2, 3],        # 去掉 [0] flightadsb 航班（误命中）
    "multimodal": [0, 1, 2, 3],
    "agent": [2, 3],           # 去掉 [0][1] AI 工具目录站
    "device": [0, 1, 2, 3],
    "perception": [2, 3],      # 去掉 [0][1] 排行榜/目录站
    "embodied": [0, 1, 2, 3],
}

CLAIMS = [
    ("C0-core", "什么时候，一个普通人才真正拥有类似《钢铁侠》JARVIS 的私人 AI 助手？", None),
    ("C1-nlp", "自然语言理解与多轮对话已实现商业化，主流大模型能流畅多轮对话，但仍存在幻觉与事实一致性问题。", "nlp"),
    ("C2-memory", "AI 长期记忆与用户建模处于工程化早期，已出现记忆存储框架（阿里云百炼、360 智脑等），但跨会话的稳定个性化记忆仍在探索。", "memory"),
    ("C3-voice", "实时语音交互已接近商业化，超低延时对话引擎与一体化语音交互出现，但全双工打断与情感韵律仍有限制。", "voice"),
    ("C4-multimodal", "多模态视觉理解已商业化，图像与视频理解模型（如腾讯混元 Large-Vision、北大开源模型）可处理视觉任务。", "multimodal"),
    ("C5-agent", "AI Agent 自主任务执行处于工程化早期，能进行工具调用与多步流程，但可靠性、长链路容错仍是主要限制。", "agent"),
    ("C6-device", "AI 控制计算机与现实设备处于实验到工程化阶段，GUI Agent 可操作手机与电脑界面，但通用性与稳定性仍有缺陷。", "device"),
    ("C7-perception", "实时环境感知处于工程化阶段，传感器与智能家居物联网可提供环境数据，但主动环境理解尚未成熟。", "perception"),
    ("C8-embodied", "机器人身体与现实世界执行处于工程化早期，人形机器人与具身智能产业快速增长，但通用操作能力仍是瓶颈。", "embodied"),
    ("C9-conclusion", "从八项能力证据看，对话、语音、多模态已商业化，长期记忆、环境感知工程化中，Agent、设备控制、具身执行仍处实验或工程化早期；JARVIS 级私人助手的完整形态尚无可靠路线与年份，属高不确定性预测。", None),
]

seen_urls = set()
claims_out = []
curation = {}
for cid, claim_text, dim in CLAIMS:
    if dim is None:
        # 核心问题取 nlp 首源；结论取"整体趋势"源（具身产业趋势 + Agent 落地），显式指定、不参与去重
        if cid == "C9-conclusion":
            ev = [research["embodied"]["usable"][0], research["agent"]["usable"][2]]
        else:
            ev = [research["nlp"]["usable"][0]]
            seen_urls.add(ev[0]["url"])
    else:
        ev = []
        for i in KEEP[dim]:
            u = research[dim]["usable"][i]
            if u["url"] not in seen_urls:
                ev.append(u)
                seen_urls.add(u["url"])
    claims_out.append({"claim_text": claim_text,
                       "evidence": [{"url": e["url"], "title": e["title"], "snippet": e["snippet"],
                                     "body": e["body"]} for e in ev]})
    curation[cid] = {"kept": len(ev), "urls": [e["url"][:60] for e in ev]}

payload = {
    "video": {"title": "什么时候才能拥有真正的 JARVIS？", "claims": claims_out},
    "style": "casual",
    "platforms": ["bilibili", "youtube", "shipinhao", "gongzhonghao"],
    "target_seconds": 660,
}
(OUT / "input.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
(OUT / "curation.json").write_text(json.dumps({
    "claim_count": len(claims_out), "evidence_total": sum(len(c["evidence"]) for c in claims_out),
    "per_claim": curation}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"claims {len(claims_out)} | evidence 总数 {sum(len(c['evidence']) for c in claims_out)}")
for cid, cu in curation.items():
    print(f"  {cid}: kept {cu['kept']} 条")
print(f"input.json -> {OUT/'input.json'}")
