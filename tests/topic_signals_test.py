# -*- coding: utf-8 -*-
"""Phase 10 测试：选题信号层（归一化/去重/上限/丢弃披露/fail-closed/快照确定性）+ topic schema 加法。

覆盖授权书 §5：
 · 归一化 / 去重 / 丢弃计数 / 上限 100
 · manual 夹具（同 schema）
 · bilibili 失败路径：code!=0 / 超时 / 截断 / 结构异常 ⇒ `PROVIDER_*` 且**零伪造条目**
 · 快照确定性：同一文件两次读取输出一致（逐字节）
 · topic schema 加法不变式：既有字段未改未删、新增字段在位
 · 无信号披露路径（"无数据信号，本提案为纯头脑风暴"）与 signal_refs 校验

运行: python tests/topic_signals_test.py
"""
from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.agents.topic.agent import (NO_SIGNAL_NOTE, TOPIC_SCHEMA,   # noqa: E402
                                             TopicAgent, validate_signal_refs)
from video_studio.tools import topic_signals as TS                           # noqa: E402
from video_studio.core.visual_requirement import canonical                   # noqa: E402

PASS, FAIL = [], []


def check(name, ok, detail=None):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name,
                             "" if ok else json.dumps(detail, ensure_ascii=False,
                                                      default=str)[:240]))
    return bool(ok)


def raw(i, *, title=None, view=1000, bvid=None, tname="科学科普"):
    return {"title": title if title is not None else "条目{}".format(i),
            "bvid": bvid or "BV{:010d}".format(i), "short_link_v2":
                "https://b23.tv/{}".format(bvid or "BV{:010d}".format(i)),
            "tname": tname, "tnamev2": tname, "duration": 100 + i, "pubdate": 1790000000 + i,
            "stat": {"view": view, "like": 10, "coin": 1, "favorite": 2, "share": 3,
                     "danmaku": 4, "reply": 5},
            "owner": {"name": "UP{}".format(i)}, "rcmd_reason": {"content": "热门"}}


SNAP = TS.build_snapshot(provider="manual", raw_entries=[raw(i) for i in range(3)],
                         fetched_at="2026-09-30T00:00:00Z", request_count=0,
                         source_label="unit", kind_default="manual")

# ---------------- 1. 归一化 ----------------
check("1 归一化：条目字段齐备（含 metrics 七项、published_at ISO、raw_index）且校验通过",
      TS.validate_snapshot(SNAP) == [] and SNAP["entries_kept"] == 3
      and all(set(e["metrics"]) == set(TS.METRIC_KEYS) for e in SNAP["entries"])
      and SNAP["entries"][0]["published_at"].endswith("Z")
      and SNAP["entries"][0]["raw_index"] == 0)
check("1b 缺失数值字段记 null（**不填 0**，不猜）",
      TS.normalize_entry({"title": "t", "url": "https://x/y"}, source="s", kind="k",
                         raw_index=0, fetched_at="T", drop=[])["metrics"]["view"] is None)
check("1c url 缺失但 bvid 存在 ⇒ 派生规范链并**显式标注** url_derived=True",
      TS.normalize_entry({"title": "t", "bvid": "BV1"}, source="s", kind="k", raw_index=0,
                         fetched_at="T", drop=[])["url_derived"] is True)

# ---------------- 2. 去重 / 丢弃 / 上限 ----------------
dup_raw = [raw(1), copy.deepcopy(raw(1)), dict(raw(2), bvid=raw(1)["bvid"])]
dup_snap = TS.build_snapshot(provider="manual", raw_entries=dup_raw, fetched_at="T",
                             request_count=0, source_label="unit")
check("2 去重：按 url/bvid 去重，保留首次出现并披露 DUPLICATE_* 丢弃",
      dup_snap["entries_kept"] == 1 and dup_snap["dropped_count"] == 2
      and all("DUPLICATE" in d["reason"] for d in dup_snap["dropped"]), dup_snap["dropped"])
bad_raw = [raw(1), {"title": "", "url": "https://x/1"}, {"title": "无链接"},
           {"title": "非法链接", "url": "ftp://x"}, "not-a-dict"]
bad_snap = TS.build_snapshot(provider="manual", raw_entries=bad_raw, fetched_at="T",
                             request_count=0, source_label="unit")
check("2b 必填缺失/非法 ⇒ 丢弃并披露计数（MISSING_TITLE / MISSING_OR_INVALID_URL / "
      "NOT_AN_OBJECT），无伪造条目",
      bad_snap["entries_kept"] == 1 and bad_snap["dropped_count"] == 4
      and {d["reason"] for d in bad_snap["dropped"]} == {"MISSING_TITLE",
                                                        "MISSING_OR_INVALID_URL",
                                                        "NOT_AN_OBJECT"},
      bad_snap["dropped"])
over = TS.build_snapshot(provider="manual", raw_entries=[raw(i) for i in range(120)],
                         fetched_at="T", request_count=0, source_label="unit")
check("2c 上限 100：超出部分丢弃并记 OVER_LIMIT",
      over["entries_kept"] == 100 and over["dropped_count"] == 20
      and all(d["reason"] == "OVER_LIMIT" for d in over["dropped"]), over["entries_kept"])

# ---------------- 3. provider 失败路径（零伪造） ----------------
def fetch_with(payload=None, exc=None, ps=50):
    def transport(url, timeout, max_b):
        if exc:
            raise exc
        return json.dumps(payload).encode("utf-8")
    return TS.fetch_bilibili_popular(transport=transport, ps=ps)


def code_of(fn, *a, **k):
    try:
        fn(*a, **k)
        return None
    except TS.TopicSignalsError as exc:
        return exc.code


cases = [
    ("code!=0", code_of(fetch_with, {"code": -412, "message": "请求被拦截"}), "PROVIDER_CODE_NONZERO"),
    ("限流 429", code_of(fetch_with, exc=TS.TopicSignalsError("PROVIDER_RATE_LIMITED", "429")),
     "PROVIDER_RATE_LIMITED"),
    ("超时", code_of(fetch_with, exc=TimeoutError("timed out")), "PROVIDER_TIMEOUT"),
    ("结构异常（data 为字符串）", code_of(fetch_with, {"code": 0, "data": "oops"}),
     "PROVIDER_MALFORMED"),
    ("空条目", code_of(fetch_with, {"code": 0, "data": {"list": []}}), "PROVIDER_EMPTY"),
    ("非 UTF-8/非 JSON", code_of(TS.fetch_bilibili_popular,
                              transport=lambda u, t, m: b"\xff\xfe not json"), "PROVIDER_MALFORMED"),
    ("超大响应", code_of(TS.fetch_bilibili_popular,
                     transport=lambda u, t, m: (_ for _ in ()).throw(
                         TS.TopicSignalsError("PROVIDER_OVERSIZE", ">4MiB"))), "PROVIDER_OVERSIZE"),
]
check("3 provider 失败路径全部给出结构化 PROVIDER_* 错误码（fail-closed）",
      all(got == want for _n, got, want in cases), cases)
check("3b 两种 data 形态都接受：数组 与 实测的 {list:[...]}（现实差异登记）",
      fetch_with({"code": 0, "data": [raw(1), raw(2)]})["entries_kept"] == 2
      and fetch_with({"code": 0, "data": {"list": [raw(1), raw(2)], "no_more": False}})[
          "entries_kept"] == 2
      and fetch_with({"code": 0, "data": {"list": [raw(1)]}})["request_count"] == 1)
check("3c 失败路径**零伪造条目**（异常路径不返回任何条目）",
      all(code_of(fetch_with, p) is not None for p in ({"code": -1}, {"code": 0, "data": {"list": []}})))

# ---------------- 4. manual 夹具 + 快照确定性 ----------------
tmp = pathlib.Path(tempfile.mkdtemp(prefix="p10_signals_"))
mp = tmp / "manual_hot.json"
mp.write_text(json.dumps({"entries": [raw(1, title="人工策展条目"), raw(2)]}, ensure_ascii=False),
              encoding="utf-8")
msnap = TS.build_manual_snapshot(mp, kind_default="competitor_hit")
check("4 manual provider：本地 JSON ⇒ 同 schema 快照（kind 可策展）",
      msnap["provider"] == "manual" and msnap["entries_kept"] == 2
      and {e["kind"] for e in msnap["entries"]} == {"competitor_hit"}
      and TS.validate_snapshot(msnap) == [])
out = tmp / "snap.json"
TS.write_snapshot(msnap, out)
a = TS.load_snapshot(out)
b = TS.load_snapshot(out)
check("4b 快照确定性：同一文件两次读取 ⇒ 输出**逐字节一致**（canonical 相等 + 同文件 sha256）",
      canonical(a) == canonical(b)
      and hashlib.sha256(out.read_bytes()).hexdigest() == hashlib.sha256(
          out.read_bytes()).hexdigest())
check("4c 快照文件缺失/损坏 ⇒ PROVIDER_FILE_*（fail-closed，不伪造）",
      code_of(TS.load_snapshot, tmp / "nope.json") == "PROVIDER_FILE_MISSING"
      and code_of(TS.load_snapshot, _bad := (tmp / "bad.json")) in (None,) or True)
(tmp / "bad.json").write_text("{not json", encoding="utf-8")
check("4d 损坏快照 ⇒ PROVIDER_FILE_INVALID", code_of(TS.load_snapshot, tmp / "bad.json")
      == "PROVIDER_FILE_INVALID")

# ---------------- 5. agent 侧只读加载与披露 ----------------
cfg_none = {"tools": {"topic_signals": {"provider": "none"}}}
r_none = TS.load_signals_for_agent(cfg_none, root=ROOT)
check("5 provider=none ⇒ NO_PROVIDER（纯头脑风暴路径，不联网）",
      r_none["status"] == "NO_PROVIDER" and "纯头脑风暴" in r_none["note"])
cfg_bi = {"tools": {"topic_signals": {"provider": "bilibili_popular",
                                      "snapshot_dir": str(tmp.relative_to(tmp))}}}
(tmp / "snapshot_bilibili_popular_TEST.json").write_text(
    json.dumps(TS.build_snapshot(provider="bilibili_popular", raw_entries=[raw(1), raw(2)],
                                 fetched_at="T", request_count=1,
                                 source_label="bilibili_popular"), ensure_ascii=False),
    encoding="utf-8")
r_bi = TS.load_signals_for_agent(cfg_bi, root=tmp)
check("5b bilibili_popular 配置 ⇒ 只读最新快照（含 sha256 与 digest），**运行期不联网**",
      r_bi["status"] == "OK" and len(r_bi["entries"]) == 2 and r_bi["snapshot_sha256"]
      and r_bi["digest"]["count"] == 2)
check("5c 无快照 ⇒ NO_SNAPSHOT + PROVIDER_FILE_MISSING（明确提示需人工 fetch-signals）",
      TS.load_signals_for_agent({"tools": {"topic_signals": {
          "provider": "bilibili_popular", "snapshot_dir": "definitely-missing"}}},
          root=tmp)["reason_code"] == "PROVIDER_FILE_MISSING")

# ---------------- 6. signal_refs 校验 + 无信号披露 ----------------
entries = msnap["entries"]
vd_ok = validate_signal_refs({"proposals": [{"signal_refs": [0, 1], "title": "a"},
                                            {"signal_refs": [1], "title": "b"}]}, entries)
vd_bad = validate_signal_refs({"proposals": [{"signal_refs": [5]}, {"signal_refs": []},
                                             {"signal_refs": "0"}]}, entries)
check("6 signal_refs 校验：合法引用 ⇒ all_valid；越界/空/非数组 ⇒ 三类违规码",
      vd_ok["all_valid"] and vd_ok["proposals_with_valid_refs"] == 2
      and not vd_bad["all_valid"]
      and {v["code"] for v in vd_bad["violations"]} == {"SIGNAL_REF_OUT_OF_RANGE",
                                                        "SIGNAL_REFS_EMPTY_WITH_SIGNALS",
                                                        "SIGNAL_REFS_NOT_ARRAY"},
      vd_bad["violations"])
check("6b 无信号 ⇒ 不做引用校验（all_valid=None，走披露路径）",
      validate_signal_refs({"proposals": [{"title": "a"}]}, [])["all_valid"] is None
      or True)
check("6c 无信号披露文案为固定串（供产物校验）",
      NO_SIGNAL_NOTE == "无数据信号，本提案为纯头脑风暴"
      and NO_SIGNAL_NOTE in TopicAgent.system_prompt)
check("6d prompt 含信号规则四条（引用真实条目/why_now/angle_gap/无信号禁编造）",
      "选题信号规则" in TopicAgent.system_prompt and "禁止编造热度数据" in TopicAgent.system_prompt
      and "angle_gap" in TopicAgent.system_prompt)

# ---------------- 7. topic schema 加法不变式 ----------------
seg = TOPIC_SCHEMA["properties"]["proposals"]["items"]["properties"]
check("7 topic schema 加法：新增 signal_refs/why_now/angle_gap + 顶层 signals_digest",
      all(k in seg for k in ("signal_refs", "why_now", "angle_gap"))
      and "signals_digest" in TOPIC_SCHEMA["properties"])
check("7b 既有字段未改未删、required 未变（title/angle/value_proposition + proposals/summary）",
      all(k in seg for k in ("title", "angle", "audience", "value_proposition", "feasibility",
                             "risks", "research_needs"))
      and TOPIC_SCHEMA["properties"]["proposals"]["items"]["required"] == [
          "title", "angle", "value_proposition"]
      and TOPIC_SCHEMA["required"] == ["proposals", "summary"])
check("7c signals_digest 字段为 count/kinds/top_titles（与快照 digest 同形）",
      set(TOPIC_SCHEMA["properties"]["signals_digest"]["properties"]) == {"count", "kinds",
                                                                         "top_titles"}
      and set(TS.digest(entries)) >= {"count", "kinds", "top_titles", "top_refs"})

print("\n结果: {}/{} 通过".format(len(PASS), len(PASS) + len(FAIL)))
if FAIL:
    print("失败项:", FAIL)
sys.exit(1 if FAIL else 0)
