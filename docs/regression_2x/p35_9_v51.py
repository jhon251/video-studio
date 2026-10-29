# -*- coding: utf-8 -*-
"""P35-1 修订轮 → **v5.1**（监理四处定点修改）。

① 段 11 落地重写：消除「信任生产方式」论文腔 ⇒ 三时代具体化（读过头／机器跑完／机器自己写）
② 恢复片尾**内容绑定 CTA** 为末句（P34 裁定口径，参考 v4.1 措辞）
③ 拆分最长句（气口断句、**零内容损失**），定点修段 3 / 段 4 书面腔；`mean_sentence_len ≤ 25`
④ 段 1「手指头发酸」事实风险处置（**虚拟语气化**）并**进 fact_risks**
⑤ 重跑全套机械校验

**只改表达，不改事实**：不新增/删除任何数字、实体。
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import ai_flavor as AF                                   # noqa: E402

V5 = R / "output/p35_script/v5_fulltext.json"
OUT = R / "output/p35_script/v5_1_fulltext.json"
LED = R / "output/p35_probe/fact_risks_ledger.json"

# ---- ④ 段 1：事实风险虚拟语气化（原句「重复到手指头会发酸」是对真实过程的断言）----
P1_OLD = "检查那一头是机器的活，人做不动，重复的次数太多了，重复到手指头会发酸。"
P1_NEW = ("检查那一头是机器的活，人做不动。要是换成手工一遍遍来，手指头大概早就"
          "酸得抬不起来了。")

# ---- ② 片尾内容绑定 CTA（P34 裁定口径：保留互动，去核查腔）----
CTA = "你要是手上有不一样的一手材料，发出来，比点赞有用。"

# ---- ① 段 11 落地重写（三时代具体化，去论文腔）----
P11_NEW = (
    "把这条线拉直了看，这五十年里真正换掉的，是数学凭什么让人信。"
    "以前一份证明凭什么算数，因为有人从头到尾读过，同行的眼睛就是封条——你说你看过了，"
    "这句话本身就有分量。到了四色定理，封条变成了程序跑完没报错。"
    "再往后到 AlphaGeometry 这一步，写证明的那一方，可能根本不是人。"
    "三代人的规矩，一代一个样：先是人读过头，然后是机器跑得完，现在是机器自己写得出来。"
    "同一个结论摆在那里，信它的理由换了三回。"
    "换掉的不只是工具，是每回该由谁点头这件事。"
    "接下来该谁点头、点头要付多大代价，现在只能看到一个方向，看不到终点。"
)

# ---- ③ 定点修书面腔：段 3 / 段 4 ----
FIX3 = [
    ("他的意思是，你要是接受这份证明，就等于承认数学证明的标准里，"
     "可以拿掉『能被人类逐步检视』这一条。",
     "他的意思是，你接受这份证明，就等于承认数学证明的规矩里，"
     "能把『人能一步步跟着走完』这一条划掉。"),
    ("数学跟别的学科不太一样，它的可信度一直挂在『同行能一步步跟着你走完』这件事上。"
     "抽掉这一条，等于换地基。",
     "数学跟别的学科不太一样。它凭什么可信，一直挂在同行能不能跟着你一步步走完上。"
     "抽掉这一条，等于把地基换了。"),
    ("他盯住的是我们信它的理由是什么，以及这个理由经不经得起追问。",
     "他盯住的是一件事：我们凭什么信它，这个凭什么经不经得起追问。"),
]
FIX4 = [
    ("他们的方向是，Tymoczko 把『证明』这个词收得太紧了。",
     "他们的方向是，Tymoczko 把『证明』这个词收得太紧了。"),
    ("有限单群分类就是几百位数学家的论文拼起来的。几百位是什么量级，"
     "今天活着的数学家里，没有一个人能把整块东西装进脑子。"
     "有人读过这一段，有人读过那一段，整体靠分工和互相引用撑着。",
     "有限单群分类就是几百位数学家的论文拼起来的。几百位是什么量级？"
     "今天活着的数学家里，没有一个人能把整块东西装进脑子。"
     "有人读过这一段，有人读过那一段，整体靠分工和互相引用撑着。"),
    ("我更认 Detlefsen 和 Luker 这一边，这是我的判断，不是那个领域的定论。",
     "我更认 Detlefsen 和 Luker 这一边。这是我的判断，不是那个领域的定论。"),
]

BREAKS = "，。！？；："
SENT_END = "。！？"


def split_long(s: str, target: int = 20) -> str:
    """在**既有**逗号处按**气口**断句，**零内容损失**、**不破语法**。

    判据（三版迭代后的定稿）——只有当逗号前的小句**有谓语收束**时才能断：
      · 尾部是**谓语/语气收尾**：了/的/是/有/过/出/来/去/着/好/完/错/掉/上(动词)/啊/吧/呢/吗
      · **且**尾部**不是方位/结构字**（里/上/中/下/内/外/后/前/面/边/间）——
        首版把「在《哲学杂志》上的文章里」判为完整句，断出「…文章里。把四色定理…」（错误）
      · **且**下一小句不以衔接词开头（就/而/但/所以/因为/如果/而且/于是/不过/只是/同时/以及/虽然/当/要/于/另/不/这）
    宁可不切（句子长一点），也不切出断裂句。
    """
    VERB_TAIL = set("了的过出来去着好完错掉啊吧呢吗是有")
    LOC_TAIL = set("里上中下内外后前面边间")
    NO_SPLIT_NEXT = tuple("就而且但因所果如虽当要于另不这同时以及只")
    out, buf, since = [], "", 0
    for i, ch in enumerate(s):
        if ch in SENT_END:
            buf += ch
            out.append(buf)
            buf, since = "", 0
            continue
        if ch == "，":
            body = buf.rstrip()
            nxt = s[i + 1] if i + 1 < len(s) else ""
            ok = (len(body) >= 2 and body[-1] in VERB_TAIL and body[-1] not in LOC_TAIL
                  and not (nxt and nxt in NO_SPLIT_NEXT) and since >= target)
            if ok:
                out.append(body + "。")
                buf, since = "", 0
                continue
            buf += "，"
            since += 1
            continue
        buf += ch
        since += 1
    if buf:
        out.append(buf)
    return "".join(out)


def main() -> int:
    doc = json.loads(V5.read_text(encoding="utf-8"))
    led = json.loads(LED.read_text(encoding="utf-8"))
    paras = doc["paragraphs"]
    log = {"schema": "p35-1-v51-edits-v1", "edits": []}
    t0 = "\n".join(p["text"] for p in paras)
    print("v5  : {} 字 | mean_sent={:.2f} | advance={}".format(
        len(re.sub(r"\s", "", t0)), AF.analyze(t0)["mean_sentence_len"],
        AF.analyze(t0)["advance_marker_count"]))

    for p in paras:
        t = p["text"]
        # ④ 段 1
        if P1_OLD in t:
            t = t.replace(P1_OLD, P1_NEW, 1)
            log["edits"].append({"para": p["id"], "op": "P1 事实风险虚拟语气化",
                                 "old": P1_OLD, "new": P1_NEW})
        # ③ 段 3 / 段 4 书面腔
        for old, new in FIX3 + FIX4:
            if old in t and old != new:
                t = t.replace(old, new, 1)
                log["edits"].append({"para": p["id"], "op": "书面腔定点修",
                                     "old": old[:40], "new": new[:40]})
        # ① 段 11 落地重写（判据：含「信任生产方式」）
        if "信任生产方式" in t:
            log["edits"].append({"para": p["id"], "op": "P11 落地重写",
                                 "old_chars": len(t), "new_chars": len(P11_NEW)})
            t = P11_NEW
        p["text"] = t

    # ③ 长句拆分（气口断句，零内容损失）
    before = AF.analyze("\n".join(p["text"] for p in paras))
    for p in paras:
        orig = p["text"]
        p["text"] = split_long(orig)
        if p["text"] != orig:
            log["edits"].append({"para": p["id"], "op": "长句拆分（气口）",
                                 "chars_unchanged":
                                     len(re.sub(r"\s", "", orig))
                                     == len(re.sub(r"\s", "", p["text"]))})
    # ② CTA 作为末句（若尚未在场）
    last = paras[-1]["text"].rstrip()
    if "比点赞有用" not in last:
        if not last.endswith(("。", "！", "？")):
            last += "。"
        paras[-1]["text"] = last + CTA
        log["edits"].append({"para": paras[-1]["id"], "op": "恢复片尾 CTA", "cta": CTA})

    new = dict(doc)
    new["paragraphs"] = paras
    new["schema"] = "script-output-v3-p35-v51"
    # ④ fact_risks：新增「手指头发酸」风险条（监理要求处置进账）
    new["fact_risks"] = list(led["fact_risks"]) + [
        "『手工检查会把手指头累酸』一句为**虚拟语气化的修辞**（原文为对真实过程的断言），"
        "属表达手法而非事实主张；若需作为事实陈述使用，须回查原始过程的重复次数与人力投入。"]
    new["_meta"] = dict(doc.get("_meta") or {})
    new["_meta"].update({
        "version": "v5.1", "revision_basis": "Phase 35 监理审读意见（四处定点修改）",
        "edits_applied": len(log["edits"]),
        "cta_restored": CTA,
        "char_count": len(re.sub(r"\s", "", "\n".join(p["text"] for p in paras))),
    })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(new, ensure_ascii=False, indent=1), encoding="utf-8")

    t1 = "\n".join(p["text"] for p in paras)
    a1 = AF.analyze(t1)
    print("v5.1: {} 字 | mean_sent={:.2f} | advance={} {} | 句数={}".format(
        len(re.sub(r"\s", "", t1)), a1["mean_sentence_len"],
        a1["advance_marker_count"], a1["advance_marker_hits"], a1["sentences"]))
    print("修订条目 {} 条".format(len(log["edits"])))
    print("-> " + str(OUT.relative_to(R)))
    (R / "docs/regression_2x/logs/p35_1_v51_edits.json").write_text(
        json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
