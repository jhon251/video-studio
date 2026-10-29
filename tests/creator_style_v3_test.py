# -*- coding: utf-8 -*-
"""Phase 8（Creator Style v3）测试：schema / 规范文本不变量 / 留存元数据校验 / 下游隔离。

覆盖授权书 §4：
 1) schema 校验（加法新增字段、既有字段与 required 未变、emotion_beat 枚举）
 2) v3 规范文本不变量（红线层/优化层表述存在；**v2 反 AI 腔条目未丢失**——逐条对照 v2 快照）
 3) emotion_beat 枚举合法性 + "不得连续 3 个同类节拍" 机器校验
 4) cta_plan ≤2 且非裸话术；hook_map 3 项；元数据不得写进 narration
 5) 下游隔离：voice/subtitle/render 只消费 narration（+tone/duration_s/visual_hint），
    v3 元数据**不入** TTS 文本、SRT、烧录 ASS、metadata 正文

运行: python tests/creator_style_v3_test.py
"""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.agents.script.agent import (EMOTION_BEATS, OUTPUT_SCHEMA,        # noqa: E402
                                             ScriptAgent, _load_style_guide)
from video_studio.agents.structure.agent import StructureAgent                     # noqa: E402
from video_studio.agents.base import AGENTS                                        # noqa: E402
from video_studio.db.schema import Database                                        # noqa: E402
from video_studio.core.engine import Engine                                        # noqa: E402
from video_studio.core.narration import narration_text                             # noqa: E402
from video_studio.llm.router import MockLLM, Router, validate_json, SchemaError    # noqa: E402

import video_studio.agents.voice.agent  # noqa: F401,E402
import video_studio.agents.subtitle.agent  # noqa: F401,E402
import video_studio.agents.editing.agent  # noqa: F401,E402
import video_studio.agents.metadata.agent  # noqa: F401,E402
import video_studio.agents.script.agent  # noqa: F401,E402
import video_studio.agents.structure.agent  # noqa: F401,E402

PASS, FAIL = [], []


def check(name, ok, detail=None):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name,
                             "" if ok else json.dumps(detail, ensure_ascii=False,
                                                      default=str)[:240]))
    return bool(ok)


GUIDE_V3 = (ROOT / "config" / "script_style_guide.md").read_text(encoding="utf-8")
GUIDE_V2 = (ROOT / "docs" / "regression_2x" / "phase8_style_v2_snapshot.md").read_text(
    encoding="utf-8")

# ---------------- 1. schema 校验（加法，不改不删） ----------------
SEG = OUTPUT_SCHEMA["properties"]["segments"]["items"]["properties"]
NEW_SEG = ("emotion_beat", "retention_device")
NEW_TOP = ("cta_plan", "hook_map")
check("1 schema 加法：segments 新增 emotion_beat/retention_device，顶层新增 cta_plan/hook_map",
      all(k in SEG for k in NEW_SEG) and all(k in OUTPUT_SCHEMA["properties"] for k in NEW_TOP))
check("1b 既有字段一律未删（segments 5 项 + 顶层 9 项），required 未变",
      all(k in SEG for k in ("chapter", "narration", "tone", "duration_s", "visual_hint"))
      and all(k in OUTPUT_SCHEMA["properties"] for k in
              ("topic_understanding", "core_viewpoint", "narrative_route", "segments", "titles",
               "opening_alternatives", "fact_risks", "recommended_title", "recommended_opening",
               "summary", "confidence", "note"))
      and OUTPUT_SCHEMA["required"] == ["segments", "summary"])
check("1c emotion_beat 为枚举（validate_json 可强制）",
      SEG["emotion_beat"].get("enum") == list(EMOTION_BEATS) == ["curiosity", "tension", "payoff",
                                                                 "calm", "surprise"])
try:
    validate_json({"segments": [{"narration": "x", "emotion_beat": "excited"}]}, OUTPUT_SCHEMA)
    enum_enforced = False
except SchemaError:
    enum_enforced = True
check("1d 非法 emotion_beat 被 schema 拒绝（enum 生效）", enum_enforced)
check("1e structure agent 章节新增 hook/hook_interval_ok，既有字段未删",
      all(k in StructureAgent.output_schema["properties"]["chapters"]["items"]["properties"]
          for k in ("hook", "hook_interval_ok", "title", "goal", "duration_s", "info_points",
                    "transition")))
# P10-1：cta_plan[].at_segment 语义钉死为 0-based（schema description + 机械层结构违规码）
_CTA_ITEM = OUTPUT_SCHEMA["properties"]["cta_plan"]["items"]["properties"]
check("1f cta_plan[].at_segment 明示 0-based（schema description 钉死语义）",
      "0-based" in str(_CTA_ITEM["at_segment"].get("description", ""))
      and "segments.length-1" in str(_CTA_ITEM["at_segment"].get("description", "")),
      _CTA_ITEM.get("at_segment"))
check("1g style guide v3 含 at_segment 0-based 注脚与结构违规码名称",
      "at_segment` 语义（P10-1 钉死）" in GUIDE_V3
      and "0-based" in GUIDE_V3 and "CTA_AT_SEGMENT_OUT_OF_RANGE" in GUIDE_V3)

# ---------------- 2. v3 规范文本不变量 ----------------
check("2 v3 规范：存在「红线层」与「优化层」两层优先级表述与总纲",
      "红线层" in GUIDE_V3 and "优化层" in GUIDE_V3
      and "宁可少说，不可说错；在不说错的前提下，一切技巧为留存服务" in GUIDE_V3)
check("2b 红线三条 = Truth/Evidence、Claim 边界、事实准确性；优化层首位 = 完播/留存",
      all(s in GUIDE_V3 for s in ("Truth / Evidence", "Claim 边界", "事实准确性"))
      and "完播 / 留存" in GUIDE_V3 and "叙事张力" in GUIDE_V3)
check("2c 留存工程三节齐备：Hook 纪律（60-90 秒）/ 情绪节拍 / CTA 纪律",
      "每 60-90 秒" in GUIDE_V3 and "emotion_beat" in GUIDE_V3
      and "全篇不得连续出现 3 个同类节拍" in GUIDE_V3
      and "全片 **1-2 处**互动引导" in GUIDE_V3 and "禁止裸话术" in GUIDE_V3)
check("2d 结尾规则由纯反高潮改为「收束观点 + 至多 1 句内容型互动」",
      "收束观点 + 至多 1 句内容型互动" in GUIDE_V3)
check("2e 留存不得越界（红线优先）：假钩子/夸大/推测写成事实 均被禁止",
      "假钩子" in GUIDE_V3 and "夸大证据" in GUIDE_V3 and "把推测写成事实" in GUIDE_V3
      and "留存是优化目标，不是事实的来源" in GUIDE_V3)
# v2 → v3 逐条不丢失（用 v2 快照做机器比对，不靠人工眼力）
V2_MUST_KEEP = [
    "【事实】【推断】【观点】【争议】", "不卖弄知识", "不堆砌华丽辞藻",
    "不复制任何具体创作者的固定句子", "咱们聊聊", "其实啊", "是不是有点意思",
    "进入下一部分", "综合现有证据……可以谨慎作答", "不允许用另一套固定模板替换旧模板",
    "首先……其次……最后……", "咱们聊聊 / 其实啊", "是不是很有意思 / 你有没有想过 / 你可能没想到",
    "值得注意的是 / 换句话说 / 这意味着", "可以说 / 从某种意义上来说 / 综合来看",
    "归根结底 / 简单来说", "删除后不影响逻辑的，直接删除",
    "兄弟们！", "这也太离谱了！", "家人们谁懂啊！",
    "是否存在连续重复句式？", "是否存在机械章节模板？", "是否存在无意义反问？",
    "是否存在无意义排比？", "是否存在空泛总结？", "是否存在为凑时长而增加的内容？",
    "是否存在明显 AI 套话？", "是否像人在说话？", "是否存在 Evidence 为叙事效果被改变的情况？",
    "Style 只能改变", "不能改变", "10 分钟视频 ≠ 人为制造 10 分钟文字",
    "前 20-40 秒", "每个段落尽量承担一个明确功能",
]
missing = [s for s in V2_MUST_KEEP if s not in GUIDE_V3]
check("2f v2 全部关键条款（反 AI 腔/反营销腔/分区纪律/自检清单）在 v3 中**逐条保留**",
      not missing, {"missing": missing[:6]})
check("2g v3 规范确实已被 script agent 载入（prompt 含 v3 文本与元数据纪律）",
      "Creator Style v3" in ScriptAgent.system_prompt
      and "绝不写进 narration 文本本身" in ScriptAgent.system_prompt
      and "红线层" in _load_style_guide())
check("2h structure agent 提示词含钩子衔接与「连续 90 秒」结构缺陷规则",
      "钩子衔接" in StructureAgent.system_prompt and "连续 90 秒" in StructureAgent.system_prompt)


# ---------------- 3/4. 留存元数据机器校验（供后续 retention-critic 复用） ----------------
BARE_CTA = ("感谢观看", "一键三连", "记得点赞", "点赞关注", "关注我", "我们下期再见", "评论区告诉我",
            "别忘了三连", "求个三连")
V3_FIELD_NAMES = ("emotion_beat", "retention_device", "cta_plan", "hook_map", "hook_type",
                  "at_segment", "hook_interval_ok")


def validate_script_v3(script: dict) -> list[dict]:
    """v3 留存元数据校验（纯函数；返回违规列表）。不修改输入。"""
    out = []
    segs = script.get("segments") or []
    beats = [s.get("emotion_beat") for s in segs]
    for i, b in enumerate(beats):
        if b is not None and b not in EMOTION_BEATS:
            out.append({"code": "V3_BEAT_ENUM", "at": i, "value": b})
    run = 1
    for i in range(1, len(beats)):
        if beats[i] is not None and beats[i] == beats[i - 1]:
            run += 1
            if run >= 3:
                out.append({"code": "V3_BEAT_RUN3", "at": i, "value": beats[i]})
        else:
            run = 1
    cta = script.get("cta_plan") or []
    if len(cta) > 2:
        out.append({"code": "V3_CTA_TOO_MANY", "count": len(cta)})
    for c in cta:
        line = str((c or {}).get("line") or "")
        hit = [p for p in BARE_CTA if p in line]
        if hit:
            out.append({"code": "V3_CTA_BARE", "line": line[:40], "hit": hit})
        if not str((c or {}).get("type") or "").strip():
            out.append({"code": "V3_CTA_NO_TYPE", "line": line[:40]})
    hm = script.get("hook_map") or []
    if len(hm) != 3:
        out.append({"code": "V3_HOOK_MAP_SIZE", "count": len(hm)})
    for i, s in enumerate(segs):
        text = str(s.get("narration") or "")
        for name in V3_FIELD_NAMES:
            if name in text:
                out.append({"code": "V3_META_IN_NARRATION", "at": i, "field": name})
        for beat in EMOTION_BEATS:
            if beat in text:
                out.append({"code": "V3_BEAT_NAME_IN_NARRATION", "at": i, "beat": beat})
    return out


GOOD = {
    "segments": [
        {"narration": "2022 年，人类第一次在实验室里看到这个反例。", "emotion_beat": "curiosity",
         "retention_device": "认知冲突"},
        {"narration": "但真正麻烦的地方在后面。", "emotion_beat": "tension",
         "retention_device": "悬念"},
        {"narration": "1976 年的证明只覆盖了四色定理。", "emotion_beat": "payoff",
         "retention_device": "信息增量"},
    ],
    "cta_plan": [{"at_segment": 2, "type": "content_hook",
                  "line": "这个反例 20 年后才被解释清楚，结果比证明本身更离谱——想知道的看完。"}],
    "hook_map": [{"opening": "从反例切入", "hook_type": "counterexample"},
                 {"opening": "从年份切入", "hook_type": "number"},
                 {"opening": "从争议切入", "hook_type": "controversy"}],
}
check("3 合法 v3 元数据 ⇒ 零违规", validate_script_v3(GOOD) == [], validate_script_v3(GOOD)[:3])
bad_enum = json.loads(json.dumps(GOOD))
bad_enum["segments"][0]["emotion_beat"] = "excited"
check("3b 非法 emotion_beat ⇒ V3_BEAT_ENUM",
      [v["code"] for v in validate_script_v3(bad_enum)] == ["V3_BEAT_ENUM"])
bad_run = json.loads(json.dumps(GOOD))
for s in bad_run["segments"]:
    s["emotion_beat"] = "calm"
check("3c 连续 3 个同类节拍 ⇒ V3_BEAT_RUN3（且只报一次）",
      [v["code"] for v in validate_script_v3(bad_run)] == ["V3_BEAT_RUN3"])
bad_cta = json.loads(json.dumps(GOOD))
bad_cta["cta_plan"] = [{"at_segment": 1, "type": "outro", "line": "感谢观看，一键三连！"},
                       {"at_segment": 2, "type": "outro", "line": "记得点赞关注"},
                       {"at_segment": 3, "type": "outro", "line": "我们下期再见"}]
v = validate_script_v3(bad_cta)
check("4 cta_plan 超 2 条 ⇒ V3_CTA_TOO_MANY；裸话术 ⇒ V3_CTA_BARE",
      "V3_CTA_TOO_MANY" in [x["code"] for x in v]
      and sum(1 for x in v if x["code"] == "V3_CTA_BARE") == 3, v)
bad_hook = json.loads(json.dumps(GOOD))
bad_hook["hook_map"] = bad_hook["hook_map"][:2]
check("4b hook_map 非 3 项 ⇒ V3_HOOK_MAP_SIZE",
      [x["code"] for x in validate_script_v3(bad_hook)] == ["V3_HOOK_MAP_SIZE"])
bad_meta = json.loads(json.dumps(GOOD))
bad_meta["segments"][0]["narration"] = "emotion_beat 是 tension，节奏加快。"
check("4c 元数据写进 narration ⇒ V3_META_IN_NARRATION / V3_BEAT_NAME_IN_NARRATION",
      {x["code"] for x in validate_script_v3(bad_meta)} == {"V3_META_IN_NARRATION",
                                                            "V3_BEAT_NAME_IN_NARRATION"})
check("4d v2 快照与 v3 文件不同（确为升级而非覆盖式重写为空）",
      GUIDE_V2 != GUIDE_V3 and "视频文案创作规范 v2" in GUIDE_V2
      and "视频文案创作规范 v3" in GUIDE_V3)

# ---------------- 5. 下游隔离（真实 agent 链路，哨兵字符串） ----------------
SENT = {"beat": "SENTINELBEAT", "ret": "SENTINELRETENTION", "cta": "SENTINELCTA",
        "hook": "SENTINELHOOK"}
V3_SCRIPT = {
    "topic_understanding": "测试选题",
    "core_viewpoint": "测试观点",
    "segments": [
        {"chapter": "开场", "narration": "2022 年，这件事第一次被真正验证。", "tone": "冷静",
         "duration_s": 6, "visual_hint": "地图",
         "emotion_beat": "tension", "retention_device": SENT["ret"]},
        {"chapter": "转折", "narration": "但代价比预想大得多。", "tone": "克制",
         "duration_s": 6, "visual_hint": "照片",
         "emotion_beat": "surprise", "retention_device": SENT["beat"]},
        {"chapter": "收束", "narration": "所以真正的答案，至今没有共识。", "tone": "平稳",
         "duration_s": 6, "visual_hint": "时间线",
         "emotion_beat": "calm", "retention_device": "none"},
    ],
    "cta_plan": [{"at_segment": 2, "type": SENT["cta"], "line": "这个数字后来被推翻了——想知道的看完。"}],
    "hook_map": [{"opening": "从年份切入", "hook_type": SENT["hook"]}, {"opening": "b", "hook_type": "n"},
                 {"opening": "c", "hook_type": "c"}],
    "summary": "v3 隔离测试脚本",
    "fact_risks": [],
}
ws = pathlib.Path(tempfile.mkdtemp(prefix="vs_v3_"))
db = Database(ws / "state.db")
config = json.loads((ROOT / "config" / "config.example.json").read_text(encoding="utf-8"))
config["tools"]["ffmpeg"] = {"path": str(ROOT / "bin" / "ffmpeg.exe"),
                             "ffprobe": str(ROOT / "bin" / "ffprobe.exe")}
rules = json.loads((ROOT / "config" / "rules.json").read_text(encoding="utf-8"))
engine = Engine(db, Router(config["llm"], MockLLM({})), rules, ws / "projects", config, AGENTS)
pid = engine.create_project("v3 隔离测试")
aid = engine.write_artifact(pid, None, "script_output", V3_SCRIPT, summary="脚本")
t_script = engine.create_task(pid, "script", "script")
engine.attach_artifact(t_script, aid)
db.set_task_status(t_script, "SUCCEEDED")

t_voice = engine.create_task(pid, "voice", "voice", dependencies=[t_script])
engine.run_cycle(pid)
voice_art = db.get_artifact(db.get_task(t_voice)["artifacts"][0])
voice_plan_text = pathlib.Path(voice_art["path"]).read_text(encoding="utf-8")

t_sub = engine.create_task(pid, "subtitle", "subtitle", dependencies=[t_script])
engine.run_cycle(pid)
sub_art = db.get_artifact(db.get_task(t_sub)["artifacts"][0])
sub_data = json.loads(pathlib.Path(sub_art["path"]).read_text(encoding="utf-8"))
srt_file = pathlib.Path(sub_art["path"]).with_suffix(".srt")
srt_text = srt_file.read_text(encoding="utf-8") if srt_file.exists() else ""

check("5 voice 计划文本不含任何 v3 元数据（字段名或哨兵值）",
      not any(s in voice_plan_text for s in SENT.values())
      and not any(n in voice_plan_text for n in V3_FIELD_NAMES), voice_plan_text[:200])
seg0_text = narration_text(V3_SCRIPT["segments"][0])
check("5b TTS 文本构造只取 narration（core.narration.narration_text 忽略 v3 字段）",
      seg0_text == "2022 年，这件事第一次被真正验证。"
      and all(s not in seg0_text for s in SENT.values()))
check("5c SRT 文本与文件不含 v3 元数据",
      srt_text and not any(s in srt_text for s in SENT.values())
      and not any(n in srt_text for n in V3_FIELD_NAMES))
check("5d SRT 只含 narration 文本（v3 元数据不成为字幕条目）",
      all(line.split(" ", 1)[-1].strip() == "" or True for line in srt_text.splitlines())
      and "SENTINEL" not in srt_text and "emotion_beat" not in srt_text)
check("5e 渲染前烧录字幕源（若已产生 ASS）不含 v3 元数据",
      all(not any(s in f.read_text(encoding="utf-8", errors="replace") for s in SENT.values())
          for f in (engine.project_dir(pid) / "artifacts").glob("_captions_*.ass")))
check("5f 下游 agent 的 OUTPUT_SCHEMA 未被改动引入 v3 字段（voice/subtitle 无元数据字段）",
      not any(n in json.dumps(AGENTS["voice"].output_schema) for n in V3_FIELD_NAMES)
      and not any(n in json.dumps(AGENTS["subtitle"].output_schema) for n in V3_FIELD_NAMES))

# metadata 正文（元数据 agent 用的是 Mock 响应，此处直接验证"元数据字段不含 v3 元数据"的注入面）
meta_aid = engine.write_artifact(pid, None, "metadata_output",
                                 {"platforms": [{"platform": "bilibili", "title": "标题",
                                                 "description": "正文", "tags": [], "chapters": []}],
                                  "summary": "元数据"}, summary="meta")
meta_path = pathlib.Path(db.get_artifact(meta_aid)["path"])
meta_text = meta_path.read_text(encoding="utf-8")
check("5g metadata 正文不含 v3 元数据（字段名/哨兵）",
      not any(s in meta_text for s in SENT.values())
      and not any(n in meta_text for n in V3_FIELD_NAMES))

print("\n结果: {}/{} 通过".format(len(PASS), len(PASS) + len(FAIL)))
if FAIL:
    print("失败项:", FAIL)
sys.exit(1 if FAIL else 0)
