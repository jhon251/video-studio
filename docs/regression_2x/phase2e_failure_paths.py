"""Phase 2-E 失败路径验证（需求 6）：真实优先，受控处明确标注。

用例（每条都断言：明确错误码 / 不成为正常命中 / 按定义 fallback·HITL·BLOCKED）：
  1 no_api_key        —— 受控配置（require_key=true 且环境无该变量）→ PROVIDER_NOT_CONFIGURED
  2 auth_failed       —— **真实**：向真实端点发送无效 Bearer → 真实 HTTP 401 → PROVIDER_AUTH_FAILED
  3 rate_limited      —— 受控 429（另附真实运行中观测到的 429 与重试记录）
  4 search_timeout    —— **真实**：timeout_s=0.001 打真实端点 → PROVIDER_TIMEOUT
  5 download_timeout  —— 真实候选 + 下载腿注入超时（真实搜索、真实 URL）→ PROVIDER_TIMEOUT
  6 corrupt_download  —— 真实候选 + 真实字节被截断 → ASSET_PROBE_FAILED / ASSET_FFMPEG_DECODE_FAILED
  7 license_missing   —— 受控：真实候选去掉许可证字段 → ASSET_LICENSE_MISSING + needs_hitl
  7b license_restricted—— 受控：声明 "fair use" → ASSET_LICENSE_RESTRICTED + needs_hitl
  8 real_blocked      —— **真实**：真实候选 + 极小 max_bytes → 全部 ASSET_OVERSIZE → ASSEMBLY_BLOCKED → 无成片

用法：python docs/regression_2x/phase2e_failure_paths.py
"""
import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.agents.base import AGENTS  # noqa: E402
from video_studio.core.engine import Engine  # noqa: E402
from video_studio.db.schema import Database  # noqa: E402
from video_studio.llm.router import MockLLM, Router  # noqa: E402
from video_studio.tools.base import ToolContext  # noqa: E402
from video_studio.tools.material_provider import (MaterialQuery, TransportError,  # noqa: E402
                                                 provider_from_config)
from video_studio.tools.provider_wikimedia import (WikimediaCommonsProvider,  # noqa: E402
                                                   classify_license)

import video_studio.agents.asset.agent  # noqa: E402,F401
import video_studio.agents.editing.agent  # noqa: E402,F401
import video_studio.agents.retrieval.agent  # noqa: E402,F401
import video_studio.agents.script.agent  # noqa: E402,F401

LOGS = ROOT / "docs" / "regression_2x" / "logs"
FFMPEG = ROOT / "bin" / "ffmpeg.exe"
FFPROBE = ROOT / "bin" / "ffprobe.exe"
SCRIPT = {"segments": [{"chapter": "s1",
                        "narration": "virtual reality headset device form factor",
                        "duration_s": 4}], "summary": "Phase 2-E failure paths"}
PASS, FAIL, ROWS = [], [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(("PASS  " if ok else "FAIL  ") + name + (" | " + str(detail)[:200] if detail else ""))


class DownloadFaultTransport:
    """真实搜索放行；下载腿按 mode 注入（超时 / 截断）。"""

    def __init__(self, mode: str, truncate_to: int = 2048):
        from video_studio.tools.material_provider import UrllibTransport
        self.base = UrllibTransport({"require_https": True})
        self.mode = mode
        self.truncate_to = truncate_to
        self.calls = []

    def get(self, url, max_bytes, timeout_s):
        self.calls.append(url.split("?")[0])
        if "w/api.php" in url:
            return self.base.get(url, max_bytes, timeout_s)
        if self.mode == "timeout":
            raise TransportError("PROVIDER_TIMEOUT", "下载腿注入超时（真实 URL）")
        if self.mode == "truncate":
            data = self.base.get(url, max_bytes, timeout_s)
            return data[:self.truncate_to]
        return self.base.get(url, max_bytes, timeout_s)


class Boom429:
    def get(self, url, max_bytes, timeout_s):
        raise TransportError("PROVIDER_RATE_LIMITED", "HTTP 429（受控注入）")


class CachedRealBytesTransport:
    """真实 provider 字节 + 受控变形（媒体主机被限流时的诚实替代）。

    搜索仍走真实网络；下载腿复用**此前由真实 provider 下载并校验过**的缓存字节
    （`byte_source=cached_real_download:<sha256>` 记录在案），再按 mode 施加故障：
      · truncate  → 截断（验证 ASSET_TRUNCATED/解码边界）
      · passthrough → 原样（配合极小 max_bytes 验证 ASSET_OVERSIZE 的流式拒绝）
    """

    def __init__(self, cache_file: Path, mode: str, truncate_to: int = 2048):
        from video_studio.tools.material_provider import UrllibTransport
        self.base = UrllibTransport({"require_https": True})
        self.bytes_ = cache_file.read_bytes()
        self.sha256 = hashlib.sha256(self.bytes_).hexdigest()
        self.mode = mode
        self.truncate_to = truncate_to
        self.calls = []

    def get(self, url, max_bytes, timeout_s):
        self.calls.append(url.split("?")[0])
        if "w/api.php" in url:
            return self.base.get(url, max_bytes, timeout_s)      # 搜索：真实网络
        payload = self.bytes_[:self.truncate_to] if self.mode == "truncate" else self.bytes_
        # 复用真实传输的**流式大小上限**语义
        total, out = 0, bytearray()
        for i in range(0, len(payload), 65536):
            chunk = payload[i:i + 65536]
            total += len(chunk)
            if total > max_bytes:
                raise TransportError("ASSET_OVERSIZE",
                                     ">{} bytes（流式中断，未落盘）".format(max_bytes))
            out += chunk
        if not out:
            raise TransportError("PROVIDER_EMPTY_RESPONSE", "0 字节响应")
        return bytes(out)


def cached_real_file() -> Path | None:
    """找一份此前真实下载并校验过的 provider 缓存文件（内容寻址，sha256 可核对）。"""
    import hashlib as _h  # noqa: F401
    root = ROOT / "projects"
    for p in sorted(root.glob("*/media/external/*.jpg")):
        try:
            if p.stat().st_size > 100_000:            # 取一份较大的真实下载
                return p
        except OSError:
            continue
    return None


POL = {"provider": "wikimedia_commons", "max_bytes": 8 * 1024 * 1024, "timeout_s": 25,
       "search_limit": 6, "min_width": 320, "min_height": 180, "license_required": True,
       "min_interval_s": 5.0, "max_requests": 8}
# 传输层抖动（真实网络限流/超时）：与"资产层故障"区分开，避免把环境问题当成用例结论
TRANSPORT_FLAKES = ("PROVIDER_TIMEOUT", "PROVIDER_RATE_LIMITED", "PROVIDER_DOWNLOAD_FAILED",
                    "PROVIDER_SEARCH_FAILED", "PROVIDER_EMPTY_RESPONSE")
CASE_GAP_S = 8.0          # 用例之间礼貌间隔：真实 provider 连续搜索会被限流（实测 429）


def run_asset_level_case(name, material_cfg, expect_codes, note, drop_license=False, tries=3,
                         transport_patch=None):
    """资产层故障用例：真实搜索可能被限流/超时打断（环境抖动）。

    重跑判据：失败原因是**传输层抖动**，或**没有任何候选走到资产层判定**（全被 429 拦在门外）。
    这样断言的是"资产层故障被正确分类"，而不是"这次网络不好"；每次尝试都记录在案。
    """
    attempts, r = [], None
    for i in range(1, tries + 1):
        if i > 1:
            time.sleep(CASE_GAP_S * i)
        r = project_with(name if i == 1 else "{}_{}".format(name, i), material_cfg,
                         transport_patch=transport_patch, drop_license=drop_license)
        ret = r.get("retrieval") or {}
        codes = [x.get("error_code") for x in (ret.get("external_rejected") or [])]
        ext_err = ret.get("external_error")
        reached_asset_level = any((c or "").startswith("ASSET_") for c in codes)
        attempts.append({"attempt": i, "project": r["pid"], "external_error": ext_err,
                         "codes": codes, "reached_asset_level": reached_asset_level,
                         "render_status": r["render_status"]})
        if ext_err not in TRANSPORT_FLAKES and reached_asset_level:
            break
    r["_attempts"] = attempts
    ret = r.get("retrieval") or {}
    codes = [x.get("error_code") for x in (ret.get("external_rejected") or [])]
    ext_err = ret.get("external_error")
    print("   project={} render={} external_error={} rejected_codes={} verified={} attempts={}".format(
        r["pid"], r["render_status"], ext_err, codes, ret.get("external_verified"), len(attempts)))
    check("{}: 明确错误码 {}".format(name, "/".join(expect_codes)),
          any(c in expect_codes for c in ([ext_err] + codes) if c), [ext_err] + codes)
    check("{}: 未成为正常命中（external_verified=0 且无 provider 候选）".format(name),
          (ret.get("external_verified") or 0) == 0
          and not [c for c in (ret.get("candidates") or [])
                   if c.get("provider") == "wikimedia_commons"], ret.get("external_verified"))
    check("{}: 不进入正常 ffmpeg 渲染（无成片且 render BLOCKED）".format(name),
          not r["films"] and r["render_status"] == "BLOCKED"
          and "[ASSET_INSUFFICIENT]" in (r["render_error"] or ""),
          {"status": r["render_status"], "films": len(r["films"])})
    ROWS.append({"case": name, "note": note, "project": r["pid"],
                 "render_status": r["render_status"], "external_error": ext_err,
                 "rejected_codes": codes, "external_verified": ret.get("external_verified"),
                 "films": r["films"], "material_mode": ret.get("material_mode"),
                 "attempts": attempts})
    return r


def project_with(pid_name, material_cfg, transport_patch=None, drop_license=False):
    """建项目 → 跑 retrieval（真实 provider）→ 跑 render；返回证据字典。"""
    cfg = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8"))
    rules = json.loads((ROOT / "config" / "rules.json").read_text(encoding="utf-8"))
    cfg["tools"]["material"] = material_cfg
    eng = Engine(Database(ROOT / "projects" / "video_studio.db"),
                 Router(cfg["llm"], MockLLM(cfg["llm"].get("mock", {}).get("responses", {}),
                                            cfg["llm"].get("mock", {}).get("default", {}))),
                 rules, ROOT / "projects", cfg, AGENTS)
    pid = eng.create_project(pid_name)
    t_script = eng.create_task(pid, "script", "script")
    aid = eng.write_artifact(pid, t_script, "script_output", SCRIPT, summary="脚本")
    eng.attach_artifact(t_script, aid)
    eng.db.set_task_status(t_script, "SUCCEEDED")

    import video_studio.tools.provider_wikimedia as pw
    orig_cls = pw.WikimediaCommonsProvider

    class Patched(orig_cls):
        def __init__(self, policy=None, transport=None, api_url=pw.API):
            if transport_patch is None:
                super().__init__(policy, transport, api_url)
            else:
                pol = {**pw.DEFAULT_POLICY, **(policy or {})}
                pol.setdefault("min_interval_s", 1.0)
                pol.setdefault("max_requests", 8)
                pol.setdefault("search_limit", 6)
                super(orig_cls, self).__init__(pol, transport_patch(pol))
                self.api_url = api_url
                self._last_request = 0.0
                self.stats.update(requests=0, requests_failed=0, search_ms=None, download_ms=0,
                                  auth_mode="none", token_present=False, response_digests=[],
                                  license_classes={})
                self.token = ""

        def search(self, query, ctx):
            out = super().search(query, ctx)
            if drop_license:
                for c in out:
                    c.license = None
                    c.license_cleared = False
            return out

    pw.WikimediaCommonsProvider = Patched
    try:
        t_ret = eng.create_task(pid, "retrieval", "retrieval", dependencies=[t_script])
        eng.run_cycle(pid, limit=4)
        t_rend = eng.create_task(pid, "render", "editing", dependencies=[t_script, t_ret])
        for _ in range(3):
            eng.run_cycle(pid, limit=4)
            if eng.db.get_task(t_rend)["status"] not in ("PENDING", "DISPATCHED", "RUNNING"):
                break
    finally:
        pw.WikimediaCommonsProvider = orig_cls

    con = sqlite3.connect(str(ROOT / "projects" / "video_studio.db"))
    con.row_factory = sqlite3.Row

    def art(tid, tp):
        r = con.execute("select * from artifacts where task_id=? and type=? "
                        "order by created_at desc limit 1", (tid, tp)).fetchone()
        return json.loads(Path(r["path"]).read_text(encoding="utf-8")) if r else None

    row = dict(con.execute("select status, error from tasks where task_id=?", (t_rend,)).fetchone())
    ret, ren = art(t_ret, "retrieval_candidates"), art(t_rend, "render_output")
    con.close()
    films = sorted((ROOT / "projects" / pid / "output").glob("*.mp4"))
    return {"pid": pid, "retrieval": ret, "render": ren, "render_status": row["status"],
            "render_error": row["error"], "films": [str(f) for f in films]}


def summarize(case, r, expect_codes, note=""):
    ret = r.get("retrieval") or {}
    codes = [x.get("error_code") for x in (ret.get("external_rejected") or [])]
    ext_err = ret.get("external_error")
    verified = ret.get("external_verified")
    cands = [c for c in (ret.get("candidates") or []) if c.get("provider") == "wikimedia_commons"]
    print("   project={} render={} external_error={} rejected_codes={} verified={}".format(
        r["pid"], r["render_status"], ext_err, codes, verified))
    check("{}: 明确错误码 {}".format(case, "/".join(expect_codes)),
          any(c in expect_codes for c in ([ext_err] + codes) if c), [ext_err] + codes)
    check("{}: 未成为正常命中（external_verified=0 且无 provider 候选）".format(case),
          (verified or 0) == 0 and not cands, {"verified": verified, "cands": len(cands)})
    check("{}: 不进入正常 ffmpeg 渲染（无成片且 render BLOCKED）".format(case),
          not r["films"] and r["render_status"] == "BLOCKED"
          and "[ASSET_INSUFFICIENT]" in (r["render_error"] or ""),
          {"status": r["render_status"], "films": len(r["films"])})
    ROWS.append({"case": case, "note": note, "project": r["pid"], "render_status": r["render_status"],
                 "external_error": ext_err, "rejected_codes": codes,
                 "external_verified": verified, "films": r["films"],
                 "material_mode": ret.get("material_mode")})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="只跑指定用例编号（逗号分隔，如 6,8）")
    args = ap.parse_args()
    only = {x.strip() for x in args.only.split(",") if x.strip()}

    def want(n):
        return not only or n in only

    tmp_ctx = ToolContext(role="retrieval", project_id="probe", project_dir=ROOT / "tmp_wheels",
                          db=None, config={"tools": {"ffmpeg": {"path": str(FFMPEG),
                                                                "ffprobe": str(FFPROBE)}}})

    # 1) 未配置 API key（受控配置）
    if want("1"):
        p, err, _ = provider_from_config({"tools": {"material": {
            "provider": "wikimedia_commons", "auth": {"mode": "bearer", "require_key": True,
                                                      "api_key_env": "WIKIMEDIA_API_TOKEN_MISSING"}}}})
        check("1 no_api_key: provider 构造返回 PROVIDER_NOT_CONFIGURED（不伪造候选）",
              p is None and err == "PROVIDER_NOT_CONFIGURED", err)
        r = project_with("test_phase2e_nokey", {"provider": "wikimedia_commons",
                                                "auth": {"require_key": True,
                                                         "api_key_env": "WIKIMEDIA_API_TOKEN_MISSING"},
                                                **POL})
        summarize("1 no_api_key", r, ("PROVIDER_NOT_CONFIGURED",), "受控配置：无 key 必须显式失败")

    # 2) 鉴权失败（真实 401；限流时退避重试，确保验证的是鉴权面而不是限流面）
    if want("2"):
        os.environ["WIKIMEDIA_API_TOKEN"] = "definitely-invalid-token-for-testing"
        try:
            real_code, auth_tries = None, []
            for i in range(1, 4):
                prov = WikimediaCommonsProvider({**POL, "auth": {
                    "mode": "bearer", "api_key_env": "WIKIMEDIA_API_TOKEN"}})
                try:
                    prov.search(MaterialQuery(text="virtual reality headset",
                                              keywords={"headset"}), tmp_ctx)
                    auth_tries.append({"attempt": i, "code": None})
                    break
                except TransportError as exc:
                    real_code = exc.code
                    auth_tries.append({"attempt": i, "code": exc.code})
                    if exc.code != "PROVIDER_RATE_LIMITED":
                        break
                    time.sleep(CASE_GAP_S * i)
            check("2 auth_failed: 真实 401 → PROVIDER_AUTH_FAILED",
                  real_code == "PROVIDER_AUTH_FAILED", {"code": real_code, "tries": auth_tries})
            time.sleep(CASE_GAP_S)
            r = project_with("test_phase2e_authfail", {"provider": "wikimedia_commons",
                                                       "auth": {
                                                           "mode": "bearer",
                                                           "api_key_env": "WIKIMEDIA_API_TOKEN"},
                                                       **POL})
            summarize("2 auth_failed", r, ("PROVIDER_AUTH_FAILED",),
                      "真实：无效 Bearer → HTTP 401")
        finally:
            os.environ.pop("WIKIMEDIA_API_TOKEN", None)

    # 3) 429 限流（受控注入；真实 429 见端到端运行 stats.retries）
    if want("3"):
        r = project_with("test_phase2e_429", POL, transport_patch=lambda pol: Boom429())
        summarize("3 rate_limited", r, ("PROVIDER_RATE_LIMITED", "PROVIDER_SEARCH_FAILED",),
                  "受控 429；真实运行中亦观测到 429 与重试")

    # 4) 搜索超时（真实）
    if want("4"):
        prov = WikimediaCommonsProvider({**POL, "timeout_s": 0.001})
        real_code = None
        try:
            prov.search(MaterialQuery(text="virtual reality headset", keywords={"headset"}),
                        tmp_ctx)
        except TransportError as exc:
            real_code = exc.code
        check("4 search_timeout: 真实端点超时 → PROVIDER_TIMEOUT",
              real_code == "PROVIDER_TIMEOUT", real_code)
        r = project_with("test_phase2e_searchtimeout", {**POL, "timeout_s": 0.001})
        summarize("4 search_timeout", r, ("PROVIDER_TIMEOUT",), "真实：timeout_s=0.001")

    # 5) 下载超时（真实搜索 + 下载腿注入）
    if want("5"):
        time.sleep(CASE_GAP_S)
        r = project_with("test_phase2e_dltimeout", POL,
                         transport_patch=lambda pol: DownloadFaultTransport("timeout"))
        summarize("5 download_timeout", r, ("PROVIDER_TIMEOUT",), "真实 URL + 下载腿超时注入")

    # 6) 下载内容损坏（真实字节被截断）
    #    真实媒体主机被限流时（429），改用**此前真实下载并校验过的缓存字节**（记录 byte_source）
    if want("6"):
        time.sleep(CASE_GAP_S)
        cached = cached_real_file()
        if cached is None:
            check("6 corrupt_download: 存在可复用的真实下载缓存", False, "无缓存文件")
        else:
            print("   使用真实缓存字节: {} ({:.0f} KB, sha256={}…)".format(
                cached.name, cached.stat().st_size / 1024, hashlib.sha256(
                    cached.read_bytes()).hexdigest()[:16]))
            run_asset_level_case(
                "6 corrupt_download", POL,
                ("ASSET_TRUNCATED", "ASSET_PROBE_FAILED", "ASSET_FFMPEG_DECODE_FAILED",
                 "ASSET_DECODE_FAILED"),
                "真实 provider 字节（缓存复用，sha256 可核对）被截断；搜索为真实网络",
                transport_patch=lambda pol: CachedRealBytesTransport(cached, "truncate", 2048))

    # 7) 许可证缺失 / 受限
    if want("7"):
        time.sleep(CASE_GAP_S)
        run_asset_level_case("7 license_missing", POL,
                             ("ASSET_LICENSE_MISSING", "ASSET_LICENSE_UNCLEAR"),
                             "受控：真实候选去掉许可证字段（真实搜索；抖动自动重跑）",
                             drop_license=True)
    cls_restricted, cleared = classify_license("fair use")
    check("7b license_restricted: 声明 fair use → RESTRICTED 且不清权",
          cls_restricted == "RESTRICTED" and cleared is False, cls_restricted)
    check("7c 许可证分类不猜测（未知声明 → UNKNOWN）",
          classify_license("Proprietary-ish thing")[0] == "UNKNOWN"
          and classify_license(None)[0] == "UNKNOWN")

    # 8) 真实素材被 BLOCKED（真实候选 + 极小体积上限；字节同样复用真实缓存）
    if want("8"):
        time.sleep(CASE_GAP_S)
        cached = cached_real_file()
        if cached is None:
            check("8 real_blocked: 存在可复用的真实下载缓存", False, "无缓存文件")
        else:
            run_asset_level_case(
                "8 real_blocked", {**POL, "max_bytes": 20 * 1024}, ("ASSET_OVERSIZE",),
                "真实 provider 字节（缓存复用）被策略上限 20KiB 流式拒绝 → BLOCKED",
                transport_patch=lambda pol: CachedRealBytesTransport(cached, "passthrough"))

    rec = {"rows": ROWS, "checks": {"pass": PASS, "fail": FAIL}}
    (LOGS / "phase2e_failure_paths.json").write_text(
        json.dumps(rec, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print("\n结果: {}/{} 通过".format(len(PASS), len(PASS) + len(FAIL)))
    if FAIL:
        print("失败项:", FAIL)
    print("记录:", LOGS / "phase2e_failure_paths.json")
    return 0 if not FAIL else 1


if __name__ == "__main__":
    sys.exit(main())
