"""5.x Phase 5-E：多模态证据质量校准的**只读**编排（`run.py mm-quality <pid>`）。

只读保证：
  · 数据库以 `mode=ro` 打开；不建任务、不改产物、不写库、不写生产决策、不触发 redo；
  · 抽帧/夹具全部写在**临时目录**（`vs_mmq_*`），不在项目目录内落任何文件；
  · 4-B / 5-A / 5-D 的报告与日志**保持不变**：本层只读取它们的输出并**并列展示**；
  · 结果只打印（可选 `--out`），不写任何生产产物。
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from ..core import mm_quality as Q
from ..core.mm_temporal import MMT_DEFAULTS, validate_temporal
from ..core.multimodal import MM_DEFAULTS, frame_plan, validate
from .metrics import semantic_report
from .mm_temporal import _ffmpeg_from_config, temporal_report
from .multimodal import collect, extract_frames, labels_from_prompts, multimodal_report
from .report import readonly_connection

DEFAULT_TRUTH_SET = "tests/fixtures/mm_truth_set_v1.json"


def _scene_of(rep: dict, sid: str) -> dict | None:
    return next((s for s in (rep.get("scenes") or []) if s.get("scene_id") == sid), None)


def _layer_result_4b(rep: dict, sid: str) -> dict:
    s = _scene_of(rep, sid) or {}
    return {"verdict": s.get("verdict"), "code": s.get("code"), "rule_id": s.get("rule"),
            "metrics": {"rule_id": s.get("rule"), "asset": (s.get("asset") or {}).get("name")}}


def _layer_result_5a(rep: dict, sid: str) -> dict:
    s = _scene_of(rep, sid) or {}
    st = ((rep.get("settings") or {}) if isinstance(rep.get("settings"), dict) else {})
    return {"verdict": s.get("verdict"), "code": s.get("code"),
            "metrics": {"expected_domain": s.get("expected_domain"),
                        "expected_sim": s.get("expected_sim"),
                        "best_other_domain": s.get("best_other_domain"),
                        "best_other_sim": s.get("best_other_sim"), "delta": s.get("delta"),
                        "top_k": s.get("top_k"), "domain_scores": s.get("domain_scores"),
                        "min_sim": st.get("min_sim", MM_DEFAULTS["min_sim"]),
                        "margin_threshold": st.get("margin", MM_DEFAULTS["margin"]),
                        "frames": len(s.get("frames") or [])}}


def _layer_result_5d(rep: dict, sid: str) -> dict:
    s = _scene_of(rep, sid) or {}
    ag, stab = (s.get("aggregate") or {}), (s.get("stability") or {})
    st = (rep.get("settings") or {}) if isinstance(rep.get("settings"), dict) else {}
    return {"verdict": s.get("verdict"), "code": s.get("code"), "rule_id": s.get("rule_id"),
            "confidence": s.get("confidence"),
            "metrics": {"expected_domain": s.get("expected_domain"),
                        "expected_sim_median": ag.get("expected_sim_median"),
                        "expected_sim_min": ag.get("expected_sim_min"),
                        "expected_sim_mean": ag.get("expected_sim_mean"),
                        "median_margin": ag.get("median_margin"),
                        "margin_min": ag.get("margin_min"),
                        "vote_expected": ag.get("vote_expected"),
                        "argmax_votes": ag.get("argmax_votes"),
                        "domains_aggregated": ag.get("domains_aggregated"),
                        "top_k": ag.get("top_k"), "frames": s.get("frame_count"),
                        "visual_stability_mean": stab.get("visual_stability_mean"),
                        "visual_stability_min": stab.get("visual_stability_min"),
                        "adjacent_cos": stab.get("adjacent_cos"),
                        "dispersion": stab.get("dispersion"),
                        "stability": {"class": stab.get("class"), "split": stab.get("split")},
                        "min_sim": st.get("min_sim", MMT_DEFAULTS["min_sim"]),
                        "margin_threshold": st.get("margin", MMT_DEFAULTS["margin"]),
                        "min_vote_frac": st.get("min_vote_frac", MMT_DEFAULTS["min_vote_frac"]),
                        "min_stability_cos": st.get("min_stability_cos",
                                                    MMT_DEFAULTS["min_stability_cos"]),
                        "split_cos": st.get("split_cos", MMT_DEFAULTS["split_cos"]),
                        "high_stability_cos": st.get("high_stability_cos",
                                                     MMT_DEFAULTS["high_stability_cos"])},
            "recompute": _recompute_metrics(s)}


def _recompute_metrics(scene: dict) -> dict:
    """重建 5-D 判定所需的 metrics（供阈值扰动复算；不重跑模型）。"""
    ag, stab = (scene.get("aggregate") or {}), (scene.get("stability") or {})
    return {"frames_used": scene.get("frame_count"), "expected_domain": scene.get("expected_domain"),
            "per_frame": scene.get("frames") or [], "adjacent_cos": stab.get("adjacent_cos") or [],
            "vote_expected": ag.get("vote_expected"), "argmax_votes": ag.get("argmax_votes") or {},
            "visual_stability_mean": stab.get("visual_stability_mean"),
            "visual_stability_min": stab.get("visual_stability_min"),
            "dispersion": stab.get("dispersion"),
            "expected_sim_median": ag.get("expected_sim_median"),
            "expected_sim_min": ag.get("expected_sim_min"),
            "expected_sim_mean": ag.get("expected_sim_mean"),
            "margin_median": ag.get("median_margin"), "margin_min": ag.get("margin_min"),
            "domains_aggregated": ag.get("domains_aggregated") or {}}


def _build_fixtures(root: Path, work: Path, ffmpeg: str | None, project_id: str) -> dict:
    """构造两个受控夹具成片（切图 / 静态），返回 {"split": {...}, "single": {...}} 或 {"error":...}。"""
    fx = root / "src" / "video_studio" / "orchestration" / "tests" / "fixtures"
    img_a = fx / "r2_S30-B02_3.img.jpg"
    sharks = sorted((root / "projects" / project_id / "media" / "external").glob("28160d959ed5*.jpg"))
    if not ffmpeg or not img_a.is_file() or not sharks:
        return {"error": {"code": "MMQ_LAYER_ERROR",
                          "detail": "夹具素材或 ffmpeg 不可用（img_a={} sharks={} ffmpeg={}）".format(
                              img_a.is_file(), len(sharks), bool(ffmpeg))}}
    img_b = sharks[0]
    work.mkdir(parents=True, exist_ok=True)
    split_film, single_film = work / "split.mp4", work / "single.mp4"
    try:
        r1 = subprocess.run([ffmpeg, "-y", "-v", "error", "-loop", "1", "-t", "3", "-i", str(img_a),
                             "-loop", "1", "-t", "3", "-i", str(img_b), "-filter_complex",
                             "[0:v]scale=1280:720,setsar=1[x];[1:v]scale=1280:720,setsar=1[y];"
                             "[x][y]concat=n=2:v=1:a=0[o]", "-map", "[o]", "-r", "30",
                             "-pix_fmt", "yuv420p", str(split_film)], capture_output=True,
                            timeout=300)
        r2 = subprocess.run([ffmpeg, "-y", "-v", "error", "-loop", "1", "-t", "6", "-i", str(img_a),
                             "-vf", "scale=1280:720,setsar=1", "-r", "30", "-pix_fmt", "yuv420p",
                             str(single_film)], capture_output=True, timeout=300)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"error": {"code": "MMQ_LAYER_ERROR",
                          "detail": "夹具生成失败: {}".format(str(exc)[:160])}}
    if r1.returncode != 0 or r2.returncode != 0 or not split_film.is_file() \
            or not single_film.is_file():
        return {"error": {"code": "MMQ_LAYER_ERROR",
                          "detail": "夹具成片未生成（rc={}/{}；stderr={}）".format(
                              r1.returncode, r2.returncode,
                              (r1.stderr or b"")[-160:] if isinstance(r1.stderr, bytes)
                              else str(r1.stderr)[-160:])}}
    scenes = [{"scene_id": "X1", "start_s": 0.0, "end_s": 6.0, "segment_index": 0}]
    plan = frame_plan(scenes, 7)
    labels = [{"id": "{d}#{i}".format(d=d, i=i), "text": t, "domain": d}
              for d in ("geography_nature", "wildlife", "xr_device")
              for i, t in enumerate({"geography_nature": ["a mountain landscape"],
                                     "wildlife": ["a wild animal in nature"],
                                     "xr_device": ["a virtual reality headset device"]}[d])]
    out = {}
    for tag, film in (("split", split_film), ("single", single_film)):
        frames, errs = extract_frames(film, plan, work / tag, ffmpeg=ffmpeg)
        if not frames:
            out[tag] = {"error": {"code": "MMQ_LAYER_ERROR", "detail": "夹具抽帧失败: {}".format(errs[:1])}}
            continue
        rep = validate_temporal(frames, labels, root=root, settings=MMT_DEFAULTS,
                                narration_by_scene={"X1": {"text": "a mountain landscape"}})
        out[tag] = {"report": rep, "scene": (rep.get("scenes") or [{}])[0],
                    "frames": len(frames), "errors": errs}
    out["images"] = [img_a.name, img_b.name]
    return out


def _case_result(case: dict, layers: dict, status_extra: dict | None = None) -> dict:
    evals, boundaries, chains = {}, {}, {}
    for layer in Q.LAYERS:
        if layer not in (case.get("expect") or {}):
            continue
        res = layers.get(layer)
        ev = Q.evaluate_layer(case, layer, res)
        evals[layer] = ev
        boundaries[layer] = Q.boundary_distances(layer, res)
        chains[layer] = Q.explain_chain(case, layer, res, ev)
    violated = any(e.get("violations") for e in evals.values())
    unresolved = any(e.get("unresolved") for e in evals.values())
    return {"case_id": case["id"], "kind": case["kind"], "source": case.get("source"),
            "content_label": case.get("content_label"),
            "content_label_provenance": case.get("content_label_provenance"),
            "covers": case.get("covers"), "layers": evals, "boundary": boundaries,
            "explanation": chains,
            "status": ("UNRESOLVED" if unresolved else ("VIOLATION" if violated else "OK")),
            **(status_extra or {})}


def calibration_report(db_path, project_id: str, *, truth_set_path: str | Path | None = None,
                       config: dict | None = None, root: Path | None = None,
                       frames_dir: Path | None = None, run_layers: bool = True) -> dict:
    """只读校准：真值集 → 三层并列评估 → 指标/冲突/敏感性/可解释链（**不改任何判定**）。"""
    root = Path(root) if root else Path(__file__).resolve().parents[3]
    ts_path = Path(truth_set_path) if truth_set_path else (root / DEFAULT_TRUTH_SET)
    rep: dict = {"schema": Q.QUALITY_SCHEMA, "project_id": project_id,
                 "layers": {k: Q.LAYER_NAMES[k] for k in Q.LAYERS},
                 "evidence_classes": {c: [] for c in Q.EVIDENCE_CLASSES},
                 "cases": [], "metrics": {}, "conflicts": [], "sensitivity": {},
                 "recommendations_5f": Q.recommendations(),
                 "policy": {"mode": "readonly_advisory", "auto_apply": False, "auto_redo": False,
                            "auto_select": False, "auto_replace": False, "writes_to_db": False,
                            "writes_to_production": False, "changes_selection": False,
                            "changes_timeline": False, "changes_thresholds": False,
                            "overwrites_4b_results": False, "overwrites_5a_results": False,
                            "overwrites_5d_results": False, "requires_human_decision": True,
                            "note": ("5-E 只做评估与解释：不改 5-A/5-D 阈值与判定逻辑、"
                                     "不自动换材/选材/redo、不写库；敏感性分析仅披露，不调参")},
                 "note": "只读校准报告：结论仅供参考，任何改动都需人工决定 + 审批"}
    data, err = Q.load_truth_set(ts_path)
    rep["truth_set"] = {"path": str(ts_path), "pin": Q.pin_status(ts_path)}
    if err:
        rep["error"] = err
        rep["fail_closed"] = {"truth_set": err["code"], "cases": 0}
        return rep
    rep["truth_set"].update({"schema": data.get("schema"), "cases": len(data["cases"]),
                            "coverage": Q.coverage_status(data)})
    cov = rep["truth_set"]["coverage"]
    if not cov["ok"]:
        rep["error"] = {"code": cov["code"] or "MMQ_INSUFFICIENT_COVERAGE",
                        "detail": "; ".join(cov["errors"][:8])}
        rep["fail_closed"] = {"coverage": rep["error"]["code"], "cases": 0}
        return rep
    if not run_layers:
        rep["fail_closed"] = {"run_layers": False}
        return rep

    work = Path(frames_dir) if frames_dir else Path(tempfile.mkdtemp(prefix="vs_mmq_"))
    ff = _ffmpeg_from_config(config, root)
    # ---- 按素材分组，三层各跑一次（缓存）----
    artifacts = sorted({c["source"]["artifact_id"] for c in data["cases"]
                        if isinstance(c.get("source"), dict) and c["source"].get("artifact_id")})
    cache: dict = {}
    layer_errors: dict = {}
    con = readonly_connection(db_path)
    try:
        collected = {a: collect(con, project_id, a) for a in artifacts}
        proj = con.execute("select project_id, name, status from projects where project_id=?",
                           (project_id,)).fetchone()
    finally:
        con.close()
    for art in artifacts:
        data_a = collected.get(art) or {}
        narr = {sid: {"text": (v or {}).get("text") or ""}
                for sid, v in (data_a.get("narration") or {}).items()}
        film = (data_a.get("ro_payload") or {}).get("output")
        try:
            rep4b = semantic_report(db_path, project_id, artifact_id=art)
        except Exception as exc:                                     # noqa: BLE001
            rep4b = {"error": {"code": "MMQ_LAYER_ERROR",
                               "detail": "{}: {}".format(type(exc).__name__, str(exc)[:160])}}
        try:
            rep5a = multimodal_report(db_path, project_id, artifact_id=art, config=config,
                                      frames_dir=work / ("5a_" + art), ffmpeg=ff, root=root)
        except Exception as exc:                                     # noqa: BLE001
            rep5a = {"error": {"code": "MMQ_LAYER_ERROR",
                               "detail": "{}: {}".format(type(exc).__name__, str(exc)[:160])}}
        try:
            rep5d = temporal_report(db_path, project_id, artifact_id=art, config=config,
                                    frames_dir=work / ("5d_" + art), ffmpeg=ff, root=root,
                                    with_five_a=False)
        except Exception as exc:                                     # noqa: BLE001
            rep5d = {"error": {"code": "MMQ_LAYER_ERROR",
                               "detail": "{}: {}".format(type(exc).__name__, str(exc)[:160])}}
        cache[art] = {"4b": rep4b, "5a": rep5a, "5d": rep5d, "narration": narr, "film": film}
    fixtures = _build_fixtures(root, work / "fixtures", ff, project_id)

    obs: list = []
    for case in data["cases"]:
        kind = case.get("kind")
        src = case.get("source") or {}
        sid = src.get("scene_id")
        layers: dict = {}
        extra: dict = {}
        if kind in ("real_artifact", "pair") and src.get("artifact_id"):
            art = src["artifact_id"]
            c = cache.get(art) or {}
            if isinstance(c.get("4b"), dict) and not c["4b"].get("error"):
                layers["4b"] = _layer_result_4b(c["4b"], sid)
            for lk, rr in (("5a", c.get("5a")), ("5d", c.get("5d"))):
                if not isinstance(rr, dict):
                    continue
                if rr.get("error"):
                    layers[lk] = {"layer_error": rr["error"]}
                else:
                    layers[lk] = (_layer_result_5a(rr, sid) if lk == "5a"
                                  else _layer_result_5d(rr, sid))
        if kind == "pair":
            pair = src.get("pair") or []
            got = []
            for item in pair:
                c = cache.get(item.get("artifact_id")) or {}
                r5d = c.get("5d") or {}
                s = _scene_of(r5d, item.get("scene_id")) or {}
                got.append({"artifact_id": item.get("artifact_id"),
                            "scene_id": item.get("scene_id"), "verdict": s.get("verdict"),
                            "median_margin": (s.get("aggregate") or {}).get("median_margin"),
                            "vote_expected": (s.get("aggregate") or {}).get("vote_expected")})
            margins = [g["median_margin"] for g in got if g["median_margin"] is not None]
            checks = []
            if len(got) == 2 and len(margins) == 2:
                checks.append({"name": "5d_margin_front_gt_side", "ok": margins[0] > margins[1],
                               "observed": margins})
                checks.append({"name": "both_vote_unanimous_if_available",
                               "ok": all((g["vote_expected"] in (1.0, None)) for g in got),
                               "observed": [g["vote_expected"] for g in got]})
            ev = {"layer": "pair", "expected": case.get("expect", {}).get("pair"),
                  "observed": got, "checks": checks, "resolved": bool(checks),
                  "violations": [c for c in checks if not c["ok"]], "ok": all(c["ok"] for c in checks)}
            extra["pair_evaluation"] = ev
            layers["pair"] = ev
        if kind == "fixture":
            key = "split" if "two_image_cut" == src.get("fixture") else "single"
            fx = fixtures.get(key) or {}
            scene = fx.get("scene")
            if not scene:
                layers["5d"] = {"layer_error": (fx.get("error") or
                                                {"code": "MMQ_LAYER_ERROR", "detail": "夹具不可用"})}
            else:
                rr = {"scenes": [scene], "settings": MMT_DEFAULTS, "error": None}
                layers["5d"] = _layer_result_5d(rr, scene.get("scene_id"))
                extra["fixture"] = {"key": key, "frames": fx.get("frames"),
                                    "images": fixtures.get("images"),
                                    "stability_min": (scene.get("stability") or {}).get(
                                        "visual_stability_min")}
        if kind == "probe":
            fault = src.get("fault")
            art = src.get("artifact_id")
            c = cache.get(art) or {}
            frames_all, _errs = ([], None)
            film = c.get("film")
            if film:
                plan = frame_plan((((c.get("5d") or {}).get("meta") or {}).get("frame_plan") or
                                   [{"scene_id": sid, "start_s": 0.0, "end_s": 1.0}]), 7)
                frames_all, _errs = extract_frames(film, plan, work / ("probe_" + str(case["id"])),
                                                  ffmpeg=ff)
            s_frames = [f for f in frames_all if f.get("scene_id") == sid]
            if not s_frames and sid is None:
                # 用例未指定镜头（如"模型不可用"这类与镜头无关的探针）→ 取成片的第一个镜头
                sid = next((f.get("scene_id") for f in frames_all if f.get("scene_id")), None)
                s_frames = [f for f in frames_all if f.get("scene_id") == sid]
            labels = labels_from_prompts()   # 与生产同一套 36 条标签（12 域）
            # 探针旁白：显式 override 优先，否则用该镜头**真实旁白**（保证期望域可推导）
            text = src.get("narration_override")
            if text is None:
                text = ((c.get("narration") or {}).get(sid) or {}).get("text") or ""
            narr_override = {sid: {"text": text}}
            if fault in ("model_missing", "model_dir_missing"):
                bad = {"model_dir": "models/__no_such_clip__"}
                r5a = validate(s_frames, labels, root=root, settings=bad,
                               narration_by_scene=narr_override, film=film)
                r5d = validate_temporal(s_frames, labels, root=root, settings=bad,
                                        narration_by_scene=narr_override, film=film)
                layers["5a"] = _layer_result_5a(r5a, sid)
                layers["5d"] = _layer_result_5d(r5d, sid)
                layers["5a"]["layer_error"] = None
                layers["5d"]["layer_error"] = None
                extra["probe"] = {"fault": fault, "frames": len(s_frames),
                                  "5a_error": (r5a.get("error") or {}).get("code"),
                                  "5d_error": (r5d.get("error") or {}).get("code")}
            elif fault == "frames_below_min":
                sub = s_frames[:2]
                r5d = validate_temporal(sub, labels, root=root,
                                        settings={**MMT_DEFAULTS, "frames_per_scene": 2},
                                        narration_by_scene=narr_override, film=film)
                layers["5d"] = _layer_result_5d(r5d, sid)
                layers["5d"]["layer_error"] = None
                extra["probe"] = {"fault": fault, "frames": len(sub),
                                  "5d_error": (r5d.get("error") or {}).get("code")}
            elif fault is None:                                   # T12 期望域推不出
                r5a = validate(s_frames, labels, root=root,
                               settings={**MM_DEFAULTS, "enabled": True},
                               narration_by_scene=narr_override, film=film)
                r5d = validate_temporal(s_frames, labels, root=root,
                                        settings={**MMT_DEFAULTS, "enabled": True},
                                        narration_by_scene=narr_override, film=film)
                layers["5a"] = _layer_result_5a(r5a, sid)
                layers["5d"] = _layer_result_5d(r5d, sid)
                layers["5a"]["layer_error"] = None
                layers["5d"]["layer_error"] = None
                extra["probe"] = {"fault": "unknown_domain", "frames": len(s_frames),
                                  "5a_code": (r5a.get("scenes") or [{}])[0].get("code"),
                                  "5d_code": (r5d.get("scenes") or [{}])[0].get("code")}
        cr = _case_result(case, layers, extra)
        rep["cases"].append(cr)
        # 敏感性观测（仅对有域分数/时序指标的层）
        for layer in Q.LAYERS:
            res = layers.get(layer)
            if not isinstance(res, dict) or res.get("layer_error"):
                continue
            m = res.get("metrics") or {}
            if layer == "5a" and m.get("domain_scores"):
                obs.append({"case_id": case["id"], "layer": layer, "kind": "5a",
                            "base_verdict": res.get("verdict"),
                            "payload": {"domain_scores": {x["domain"]: x["sim"]
                                                          for x in m["domain_scores"]},
                                        "expected_domain": m.get("expected_domain")}})
            if layer == "5d" and (res.get("recompute") or {}).get("domains_aggregated"):
                obs.append({"case_id": case["id"], "layer": layer, "kind": "5d",
                            "base_verdict": res.get("verdict"),
                            "payload": {"metrics": res["recompute"],
                                        "expected_domain": m.get("expected_domain")}})

    rep["metrics"] = Q.aggregate(rep["cases"])
    rep["conflicts"] = Q.detect_conflicts(rep["cases"])
    matrix = {"margin": [-0.01, 0.0, 0.01, 0.02, 0.04], "min_stability_cos": [0.0, -0.05, 0.05]}
    rows = Q.sensitivity_rows(obs, matrix)
    rep["sensitivity"] = {
        "matrix": matrix,
        "note": ("阈值扰动**仅供披露**：正数=更严、负数=更松。5-E **不采纳**任何改动；"
                 "「更松」一侧的翻转是'不能用调阈值消除问题'的直接证据。"),
        "rows": rows,
        "flip_summary": [{"case_id": r["case_id"], "layer": r["layer"], "flips": r["flips"]}
                         for r in rows if r["flip_count"]],
        "cases_never_flipping": sorted({r["case_id"] for r in rows} -
                                       {r["case_id"] for r in rows if r["flip_count"]})}
    counts = {c: 0 for c in Q.EVIDENCE_CLASSES}
    for f in Q.FIELD_CLASSES:
        counts[Q.evidence_class(f)] += 1
    rep["evidence_classes"] = {
        "definition": {
            "MODEL_EVIDENCE": "模型直接产出的数值（CLIP 相似度/嵌入/逐帧 argmax/top-k）",
            "RULE_INFERENCE": "由规则推断出的结论（verdict/rule_id/reason/confidence/边际）",
            "ENGINEERING_THRESHOLD": "人工设定的工程阈值（min_sim/margin/vote/stability 等）",
            "UNKNOWN": "无法判定或未登记（不做猜测）"},
        "field_map": Q.FIELD_CLASSES, "field_counts": counts,
        "case_status_counts": {st: sum(1 for c in rep["cases"] if c["status"] == st)
                               for st in ("OK", "VIOLATION", "UNRESOLVED")}}
    unresolved = [c["case_id"] for c in rep["cases"] if c["status"] == "UNRESOLVED"]
    violations = [c["case_id"] for c in rep["cases"] if c["status"] == "VIOLATION"]
    model_unavailable = [c["case_id"] for c in rep["cases"]
                         if case_probe_fault(c) == "model_missing"]
    rep["fail_closed"] = {
        "truth_set_ok": True, "coverage_ok": True,
        "unresolved_cases": unresolved, "violation_cases": violations,
        "conflicts": [c["case_id"] for c in rep["conflicts"]],
        "model_unavailable_cases": model_unavailable,
        "all_cases_resolved": not unresolved,
    }
    rep["meta"] = {
        "project": ({"project_id": proj["project_id"], "name": proj["name"]}
                    if proj is not None else None),
        "artifacts_used": artifacts, "frames_dir": str(work),
        "readonly": True, "db_writes": 0, "production_writes": 0,
        "layers_run": {"4b": len(artifacts), "5a": len(artifacts), "5d": len(artifacts)},
        "fixtures": ("ok" if (fixtures.get("split") or {}).get("scene")
                     and (fixtures.get("single") or {}).get("scene") else "unavailable"),
    }
    return rep


def case_probe_fault(case: dict) -> str | None:
    if case.get("kind") != "probe":
        return None
    return ((case.get("source") or {}).get("fault")) or "unknown_domain"


def format_mmq(rep: dict) -> str:
    """人读输出：并列展示三层结果 + 证据等级 + 边界距离 + 5-F 建议。"""
    if rep.get("error"):
        return "校准未完成：{} — {}".format(rep["error"].get("code"), rep["error"].get("detail"))
    ts = rep.get("truth_set") or {}
    lines = ["# 多模态证据质量校准（只读评估；不改任何判定逻辑 / 不调阈值）",
             "真值集 {}（{} 例，指纹 {}） 覆盖：{}".format(
                 ts.get("path"), ts.get("cases"), (ts.get("pin") or {}).get("sha256", "")[:16],
                 (ts.get("coverage") or {}).get("coverage")),
             "层：{}".format("；".join("{}={}".format(k, v) for k, v in (rep.get("layers") or {}).items()))]
    for c in rep.get("cases") or []:
        lines.append("· {} [{}] 内容标签={}".format(c["case_id"], c["status"], c["content_label"]))
        for layer in ("4b", "5a", "5d", "pair"):
            e = (c.get("layers") or {}).get(layer)
            if not e:
                continue
            obs = e.get("observed")
            lines.append("    {:<4s} {}".format(layer, obs if obs else
                                                ("UNRESOLVED: {}".format(e.get("unresolved")))))
        lines.append("    可解释链：")
        for layer, chain in (c.get("explanation") or {}).items():
            for ln in chain:
                lines.append("      {}: {}".format(layer, ln))
    m = rep.get("metrics") or {}
    lines.append("")
    lines.append("指标（按层）：")
    for layer, v in m.items():
        lines.append("  {:<4s} 用例={} 违例={} UNKNOWN={} MATCH={} MISMATCH={} "
                     "MATCH精确率={} MISMATCH召回={}".format(
                         layer, v["cases_with_expectation"], v["violation_count"],
                         v["unknown_count"], v["match_count"], v["mismatch_count"],
                         v["match_precision_on_truth"], v["mismatch_recall_on_truth"]))
    lines.append("冲突：{}".format(rep.get("conflicts") or "无"))
    lines.append("")
    lines.append("5-F 建议（**仅建议，未实施**）：")
    for r in rep.get("recommendations_5f") or []:
        lines.append("  [{}] {} —— {}".format(r["id"], r["title"], r["why"][:100]))
    lines.append("")
    lines.append("（只读：未写数据库/未写产物/未改选材·时间轴·阈值/未触发 redo；"
                 "4-B 与 5-A/5-D 结果原样保留）")
    return "\n".join(lines)
