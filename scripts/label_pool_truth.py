"""Stage 8B.1：label-first 重建 dev 口径。

- 保留原始 world truth（s8_claim_labels.json 不动）；
- 新增 evidence-sufficiency truth（s8_pool_truth.json）：回答"在当前 Evidence Pool 中，
  该 Claim 能否被现有证据充分支持/反驳"，而非"现实是否为真"；
- 新增 11 条构造 Claim（s8_dev2_samples.json，Evidence 全部取自真实采集页面，
  与冻结集去重）：DIRECT×4（含 anchor+互补）、CONTRADICTS×3（数字精确矛盾/谓词否定/存在否定）、
  NO_SUFFICIENT×2（topic-only 池）、PARTIAL×2（数字近似冲突/时间冲突）。
"""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# ---------- 50 Claim 的 pool truth（label-first，按池内证据能力标注） ----------
POOL_TRUTH = {
    # ASSERTION + 池内命题证据
    "c_551": ("PARTIAL_SUPPORT", "维基/影评多源确认剧集与设定，限定词欠背书"),
    "c_562": ("PARTIAL_SUPPORT", "MIT/显微观点多源确认连接组，但年份/期刊限定与池内证据冲突"),
    "c_563": ("PARTIAL_SUPPORT", "新华网锚点覆盖主体与最大，'目前'未背书"),
    "c_568": ("PARTIAL_SUPPORT", "清华/虎嗅/腾讯锚点一致，突触数量级与600T为近似冲突"),
    "c_569": ("PARTIAL_SUPPORT", "果蝇上传多源，数字(十四万/五数量级)未背书"),
    "c_570": ("PARTIAL_SUPPORT", "维基/煎蛋/安全内参确认 302 神经元与项目史，但无媒体级锚点来源"),
    "c_574": ("PARTIAL_SUPPORT", "突触/胶质子题多源，清单命题无锚点"),
    "c_582": ("PARTIAL_SUPPORT", "休谟/果壳确认思想实验存在"),
    "c_583": ("PARTIAL_SUPPORT", "果壳/NYT讨论上传-副本问题（修辞句规则态 CONTEXT 之外按池标 PARTIAL）"),
    "c_589": ("PARTIAL_SUPPORT", "litianyi/记忆页部分覆盖"),
    "c_590": ("PARTIAL_SUPPORT", "PanSci/分身讨论部分覆盖"),
    "c_600": ("PARTIAL_SUPPORT", "法律空白概念多源"),
    "c_603": ("PARTIAL_SUPPORT", "病理扫描/科技进展帖仅主题相邻"),
    # ASSERTION 但池内仅 topic-only / 无核心支持
    "c_555": ("NO_SUFFICIENT_EVIDENCE", "脑机接口新闻仅主题相关，无命题证据"),
    "c_559": ("IRRELEVANT", "池内为时政/翻译等无关页"),
    "c_561": ("NO_SUFFICIENT_EVIDENCE", "纪委/手机扫描/OCT 为同形词页面"),
    "c_564": ("IRRELEVANT", "池内为 UN/UCLA/预算案"),
    "c_571": ("NO_SUFFICIENT_EVIDENCE", "神经元百科/BBC/测量页仅词面"),
    "c_572": ("IRRELEVANT", "CAN总线/邮递员问题同形词页面"),
    "c_576": ("IRRELEVANT", "Gmail/AWS/抚养费"),
    "c_579": ("IRRELEVANT", "英伟达投资视频"),
    "c_580": ("IRRELEVANT", "GSoC/UCLA"),
    "c_581": ("NO_SUFFICIENT_EVIDENCE", "技术哲学维基仅主题相关"),
    "c_584": ("IRRELEVANT", "党史/哲学史页面无关"),
    "c_585": ("IRRELEVANT", "数学连续性页面同形词"),
    "c_586": ("IRRELEVANT", "文革两派页面同形词"),
    "c_593": ("IRRELEVANT", "电商/Steam 页面对象不同"),
    "c_595": ("IRRELEVANT", "定价概念/阿里云对象不同"),
    "c_607": ("IRRELEVANT", "自律帖/播客/翻译页"),
    "c_609": ("IRRELEVANT", "建筑/壁画/绘画页同形词"),
    # 非 ASSERTION（问句/叙事/修辞/第X步/对照构式）→ 规则态 CONTEXT_ONLY
    "c_552": ("PARTIAL_SUPPORT", "维基 Underworld 设定页主题相关（规则态不受类型帽子影响）"),
    "c_553": ("CONTEXT_ONLY", "影视叙事句"),
    "c_556": ("CONTEXT_ONLY", "第X步定义句"),
    "c_557": ("CONTEXT_ONLY", "第X步定义句"),
    "c_558": ("CONTEXT_ONLY", "第X步定义句"),
    "c_560": ("CONTEXT_ONLY", "过渡叙事句"),
    "c_565": ("CONTEXT_ONLY", "对照/否定构式句"),
    "c_567": ("CONTEXT_ONLY", "问句"),
    "c_573": ("CONTEXT_ONLY", "不是A而是B 构式句"),
    "c_578": ("DIRECT_SUPPORT", "经济日报锚点+钛媒体/华尔街多独立源，全要素覆盖"),
    "c_587": ("CONTEXT_ONLY", "叙事句"),
    "c_588": ("CONTEXT_ONLY", "问句"),
    "c_591": ("CONTEXT_ONLY", "问句"),
    "c_597": ("CONTEXT_ONLY", "问句"),
    "c_598": ("CONTEXT_ONLY", "问句"),
    "c_599": ("CONTEXT_ONLY", "问句"),
    "c_601": ("CONTEXT_ONLY", "不是A是B 构式句"),
    "c_602": ("CONTEXT_ONLY", "叙事句"),
    "c_608": ("CONTEXT_ONLY", "问句"),
    "c_612": ("CONTEXT_ONLY", "问句"),
}

world = json.loads((ROOT / "projects" / "_drafts" / "s8_claim_labels.json").read_text(encoding="utf-8"))["labels"]
out = {}
for cid, (state, why) in POOL_TRUTH.items():
    out[cid] = {"world_truth": world[cid]["state"], "world_rationale": world[cid]["rationale"],
                "pool_truth": state, "expected_state": state, "rationale": why}
(ROOT / "projects" / "_drafts" / "s8_pool_truth.json").write_text(
    json.dumps({"_meta": {"name": "s8_pool_truth",
                          "note": "evidence-sufficiency truth（label-first）：回答池内证据能否支持/反驳，"
                                  "而非现实真假；world_truth 保留自 s8_claim_labels.json 未改。"},
                "labels": out}, ensure_ascii=False, indent=2), encoding="utf-8")
print("pool_truth written:", len(out), dict(Counter(v["pool_truth"] for v in out.values())))
