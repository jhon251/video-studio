"""Stage 8B.1：构造 11 条聚合 dev 样本（label-first；Evidence 全部为真实采集页面）。

DIRECT×4（含 anchor+互补证据）、CONTRADICTS×3、NO_SUFFICIENT×2、PARTIAL×2（数字近似/时间冲突）。
页面文本取自盲测/dev/R1 真实集合；与冻结 197 无重复配对。
"""
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

col = json.loads((ROOT / "projects" / "_drafts" / "r1_blind_collection.json").read_text(encoding="utf-8"))
dev = json.loads((ROOT / "projects" / "_drafts" / "s5_dev_collection.json").read_text(encoding="utf-8"))
pages = {}
for c in col["claims"] + dev["claims"]:
    for r in c["results"]:
        pages[r["url"]] = {"url": r["url"], "title": r["title"], "snippet": r["snippet"],
                           "text": r["page"].get("text", "")}
db = sqlite3.connect(str(ROOT / "projects" / "video_studio.db"))
db.row_factory = sqlite3.Row
for r in db.execute("SELECT * FROM evidence WHERE project_id='p_f2215875dd49'"):
    pages[r["url"]] = {"url": r["url"], "title": "", "snippet": "",
                       "text": r["excerpt"] or ""}


def P(url_part):
    for u, p in pages.items():
        if url_part in u:
            return p
    raise KeyError(url_part)


S = [
    # ---- DIRECT×4 ----
    dict(id="D2-01", truth="DIRECT_SUPPORT", claim="成年果蝇大脑的完整映射包含约139,255个神经元和超过5,000万个突触连接",
         pool=[P("mittrchina.com/news/detail/16047"), P("micro-point.tw/2025/06/27"),
               P("youtube.com/watch?v=wxd9oWMtHho")],
         why="MIT 锚点全要素+两独立源；约139,255/5,000万均原文背书"),
    dict(id="D2-02", truth="DIRECT_SUPPORT", claim="数据中心运行成本中电费占六成，电费中四成多来自冷却散热",
         pool=[P("paper.ce.cn/pc/content/202404/29"), P("tmtpost.com/7934099"),
               P("wallstreetcn.com/articles/3777873")],
         why="经济日报锚点+钛媒体/华尔街多独立源全要素背书"),
    dict(id="D2-03", truth="DIRECT_SUPPORT", claim="人类大脑约包含860亿个神经元",
         pool=[P("tsinghua.edu.cn/info/1182/111441"), P("huxiu.com/article/4837546"),
               P("news.qq.com/rain/a/20260227A06NZV00"), P("ntualumnibm.ntu.edu.tw")],
         why="清华学术锚点+虎嗅/腾讯/台大多独立源一致"),
    dict(id="D2-04", truth="DIRECT_SUPPORT",
         claim="全球数据中心散热市场规模约263亿美元，且散热是数据中心中非算力相关的最大能耗来源之一",
         pool=[P("wallstreetcn.com/articles/3777873"), P("froresystems.com/cn/blog")],
         why="anchor(华尔街)覆盖主体+263亿美元，Frore 互补'最大能耗来源'限定词——anchor+互补证据"),
    # ---- CONTRADICTS×3 ----
    dict(id="C2-01", truth="CONTRADICTS", claim="人类大脑的神经元总数为1000亿个",
         pool=[P("huxiu.com/article/4837546")],
         why="数字精确矛盾：证据明确'860亿个神经元'（同单位同对象，双精确）"),
    dict(id="C2-02", truth="CONTRADICTS", claim="AI芯片的散热问题已经彻底解决",
         pool=[P("youtube.com/watch?v=c-HZgiYCD84")],
         why="谓词否定：证据称功耗破千瓦若不解决散热算力无法释放"),
    dict(id="C2-03", truth="CONTRADICTS", claim="虚拟数字人领域至今没有任何管理办法出台",
         pool=[P("chinalawtranslate.com/digital-humans-draft")],
         why="存在否定：证据即《数字虚拟人信息服务管理办法（征求意见稿）》"),
    # ---- NO_SUFFICIENT×2 ----
    dict(id="N2-01", truth="NO_SUFFICIENT_EVIDENCE", claim="脑部扫描技术已经进入临床应用研究",
         pool=[P("ccdi.gov.cn/2026/01/14"), P("zh-cn.bluefinvision.com"), P("support.apple.com/en-us/102680")],
         why="池内为审查扫描/OCT眼扫描/二维码扫描——同形词页面，无命题证据"),
    dict(id="N2-02", truth="NO_SUFFICIENT_EVIDENCE", claim="意识上传技术已经商业化普及",
         pool=[P("m.huxiu.com/article/379957"), P("sohu.com/a/1052964186")],
         why="池内讨论意识上传概念，未涉及商业化普及命题"),
    # ---- PARTIAL×2（数字近似冲突 / 时间冲突）----
    dict(id="Q2-01", truth="PARTIAL_SUPPORT",
         claim="人脑大约860亿个神经元，突触按百万亿算",
         pool=[P("tsinghua.edu.cn/info/1182/111441"), P("huxiu.com/article/4837546")],
         why="数字近似冲突：清华'约1000亿/100万亿'——约数不一致，非精确矛盾"),
    dict(id="Q2-02", truth="PARTIAL_SUPPORT",
         claim="2023年，科学家完成了成年果蝇的全脑连接组，发在《科学》上",
         pool=[P("mittrchina.com/news/detail/16047"), P("micro-point.tw/2025/06/27")],
         why="时间冲突：证据为2024年10月《自然》——时间限定不一致，非命题否定"),
]

samples = [{"id": s["id"], "claim_text": s["claim"], "claim_source": "derived",
            "truth": s["truth"], "rationale": s["why"], "pool": s["pool"]} for s in S]
(ROOT / "projects" / "_drafts" / "s8_dev2_samples.json").write_text(
    json.dumps({"_meta": {"name": "s8_dev2_samples",
                          "note": "Stage 8B.1 构造聚合样本：Evidence 为真实采集页面；与冻结集去重；"
                                  "label-first（truth 先行落盘）。"},
                "samples": samples}, ensure_ascii=False, indent=2), encoding="utf-8")
from collections import Counter
print("dev2 written:", len(samples), dict(Counter(s["truth"] for s in samples)))
