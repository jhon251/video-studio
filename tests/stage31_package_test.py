"""Stage 3.1 Material Package 测试（G7/G8/G9/G10：硬门槛、NO_SAFE_MATCH、
Shot→Material 映射、provenance、人工状态）。离线合成 fixture，不联网。"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from video_studio.stage31.package import build_package          # noqa: E402
from video_studio.stage31.sources import Candidate, SearchOutcome  # noqa: E402
from video_studio.stage31.visual_intent import VisualIntent      # noqa: E402
from video_studio.stage31.ranking import set_rank_mode           # noqa: E402

set_rank_mode("lexical")  # fixture 测试使用确定性模式（不依赖本地语义模型）


def intent(sid, sec, mtype, mkind, role):
    return VisualIntent(
        shot_id=sid, section=sec, role=role, beat="",
        match_type=mtype, material_kind=mkind,
        subject="test subject", action="test action", object="test object",
        environment="test env", concept="test concept", visual_relationship="",
        mood="test", temporal_context="", abstraction_level="literal",
        preferred_media_type="image", camera_style="wide",
        preferred_duration=10.0, avoid_list=["space"],
        queries_en=["test query"], queries_zh=["测试"],
        query_ladder=[("literal", ["test query"]), ("conceptual", ["test query"]),
                      ("metaphorical", ["test query"])],
        concepts_pos=["test", "subject"], concepts_neg=["space"],
        evidence_refs=[], narration="测试口播", rationale="fixture")


def cand(url, lic, w=1920, creator="作者", desc="test subject query 测试描述"):
    return Candidate(
        source="wikimedia_commons", source_url=url, original_url=url,
        download_url="https://upload.wikimedia.org/x.jpg",
        source_name="Wikimedia Commons", creator=creator, license=lic,
        license_url="https://example.org/license", content_type="image",
        width=w, height=1080, visual_description=desc,
        raw={"title": "File:test.jpg"})


def main() -> int:
    checks = []

    def check(name, cond, detail=""):
        checks.append((name, cond))
        print(f"{'PASS' if cond else 'FAIL'}  {name} {detail}")

    intents = [
        intent("S01", "开头", "RHYTHM", "broll", "hook"),
        intent("S02", "会聊天", "DIRECT", "broll", "body"),
        intent("S03", "结尾", "EVIDENCE", "evidence", "body"),
        intent("S04", "能拥有身体", "CONCEPTUAL", "broll", "body"),
        intent("S05", "结尾", "SELF_MADE", "none", "gap"),
    ]
    outcomes = {
        "S01": [SearchOutcome(query="test query", source="wikimedia_commons", status="OK", candidates=[
            cand("https://www.youtube.com/watch?v=x", "CC0"),          # UNSAFE 域
            cand("https://example.com/nolic.jpg", ""),                 # UNKNOWN
            cand("https://commons.wikimedia.org/wiki/File:Safe.jpg", "CC0"),  # SAFE
        ])],
        "S02": [SearchOutcome(query="test query", source="wikimedia_commons", status="OK", candidates=[
            cand("https://commons.wikimedia.org/wiki/File:By.jpg", "CC BY 4.0"),  # CONDITIONAL
        ])],
        "S04": [SearchOutcome(query="test query", source="wikimedia_commons", status="OK", candidates=[
            cand("https://www.bilibili.com/video/x", "CC0"),           # UNSAFE
            cand("https://example.com/x.jpg", "mystery license"),      # UNKNOWN
        ])],
    }

    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "pkg"
        result = build_package(intents, outcomes, {"references": []}, out,
                               {"wikimedia_commons": "OK"}, {"input": "fixture"})
        check("G10 包输出成功", (out / "README.md").exists())
        for sub in ("materials", "metadata", "rights", "shot_mapping", "search_log"):
            check(f"目录存在 {sub}", (out / sub).is_dir())

        mat = json.loads((out / "metadata" / "materials.json").read_text(encoding="utf-8"))["materials"]
        mapping = json.loads((out / "shot_mapping" / "all_shots.json").read_text(encoding="utf-8"))["shots"]

        # G7: UNSAFE/UNKNOWN 不进推荐位
        s01 = mapping["S01"]
        pool_ids = [s01["primary"]["material_id"]] + [a["material_id"] for a in s01["alternatives"]]
        pool_recs = [m for m in mat if m["material_id"] in pool_ids]
        check("G7 推荐池全部 SAFE", all(m["rights_status"] == "SAFE" for m in pool_recs),
              str([(m["material_id"], m["rights_status"]) for m in pool_recs]))
        unsafe_in_meta = [m for m in mat if m["rights_status"] in ("UNSAFE", "UNKNOWN")]
        check("UNSAFE/UNKNOWN 在 metadata 中被淘汰记录", len(unsafe_in_meta) == 4,
              f"({len(unsafe_in_meta)})")
        check("被淘汰者 match_score=None", all(m["match_score"] is None for m in unsafe_in_meta))

        # CONDITIONAL 处理
        s02 = mapping["S02"]
        check("S02 primary 为 CONDITIONAL 且注明署名", s02["primary"]["rights_status"] == "CONDITIONAL"
              and s02["primary"]["attribution_text"], s02["primary"]["attribution_text"])
        check("S02 note 提示署名", "署名" in s02.get("note", ""))

        # G8: NO_SAFE_MATCH
        no_safe = json.loads((out / "shot_mapping" / "all_shots.json").read_text(encoding="utf-8"))["no_safe_match"]
        check("G8 NO_SAFE_MATCH 记录 S04", any(n["shot_id"] == "S04" for n in no_safe))
        ns = next(n for n in no_safe if n["shot_id"] == "S04")
        check("NO_SAFE_MATCH 含检索词/来源/淘汰原因/自制建议",
              ns["searched_queries"] and ns["searched_sources"] and ns["rejected_candidates"] == 2
              and ns["recommendation"], json.dumps(ns, ensure_ascii=False)[:200])

        # G9: Evidence 与 gap 镜处理
        check("S03 evidence 分离（不搜 b-roll）",
              "Truth/Evidence" in mapping["S03"].get("note", ""))
        check("S05 占位镜无素材需求", "占位镜" in mapping["S05"].get("note", ""))

        # provenance 字段完整性（§六）
        for m in mat:
            missing = [k for k in ("material_id", "shot_id", "source_url", "original_url",
                                   "source_name", "creator", "license", "rights_status",
                                   "commercial_use", "attribution_required", "attribution_text",
                                   "download_url", "retrieved_at", "content_type", "resolution",
                                   "visual_description", "match_type", "copyright_notes")
                       if k not in m]
            check(f"{m['material_id']} provenance 字段完整", not missing, str(missing))

        # 人工状态默认 NEEDS_REVIEW
        check("人工状态默认 NEEDS_REVIEW",
              all(m.get("review_status") == "NEEDS_REVIEW" for m in mat))

    failed = [c for c in checks if not c[1]]
    print(f"\n结果: {len(checks) - len(failed)}/{len(checks)} 通过")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
