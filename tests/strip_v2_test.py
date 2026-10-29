"""V2 第四阶段测试：strip_claims 全链路剥离 + 内部可追溯性保留。"""

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from video_studio.core.strip import strip_claims, strip_claims_deep, has_claims  # noqa: E402
from video_studio.db.schema import Database  # noqa: E402
from video_studio.core.engine import Engine  # noqa: E402
from video_studio.llm.router import MockLLM, Router  # noqa: E402
from export_script import build_script_text  # noqa: E402

import video_studio.agents.claim_extractor.agent  # noqa: F401,E402
import video_studio.agents.voice.agent  # noqa: F401,E402
import video_studio.agents.subtitle.agent  # noqa: F401,E402
import video_studio.agents.editing.agent  # noqa: F401,E402
import video_studio.agents.metadata.agent  # noqa: F401,E402
import video_studio.agents.script.agent  # noqa: F401,E402
import video_studio.agents.pm.agent  # noqa: F401,E402
import video_studio.agents.topic.agent  # noqa: F401,E402
from video_studio.agents.base import AGENTS  # noqa: E402

MARKED_SCRIPT = {
    "segments": [
        {"chapter": "开场", "narration": "[CLAIM:c_001]2022年，桐人戴上NerveGear。",
         "duration_s": 5, "visual_hint": "",
         # Phase 8 / Creator Style v3：留存元数据（**元数据**，不得进入任何用户可见文本）
         "emotion_beat": "curiosity", "retention_device": "V3SENTINEL_RETENTION"},
        {"chapter": "人体试验", "narration": "[CLAIM:c_002]2024年1月，Neuralink完成第一例人体植入。",
         "duration_s": 5, "visual_hint": "",
         "emotion_beat": "tension", "retention_device": "悬念"},
    ],
    "summary": "标记测试脚本",
    # v3 顶层留存元数据（哨兵值用于泄漏检测）
    "cta_plan": [{"at_segment": 1, "type": "content_hook", "line": "V3SENTINEL_CTA"}],
    "hook_map": [{"opening": "从年份切入", "hook_type": "V3SENTINEL_HOOK"},
                 {"opening": "b", "hook_type": "n"}, {"opening": "c", "hook_type": "c"}],
}

#: Phase 8（v3）：下游隔离哨兵 —— 这些字符串只允许存在于 script 内部产物中
V3_SENTINELS = ("V3SENTINEL_RETENTION", "V3SENTINEL_CTA", "V3SENTINEL_HOOK")
V3_FIELD_NAMES = ("emotion_beat", "retention_device", "cta_plan", "hook_map", "hook_type",
                  "at_segment")


def has_v3_meta(text: str) -> bool:
    """检测文本是否泄漏 v3 留存元数据（字段名或哨兵值）。"""
    return any(s in text for s in V3_SENTINELS) or any(n in text for n in V3_FIELD_NAMES)

META_WITH_MARKERS = {
    "platforms": [
        {"platform": "bilibili", "title": "标题[CLAIM:c_002]实测",
         "description": "描述含标记[CLAIM:c_001]文字", "tags": ["标签[CLAIM:c_002]"], "chapters": []},
    ],
    "summary": "元数据（含标记，测试防御剥离）",
    "confidence": 0.8,
    "note": "",
    # ---- Phase 11（P11-2）：标题/封面候选（**计划数据**，不得污染 TTS/SRT/ASS 与发布面正文）----
    "title_candidates": [
        {"text": "P11TITLE 候选正文", "technique": "specificity",
         "evidence_refs": [0], "number_sources": [0],
         "why_win": "P11WHY", "disappointment_risk": "P11RISK"},
    ],
    "ab_plan": {"platform": "bilibili", "variants": ["P11VARIANT A", "P11VARIANT B"],
                "metric": "ctr", "execution": "manual",
                "note": "P11ABNOTE 人工发布执行，系统不做任何发布动作"},
    "cover_text_candidates": [
        {"text": "P11COVER", "cover_title_pairing": "递进", "pairing_note": "P11PAIR"},
    ],
}

#: Phase 11（P11-2）：新字段名与哨兵 —— 只允许存在于 metadata 计划产物/发布清单中，
#: **不得**出现在 TTS、SRT、烧录 ASS，以及发布面的 title/description/tags 正文字段里。
P11_FIELD_NAMES = ("title_candidates", "ab_plan", "cover_text_candidates",
                   "cover_title_pairing", "number_sources", "evidence_refs", "disappointment_risk")
P11_SENTINELS = ("P11TITLE", "P11WHY", "P11RISK", "P11VARIANT", "P11ABNOTE", "P11COVER", "P11PAIR")


def has_p11_meta(text: str) -> bool:
    """检测文本是否混入 P11 计划数据（字段名或哨兵值）。"""
    return any(s in text for s in P11_SENTINELS) or any(n in text for n in P11_FIELD_NAMES)


def main() -> int:
    checks = []

    def check(name, cond, detail=""):
        checks.append((name, cond))
        print(f"{'PASS' if cond else 'FAIL'}  {name} {detail}")

    # ---------- 单元测试 ----------
    s = strip_claims("开头[CLAIM:c_001]正文[CLAIM:x-9]结尾")
    check("strip_claims 基本剥离", s == "开头正文结尾")
    deep = strip_claims_deep({"a": ["x[CLAIM:c_1]y"], "b": {"c": "[CLAIM:z]d"}})
    check("strip_claims_deep 递归剥离", deep == {"a": ["xy"], "b": {"c": "d"}})
    check("has_claims 检测", has_claims("有[CLAIM:c_1]") and not has_claims("没有"))

    # ---------- 全链路 ----------
    workspace = Path(tempfile.mkdtemp(prefix="vs_strip_"))
    db = Database(workspace / "state.db")
    config = json.loads((ROOT / "config" / "config.example.json").read_text(encoding="utf-8"))
    config["tools"]["ffmpeg"] = {"path": str(ROOT / "bin" / "ffmpeg.exe"),
                                 "ffprobe": str(ROOT / "bin" / "ffprobe.exe")}
    rules = json.loads((ROOT / "config" / "rules.json").read_text(encoding="utf-8"))
    mock = MockLLM({"元数据与 SEO": META_WITH_MARKERS})
    engine = Engine(db, Router(config["llm"], mock), rules, workspace / "projects", config, AGENTS)
    pid = engine.create_project("剥离测试")

    # script 产物 + 挂到任务上（不运行 script agent）
    script_aid = engine.write_artifact(pid, None, "script_output", MARKED_SCRIPT, summary="脚本")
    t_script = engine.create_task(pid, "script", "script")
    engine.attach_artifact(t_script, script_aid)
    db.set_task_status(t_script, "SUCCEEDED")

    # claim_extractor：内部稿/claims_map/claims 保留标记与索引
    t1 = engine.create_task(pid, "claim_extract", "claim_extractor",
                            inputs={"script_ref": script_aid})
    engine.run_cycle(pid)
    art1 = db.get_artifact(db.get_task(t1)["artifacts"][0])
    with open(art1["path"], encoding="utf-8") as fh:
        map_data = json.load(fh)
    internal_text = json.dumps(map_data.get("segments_internal", []), ensure_ascii=False)
    check("内部稿保留标记（可追溯）", "[CLAIM:c_001]" in internal_text)
    check("claims 表保留索引", len(db.list_claims(pid)) >= 2)
    # 模拟人工批准（V2 闸门：生产任务要求全部 claim 处于 PASSED 状态）
    for c in db.list_claims(pid):
        db.update_claim(c["claim_id"], status="VERIFIED", human_review_required=False)

    # voice（计划模式）→ 零标记
    t_voice = engine.create_task(pid, "voice", "voice", dependencies=[t_script])
    engine.run_cycle(pid)
    art_v = db.get_artifact(db.get_task(t_voice)["artifacts"][0])
    with open(art_v["path"], encoding="utf-8") as fh:
        voice_plan = json.load(fh)
    check("voice 计划文本零标记", not has_claims(json.dumps(voice_plan, ensure_ascii=False)))

    # subtitle → SRT 零标记
    t_sub = engine.create_task(pid, "subtitle", "subtitle", dependencies=[t_script])
    engine.run_cycle(pid)
    art_s = db.get_artifact(db.get_task(t_sub)["artifacts"][0])
    with open(art_s["path"], encoding="utf-8") as fh:
        sub_data = json.load(fh)
    check("SRT 文本零标记", not has_claims(sub_data["srt"]))
    srt_file = Path(art_s["path"]).with_suffix(".srt")
    check("SRT 文件零标记", srt_file.exists() and not has_claims(srt_file.read_text(encoding="utf-8")))

    # render → 烧录字幕源零标记 + 成片产出
    t_render = engine.create_task(pid, "render", "editing", dependencies=[t_script])
    engine.run_cycle(pid)
    # 5-M：烧录字幕源由"逐段 `_seg*.txt`（drawtext）"改为"`_captions_*.ass`（libass）"；
    #      断言**意图不变**——烧录用的字幕源不得含 claim 标记（测试契约更新，非业务语义变更）。
    cap_files = list((engine.project_dir(pid) / "artifacts").glob("_captions_*.ass"))
    cap_text = "\n".join(f.read_text(encoding="utf-8", errors="replace") for f in cap_files)
    check("烧录字幕源零标记", bool(cap_files) and not has_claims(cap_text))
    render_task = db.get_task(t_render)
    check("渲染产出成片", render_task["status"] == "SUCCEEDED"
          and (engine.project_dir(pid) / "output" / f"{t_render}_draft.mp4").exists())

    # metadata → 防御剥离
    t_meta = engine.create_task(pid, "metadata", "metadata", dependencies=[t_script])
    engine.run_cycle(pid)
    art_m = db.get_artifact(db.get_task(t_meta)["artifacts"][0])
    with open(art_m["path"], encoding="utf-8") as fh:
        meta_data = json.load(fh)
    check("metadata 零标记", not has_claims(json.dumps(meta_data, ensure_ascii=False)))

    # publish → 发布稿零标记
    from video_studio.tools.publish_tool import PublishTool
    from video_studio.tools.base import ToolContext
    (engine.project_dir(pid) / "output").mkdir(exist_ok=True)
    dummy = engine.project_dir(pid) / "output" / "final.mp4"
    dummy.write_bytes(b"\x00" * 1024)
    pctx = ToolContext(role="human", project_id=pid, project_dir=engine.project_dir(pid),
                       db=db, config=config, human_token="ok")
    presult = PublishTool().execute({"video": "output/final.mp4", "platform": "bilibili",
                                     "metadata_ref": db.get_task(t_meta)["artifacts"][0]}, pctx)
    pkg_text = (engine.project_dir(pid) / "output" / "publish" / "publish_bilibili.json").read_text(encoding="utf-8")
    check("发布稿零标记", not has_claims(pkg_text))

    # 朗读稿导出
    script_art = db.get_artifact(script_aid)
    with open(script_art["path"], encoding="utf-8") as fh:
        script_data = json.load(fh)
    narrate_text = build_script_text(script_data)
    check("朗读稿导出零标记", not has_claims(narrate_text) and "桐人" in narrate_text)

    # ---------- Phase 8（Creator Style v3）：下游隔离（元数据不得泄漏到用户可见文本） ----------
    # 脚本内部产物**应当**保留 v3 元数据（可追溯），用户可见文本**不得**出现。
    internal_v3 = json.dumps(script_data, ensure_ascii=False)
    check("v3 元数据在 script 内部产物中保留（可追溯）",
          "emotion_beat" in internal_v3 and "V3SENTINEL_RETENTION" in internal_v3)
    check("v3 隔离：voice 计划文本无 v3 元数据",
          not has_v3_meta(json.dumps(voice_plan, ensure_ascii=False)))
    check("v3 隔离：SRT 文本文件无 v3 元数据",
          not has_v3_meta(sub_data["srt"])
          and srt_file.exists() and not has_v3_meta(srt_file.read_text(encoding="utf-8")))
    check("v3 隔离：烧录字幕源（ASS）无 v3 元数据", not has_v3_meta(cap_text))
    check("v3 隔离：metadata 正文无 v3 元数据",
          not has_v3_meta(json.dumps(meta_data, ensure_ascii=False)))
    check("v3 隔离：发布稿无 v3 元数据", not has_v3_meta(pkg_text))
    check("v3 隔离：朗读稿导出无 v3 元数据", not has_v3_meta(narrate_text))

    # ---------- Phase 11（P11-2）：标题/封面候选计划数据的隔离 ----------
    meta_text = json.dumps(meta_data, ensure_ascii=False)
    check("P11 计划数据在 metadata 产物中保留（可追溯）",
          "P11TITLE" in meta_text and "title_candidates" in meta_text)
    check("P11 隔离：voice 计划文本无标题/封面候选数据",
          not has_p11_meta(json.dumps(voice_plan, ensure_ascii=False)))
    check("P11 隔离：SRT 文本与文件无标题/封面候选数据",
          not has_p11_meta(sub_data["srt"])
          and not has_p11_meta(srt_file.read_text(encoding="utf-8") if srt_file.exists() else ""))
    check("P11 隔离：烧录字幕源（ASS）无标题/封面候选数据", not has_p11_meta(cap_text))
    check("P11 隔离：朗读稿导出无标题/封面候选数据", not has_p11_meta(narrate_text))
    pkg_obj = json.loads(pkg_text)
    face = json.dumps([{k: p.get(k) for k in ("title", "description", "tags")}
                       for p in (pkg_obj.get("metadata") or {}).get("platforms") or []],
                      ensure_ascii=False)
    check("P11 隔离：发布**面**正文字段（title/description/tags）无标题/封面候选数据",
          bool(face) and not has_p11_meta(face), face[:160])
    body_text = "{} {}".format(pkg_obj.get("platform", ""), pkg_obj.get("video", ""))
    check("P11 隔离：发布清单的正文级字段（platform/video）无候选数据",
          not has_p11_meta(body_text))
    # 如实断言（不隐藏）：发布清单按设计**内嵌** metadata 计划产物（评审留痕），
    # 因此候选字段**会**出现在清单的 metadata 段 —— 这是设计事实，显式断言而非回避。
    check("P11 披露：发布清单按设计内嵌 metadata 计划数据（含候选字段，非泄漏）",
          has_p11_meta(json.dumps(pkg_obj.get("metadata") or {}, ensure_ascii=False)))

    # 可追溯性终检：内部产物与 claims 表未受影响
    check("claims 表与标记链路完好",
          len(db.list_claims(pid)) >= 2
          and any(c["claim_id"] == "c_001" for c in db.list_claims(pid)))

    db.close()
    failed = [c for c in checks if not c[1]]
    print(f"\n结果: {len(checks) - len(failed)}/{len(checks)} 通过")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
