"""Stage 8A：Claim-level truth 标注（先行落盘，供 8B 聚合实验使用，本阶段不消费）。

标注口径（B 路线 §六/§八）：
- DIRECT_SUPPORT：存在独立、可靠且与 Claim 完全匹配的证据集合（数字/限定词有背书）；
- PARTIAL_SUPPORT：命题层面相关证据存在，但缺独立源/限定词背书/存在限定冲突；
- NONE：问句/叙事/修辞/观点句，或池内无命题层面证据（不可核查，对应人工路径）；
- CONTRADICTED：池内存在通过审查的真实反驳（本轮 0 条）。
"""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DIRECT = {
    "c_563": "小鼠全脑图谱：新华网'最大最详细哺乳动物连接图谱'+科技日报'首绘20种细胞全脑三维分布'+bsbii，多独立源且'最大/2025'有背书",
    "c_568": "860亿神经元：清华/虎嗅/腾讯/台大/PMC 多独立源一致确认约860亿（突触为数量级背书）",
    "c_570": "OpenWorm 302神经元/十余年：维基+煎蛋+安全内参多独立源，302与项目史一致",
    "c_578": "算力能耗散热都是钱：经济日报/钛媒体/华尔街见闻/散热产业稿多独立源一致",
}
PARTIAL = {
    "c_551": "圣朱尼佩罗设定成立，1987/海滩限定词少源背书",
    "c_552": "Underworld 设定成立，'把人脑塞进机器'表述为百科级背书",
    "c_556": "定义句；脑扫描研究多源存在",
    "c_557": "定义句；复制/上传研究多源存在",
    "c_561": "脑扫描研究确有多源证据",
    "c_562": "果蝇连接组成立，但'2023年/《科学》'限定与主流源(2024/Nature)冲突",
    "c_565": "接线图≠意识属学界共识的推断表述，多源间接背书",
    "c_569": "果蝇约14万神经元成立；'多五个数量级'为近似推断",
    "c_573": "记忆重组机制多源背书，但'基本共识'强限定欠直接背书",
    "c_574": "复制清单多层面成立，'学界无公认答案'难直接证",
    "c_582": "传送机思想实验存在（果壳/里德1775/帕菲特），多源",
    "c_583": "上传-副本哲学问题多源讨论",
    "c_584": "两派之争（功能主义/连续性）多源讨论",
    "c_585": "连续性派观点有学术来源",
    "c_586": "两派长期无共识有学术讨论来源",
    "c_589": "记忆/身体连续性讨论有源，命题本身为概念分析",
    "c_590": "上传切断两样的概念分析有源",
    "c_593": "'有人卖东西'成立（Nectome 案例），但定价句独立成 c_595",
    "c_595": "Nectome 定价报道存在，精确数字需一手确认",
    "c_600": "数字人法律基本空白多源成立",
    "c_603": "脑图谱进展快多源成立，'几十年内大进展'为外推",
}
NONE = {
    "c_553": "影视叙事惯例句", "c_555": "叙事句", "c_558": "叙事句", "c_559": "修辞句",
    "c_560": "叙事句", "c_564": "修辞句", "c_567": "问句", "c_571": "修辞句", "c_572": "隐喻/观点",
    "c_576": "叙事句", "c_579": "修辞句", "c_580": "修辞句", "c_581": "修辞句", "c_587": "叙事句",
    "c_588": "问句", "c_591": "问句", "c_597": "问句", "c_598": "问句", "c_599": "问句",
    "c_601": "修辞句", "c_602": "叙事句", "c_607": "观点句", "c_608": "问句", "c_609": "修辞句",
    "c_612": "问句",
}

labels = {}
for cid, why in DIRECT.items():
    labels[cid] = {"state": "DIRECT_SUPPORT", "rationale": why}
for cid, why in PARTIAL.items():
    labels[cid] = {"state": "PARTIAL_SUPPORT", "rationale": why}
for cid, why in NONE.items():
    labels[cid] = {"state": "NONE", "rationale": why}

out = {"_meta": {"name": "s8_claim_labels",
                 "note": "Stage 8A Claim-level truth 标注（先行落盘，供 8B 聚合实验；本阶段不消费）。"
                         "口径=B 路线设计 §六/§八；CONTRADICTED 本轮 0 条。"},
       "labels": labels}
(ROOT / "projects" / "_drafts" / "s8_claim_labels.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print("written. claims:", len(labels), "| distribution:", dict(Counter(v["state"] for v in labels.values())))
