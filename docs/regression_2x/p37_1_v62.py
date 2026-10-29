# -*- coding: utf-8 -*-
"""Phase 37：**v6.2 落地改写**（抽象名词链清剿；本题材最后一次文本迭代）。

监理四个定点（**按内容映射，不按段号**——监理段号与 v6.1 存在偏移，见报告）：
  ① P07：段首去抽象回指 ⇒ 具体场景；「一个新结果」补性质；LTE 名字**降级**处理
  ② P09：恢复 v4.1 具体清单（在守恒并集内复用）；保留地论证**加桥**；
        删除与封条段重复的抽象句
  ③ P04：有限单群分类**落地**（不新增数字）
  ④ P01：构型**落地**（紧跟沙漠类比补一句）

全局硬规则：**每个抽象名词在其承担论证作用的句子里必须带具体锚**；
连续两句不得共用未落地的抽象名词。新门 = 信号 k（抽象名词密度）。
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

V61 = R / "output/p36_script/v6_fulltext.json"


def split_long(s: str, target: int = 14) -> str:
    """与 P36 定稿同一实现（三档判据，仅改标点）——用于**最后**统一断句。"""
    VERB_TAIL = set("了的过出来去着好完错掉啊吧呢吗是有")
    LOC_TAIL = set("里上中下内外后前面边间")
    NO_SPLIT_NEXT = tuple("就而且但因所果如虽当要于另不这同时以及只它其")
    STRONG_TAIL = set("了是有完错掉")
    out, buf, since = [], "", 0
    for i, ch in enumerate(s):
        if ch in "。！？":
            buf += ch
            out.append(buf)
            buf, since = "", 0
            continue
        if ch == "，":
            body = buf.rstrip()
            nxt = s[i + 1] if i + 1 < len(s) else ""
            base = (len(body) >= 2 and body[-1] in VERB_TAIL
                    and body[-1] not in LOC_TAIL
                    and not (nxt and nxt in NO_SPLIT_NEXT))
            if base and (since >= target
                         or (since >= 8 and body[-1] in STRONG_TAIL)
                         or since >= 20):
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
V62 = R / "output/p36_script/v6_2_fulltext.json"
L = R / "docs" / "regression_2x" / "logs"

# ---------------- 定点 ①：P07 ----------------
P07_OLD_HEAD = "替谁改语言的答案，2020 年有人公开摆上了台面。Peter Scholze 提了个挑战：他手上有一个新结果，希望有人用 Lean 把它形式化。"
P07_NEW_HEAD = ("2020 年，数学界出了件新鲜事：一位顶尖数学家主动把自己的证明送上了"
                "机器。他是 Peter Scholze，手上那份东西是一份刚做出来的人类风格证明，"
                "里面堆着不少「显然」；他公开请人用 Lean 把它逐句形式化。")
P07_OLD_NAME = ("2022 年，Kevin Buzzard 宣布挑战完成，它后来被叫作 Liquid Tensor "
                "Experiment。这一次是数学家主动把自己的东西交出去，请机器来挑刺。")
P07_NEW_NAME = ("2022 年，Kevin Buzzard 宣布挑战完成。这名字很怪，叫 Liquid Tensor "
                "Experiment，记不住没关系——记住这件事：一位顶尖数学家，主动请机器"
                "来挑自己的刺。")

# ---------------- 定点 ②：P09 ----------------
V41_LEDGER = R / "output/phase33_script_sandbox/script_p33_v41_40seg.json"
P09_OLD_TAIL = ("所以真正要盯的，是验证这件事正在从人类共同体的逐步检视，转向机器逐句检查。"
                "这个转向一旦走完，剩下的活儿并不轻松。")
P09_NEW_TAIL = ("机器接走的，从头到尾都是「检查」这一步。挑哪些问题值得做、造什么概念、"
                "把验完的结论讲成人话、决定什么该信谁——这些还在人手里。"
                "一定有人说，机器做不出的那部分才是真正的核心。这种说法历史上失效过很多回。")

# ---------------- 定点 ③：P04 ----------------
P04_OLD = "有限单群分类就是几百位数学家的论文拼起来的，那几百位是什么量级，这么说吧：今天活着的数学家里，没有一个人能把整块东西装进脑子。"
P04_NEW = ("有限单群分类就是一个由几百位数学家接力完成的巨型证明，谁也没读过全部，"
           "每个人只读自己那一块。几百位是什么量级？今天活着的数学家里，"
           "没有一个人能把整块东西装进脑子。")

# ---------------- 定点 ④：P01 ----------------
P01_OLD = "他们就把无穷多种情况归约成有限多种构型，像把一整片沙漠筛成几堆沙，剩下那部分交给计算机，一种一种跑过去。"
P01_NEW = ("他们就把无穷多种情况归约成有限多种构型，像把一整片沙漠筛成几堆沙——"
           "天底下所有地图，都能塞进这么几类花样，剩下那部分交给计算机，一种一种跑过去。")


def main() -> int:
    d = json.loads(V61.read_text(encoding="utf-8"))
    ps = {p["id"]: p for p in d["paragraphs"]}
    edits = []

    def apply(pid, old, new, why):
        t = ps[pid]["text"]
        if old in t:
            ps[pid]["text"] = t.replace(old, new, 1)
            edits.append({"para": pid, "why": why, "old": old[:44], "new": new[:44]})
            return True
        edits.append({"para": pid, "why": why, "MISS": old[:44]})
        return False

    apply("P07", P07_OLD_HEAD, P07_NEW_HEAD, "① 段首去抽象回指 + 补「新结果」性质")
    apply("P07", P07_OLD_NAME, P07_NEW_NAME, "① LTE 名字降级处理")
    apply("P09", P09_OLD_TAIL, P09_NEW_TAIL,
          "② v4.1 具体清单复用 + 保留地加桥 + 删封条重复句")
    apply("P04", P04_OLD, P04_NEW, "③ 有限单群分类落地")
    apply("P01", P01_OLD, P01_NEW, "④ 构型落地")
    # **长度回落**：P09 新增清单后总时长会超 700s ⇒ 收紧一句冗余表述（不删任何事实）
    t9 = ps["P09"]["text"]
    for old, new in (("国际象棋、围棋，都曾经被列进人类的保留地，后来都易主了，"
                      "这类名单历史上不止一次被改写。",
                      "国际象棋、围棋都曾被列进人类的保留地，后来都易主了，"
                      "这类名单改写过不止一次。"),):
        if old in t9:
            ps["P09"]["text"] = t9.replace(old, new, 1)
            edits.append({"para": "P09", "why": "长度回落（同义收紧，不删事实）",
                          "old": old[:44], "new": new[:44]})
    # **长度回落（第二轮）**：压掉 P07 内**我自己新增部分**的冗余（同义，不删事实）
    t7 = ps["P07"]["text"]
    for old, new in (("2020 年，数学界出了件新鲜事：一位顶尖数学家主动把自己的证明送上了机器。"
                      "他是 Peter Scholze，手上那份是一份刚做出来的人类风格证明，",
                      "2020 年，数学界出了件新鲜事：一位顶尖数学家主动把自己的证明送上了机器。"
                      "他是 Peter Scholze，那份东西是一份刚做出来的人类风格证明，"),
                     ("这名字很怪，叫 Liquid Tensor Experiment，记不住没关系——记住这件事："
                      "一位顶尖数学家主动请机器来挑自己的刺。",
                      "这名字很怪，叫 Liquid Tensor Experiment，记不住没关系——记住这件事："
                      "他主动请机器来挑自己的刺。"),
                     ("Scholze 是顶尖数学家，他拿出来的不是业余爱好者的题目。",
                      "Scholze 拿出来的不是业余爱好者的题目。")):
        if old in t7:
            t7 = t7.replace(old, new, 1)
            edits.append({"para": "P07", "why": "长度回落（同义收紧）",
                          "old": old[:40], "new": new[:40]})
    ps["P07"]["text"] = t7
    # ---- 最后统一断句（三档判据）----
    for p in d["paragraphs"]:
        p["text"] = split_long(p["text"])

    # ---- 全局：抽象名词锚规则（只动病句，不重写已通过段落）----
    TERMS = ["归约", "构型", "形式化", "验证", "信任", "认识论", "可检视", "共同体",
             "分工", "定义问题", "保留地"]
    ANCHOR = ("1977", "1852", "1979", "1980", "1998", "2014", "2020", "2022", "2024",
              "99", "Appel", "Haken", "Tymoczko", "Detlefsen", "Luker", "Hales",
              "Flyspeck", "Lean", "mathlib", "Scholze", "Buzzard", "DeepMind",
              "AlphaGeometry", "AlphaProof", "IMO", "Nature", "四色定理", "开普勒猜想",
              "有限单群分类", "飞机", "沙漠", "沙", "橘子", "地图", "水果摊", "棋",
              "围棋", "国际象棋", "签字", "名字", "封条", "手术台", "手指头", "编译器",
              "标准件", "辅助线", "奖牌", "银牌", "领奖台", "论文", "刊物", "哲学杂志")

    def sents(t):
        return [s.strip() for s in re.split(r"(?<=[。！？])", t) if s.strip()]

    def k_report(text):
        """信号 k：术语出现、但**前后 2 句内无具体锚** ⇒ 计一次「未落地」."""
        ss = sents(text)
        hits, unanchored = [], []
        for i, s in enumerate(ss):
            for term in TERMS:
                if term in s:
                    lo, hi = max(0, i - 2), min(len(ss), i + 3)
                    ctx = "".join(ss[lo:hi])
                    if not any(a in ctx for a in ANCHOR):
                        unanchored.append({"sent": i, "term": term, "text": s[:52]})
                    hits.append({"sent": i, "term": term})
        return {"term_occurrences": len(hits), "unanchored": unanchored,
                "unanchored_count": len(unanchored),
                "density": round(len(unanchored) / max(len(ss), 1), 4)}

    text = "\n".join(p["text"] for p in d["paragraphs"])
    k = k_report(text)
    # ---- fact_risks / hook_map / cta_plan：自 v5.2 继承（15 条 = 14 底账 + P35 新增条）----
    v52 = json.loads((R / "output/p35_script/v5_2_fulltext.json")
                     .read_text(encoding="utf-8"))
    d["fact_risks"] = v52["fact_risks"]
    d["hook_map"] = v52.get("hook_map")
    d["cta_plan"] = v52.get("cta_plan")
    d["story_spine"] = "凭什么信（单线贯穿九拍；v6.2 抽象名词链清剿）"
    d["schema"] = "script-output-v4-p37-v62"
    d["_meta"] = dict(d.get("_meta") or {})
    d["_meta"].update({
        "version": "v6.2",
        "revision_basis": "Phase 37 授权书：抽象名词链清剿（四个定点 + 全局锚规则）",
        "edits": edits,
        "signal_k": k,
        "note_pid_mapping": ("监理段号与 v6.1 存在偏移：监理「段1/段4/段7/段9」"
                             "按内容对应 v6.1 的 P01/P04/P07/P09"),
    })
    V62.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")

    a = AF.analyze(text)
    chars = len(re.sub(r"\s", "", text))
    print("编辑 {} 条（MISS {} 条）".format(
        sum(1 for e in edits if "MISS" not in e),
        sum(1 for e in edits if "MISS" in e)))
    for e in edits:
        flag = "MISS" if "MISS" in e else "OK  "
        print("  {} {} {}".format(flag, e["para"], e["why"]))
    print()
    print("信号 k（抽象名词密度）：术语出现 {} 次 | **未落地 {} 处** | 密度 {:.4f}".format(
        k["term_occurrences"], k["unanchored_count"], k["density"]))
    for u in k["unanchored"][:8]:
        print("    ! [{}] {}".format(u["term"], u["text"]))
    print()
    print("v6.2: {} 字 | 预估 {:.0f}s | mean_sent={:.2f} | 推进词={}".format(
        chars, chars / 4.9, a["mean_sentence_len"], a["advance_marker_count"]))
    print("-> " + str(V62.relative_to(R)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
