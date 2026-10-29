"""Phase 2-D 故障矩阵：10 类外部素材故障在**真实项目**中的端到端行为。

每个用例：建真实项目 → 配置 local_catalog provider（目录内放一条"命中但故障"的候选）
→ 跑真实 retrieval（经 provider 层下载+校验）→ 跑真实 render → 断言：

  · 有明确错误码/状态（候选 REJECTED + error_code）
  · 不进入正常 ffmpeg 渲染（无成片；render BLOCKED）
  · 不被标记为正常素材命中（不在 candidates 里，external_verified=0）
  · 按定义进入 fallback / HITL / BLOCKED（许可证用例额外挂一个本地素材，验证降级到 local_ingest）

超时/404/500/空响应通过**进程内替换传输层**注入（与 Phase 2-B.1 的注入方式一致，不改生产代码）。

用法：python docs/regression_2x/phase2d_boundary_matrix.py
"""
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.agents.base import AGENTS  # noqa: E402
from video_studio.core.engine import Engine  # noqa: E402
from video_studio.db.schema import Database  # noqa: E402
from video_studio.llm.router import MockLLM, Router  # noqa: E402
from video_studio.tools import material_provider as mp  # noqa: E402

import video_studio.agents.asset.agent  # noqa: E402,F401
import video_studio.agents.editing.agent  # noqa: E402,F401
import video_studio.agents.retrieval.agent  # noqa: E402,F401
import video_studio.agents.script.agent  # noqa: E402,F401

LOGS = ROOT / "docs" / "regression_2x" / "logs"
REAL_IMG = ROOT / "output" / "run03" / "asset_cache" / "files" / "r3_S01-B01_3.img.jpg"
SCRIPT = {"segments": [{"chapter": "外部段", "narration": "皮肤界面截图展示鲸鱼娘皮肤。",
                        "duration_s": 4}], "summary": "Phase 2-D boundary matrix"}
PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(("PASS  " if ok else "FAIL  ") + name + (" | " + str(detail)[:200] if detail else ""))


class FakeTransport:
    """按 URL 返回预置结果；用于超时/HTTP 错误/空响应注入。"""

    def __init__(self, mode: str):
        self.mode = mode

    def get(self, url, max_bytes, timeout_s):
        if self.mode == "timeout":
            raise mp.TransportError("PROVIDER_TIMEOUT", "模拟超时")
        if self.mode == "http_404":
            raise mp.TransportError("PROVIDER_HTTP_404", "模拟 404")
        if self.mode == "http_500":
            raise mp.TransportError("PROVIDER_HTTP_5XX", "模拟 500")
        if self.mode == "empty":
            raise mp.TransportError("PROVIDER_EMPTY_RESPONSE", "模拟空响应")
        raise mp.TransportError("PROVIDER_DOWNLOAD_FAILED", "no plan")


def build_case(name, entry, *, mode=None, local_asset=False, policy=None, content=None):
    work = Path(tempfile.mkdtemp(prefix="vs_p2d_bm_"))
    cat = work / "catalog"
    cat.mkdir(parents=True, exist_ok=True)
    if content is not None:
        (cat / "payload.jpg").write_bytes(content)
        entry = {**entry, "file": str(cat / "payload.jpg")}
    (cat / "catalogue.json").write_text(json.dumps({"items": [entry]}, ensure_ascii=False),
                                        encoding="utf-8")
    cfg = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8"))
    rules = json.loads((ROOT / "config" / "rules.json").read_text(encoding="utf-8"))
    cfg["tools"]["material"] = {"provider": "local_catalog", "catalog": str(cat), **(policy or {})}
    eng = Engine(Database(ROOT / "projects" / "video_studio.db"),
                 Router(cfg["llm"], MockLLM(cfg["llm"].get("mock", {}).get("responses", {}),
                                            cfg["llm"].get("mock", {}).get("default", {}))),
                 rules, ROOT / "projects", cfg, AGENTS)
    pid = eng.create_project("test_phase2d_" + name)
    src = Path(tempfile.mkdtemp(prefix="vs_p2d_src_"))
    if local_asset:
        shutil.copy2(REAL_IMG, src / "皮肤界面截图_本地.jpg")
        subprocess.run([sys.executable, "run.py", "--config", "config/config.json", "ingest",
                        pid, str(src)], cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    t_script = eng.create_task(pid, "script", "script")
    aid = eng.write_artifact(pid, t_script, "script_output", SCRIPT, summary="脚本")
    eng.attach_artifact(t_script, aid)
    eng.db.set_task_status(t_script, "SUCCEEDED")

    orig = mp.UrllibTransport
    if mode:
        mp.UrllibTransport = lambda policy: FakeTransport(mode)      # 仅本进程内注入
    try:
        t_ret = eng.create_task(pid, "retrieval", "retrieval", dependencies=[t_script])
        eng.run_cycle(pid, limit=4)
        t_rend = eng.create_task(pid, "render", "editing", dependencies=[t_script, t_ret])
        for _ in range(4):
            eng.run_cycle(pid, limit=4)
            if eng.db.get_task(t_rend)["status"] not in ("PENDING", "DISPATCHED", "RUNNING"):
                break
    finally:
        mp.UrllibTransport = orig

    con = sqlite3.connect(str(ROOT / "projects" / "video_studio.db"))
    con.row_factory = sqlite3.Row

    def art(tid, tp):
        r = con.execute("select * from artifacts where task_id=? and type=? "
                        "order by created_at desc limit 1", (tid, tp)).fetchone()
        return json.loads(Path(r["path"]).read_text(encoding="utf-8")) if r else None

    row = dict(con.execute("select status, error from tasks where task_id=?", (t_rend,)).fetchone())
    ret_payload, ren_payload = art(t_ret, "retrieval_candidates"), art(t_rend, "render_output")
    con.close()
    vids = sorted((ROOT / "projects" / pid / "output").glob("*.mp4"))
    return {"case": name, "project": pid, "retrieval": ret_payload,
            "render": ren_payload, "render_status": row["status"],
            "render_error": row["error"], "films": [str(v) for v in vids]}


CASES = {
    # ---- 传输层故障（进程内注入）----
    "timeout": dict(entry={"source_id": "ext-t", "name": "皮肤界面截图_t.jpg",
                           "url": "https://example.invalid/t.jpg", "license": "CC0"},
                    mode="timeout", expect="PROVIDER_TIMEOUT"),
    "http_404": dict(entry={"source_id": "ext-404", "name": "皮肤界面截图_404.jpg",
                            "url": "https://example.invalid/404.jpg", "license": "CC0"},
                     mode="http_404", expect="PROVIDER_HTTP_404"),
    "http_500": dict(entry={"source_id": "ext-500", "name": "皮肤界面截图_500.jpg",
                            "url": "https://example.invalid/500.jpg", "license": "CC0"},
                     mode="http_500", expect="PROVIDER_HTTP_5XX"),
    "empty_response": dict(entry={"source_id": "ext-e", "name": "皮肤界面截图_e.jpg",
                                  "url": "https://example.invalid/e.jpg", "license": "CC0"},
                           mode="empty", expect="PROVIDER_EMPTY_RESPONSE"),
    # ---- 文件层故障（真实文件）----
    "corrupt_file": dict(entry={"source_id": "ext-c", "name": "皮肤界面截图_c.jpg",
                                "license": "CC0"},
                         content=b"\xff\xd8\xff\xe0" + b"\x00" * 400,
                         expect=("ASSET_TRUNCATED", "ASSET_PROBE_FAILED", "ASSET_DECODE_FAILED",
                                 "ASSET_FFMPEG_DECODE_FAILED")),
    "non_media_masquerade": dict(entry={"source_id": "ext-n", "name": "皮肤界面截图_n.jpg",
                                        "license": "CC0"},
                                 content="这不是图片，只是文本，伪装成 jpg。".encode("utf-8") * 40,
                                 expect=("ASSET_TYPE_MISMATCH",)),
    "oversize": dict(entry={"source_id": "ext-o", "name": "皮肤界面截图_o.jpg",
                            "file": str(REAL_IMG), "license": "CC0"},
                     policy={"max_bytes": 2048}, expect=("ASSET_OVERSIZE",)),
    "ffprobe_decode_fail": dict(entry={"source_id": "ext-d", "name": "皮肤界面截图_d.jpg",
                                       "license": "CC0"},
                                content=(REAL_IMG.read_bytes()[:2048]),
                                expect=("ASSET_TRUNCATED", "ASSET_PROBE_FAILED",
                                        "ASSET_FFMPEG_DECODE_FAILED", "ASSET_DECODE_FAILED")),
    # ---- 许可证 / 危险文件名（可降级：同时挂一个本地素材）----
    "missing_license": dict(entry={"source_id": "ext-l", "name": "皮肤界面截图_l.jpg",
                                   "file": str(REAL_IMG)},
                            local_asset=True, expect=("ASSET_LICENSE_MISSING",)),
    "dangerous_filename": dict(entry={"source_id": "ext-x", "name": "../皮肤界面截图_x.jpg",
                                      "file": str(REAL_IMG), "license": "CC0"},
                               expect=("ASSET_DANGEROUS_FILENAME",)),
}


def main():
    out = []
    for name, spec in CASES.items():
        print("\n=== {} ===".format(name))
        r = build_case(name, spec["entry"], mode=spec.get("mode"),
                       local_asset=spec.get("local_asset", False),
                       policy=spec.get("policy"), content=spec.get("content"))
        ret = r.get("retrieval") or {}
        rejected = ret.get("external_rejected") or []
        cands = ret.get("candidates") or []
        codes = [x.get("error_code") for x in rejected]
        expect = spec["expect"] if isinstance(spec["expect"], tuple) else (spec["expect"],)
        print("  retrieval: mode={} verified={} rejected={} codes={}".format(
            ret.get("material_mode"), ret.get("external_verified"), len(rejected), codes))
        print("  render: {} | films={}".format(r["render_status"], len(r["films"])))
        if r.get("render_error"):
            print("  render_error:", str(r["render_error"])[:160])
        check("{}: 明确错误码 {}".format(name, "/".join(expect)),
              any(c in expect for c in codes if c), codes)
        check("{}: 未被标记为正常命中（external_verified=0 且不在 candidates）".format(name),
              ret.get("external_verified") == 0
              and not any(c.get("provider") == "local_catalog" for c in cands),
              {"verified": ret.get("external_verified"),
               "cand_providers": [c.get("provider") for c in cands]})
        check("{}: 被拒候选未落盘（downloaded_path 为空）".format(name),
              all(not x.get("downloaded_path") for x in rejected), [x.get("downloaded_path")
                                                                    for x in rejected])
        if spec.get("local_asset"):
            # 可降级用例：外部失败 → 退回本地素材，仍出片（fallback 定义）
            tl = (r.get("render") or {}).get("material_timeline") or []
            s1 = tl[0] if tl else {}
            check("{}: 降级到 local_ingest 并出片 + 许可证候选记 HITL".format(name),
                  bool(r["films"]) and s1.get("fallback_state") == "LOCAL_INGEST"
                  and s1.get("needs_hitl") is True and s1.get("license_pending") is True,
                  {"films": len(r["films"]), "state": s1.get("fallback_state"),
                   "hitl": s1.get("needs_hitl"), "license_pending": s1.get("license_pending")})
        else:
            check("{}: 不进入 ffmpeg 渲染（无成片 + render BLOCKED）".format(name),
                  not r["films"] and r["render_status"] == "BLOCKED"
                  and "[ASSET_INSUFFICIENT]" in (r.get("render_error") or ""),
                  {"status": r["render_status"], "films": len(r["films"])})
        out.append(r)
    (LOGS / "phase2d_boundary_matrix.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print("\n结果: {}/{} 通过".format(len(PASS), len(PASS) + len(FAIL)))
    if FAIL:
        print("失败项:", FAIL)
    print("记录:", LOGS / "phase2d_boundary_matrix.json")
    return 0 if not FAIL else 1


if __name__ == "__main__":
    sys.exit(main())
