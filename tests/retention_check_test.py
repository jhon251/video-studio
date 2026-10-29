# -*- coding: utf-8 -*-
"""Phase 9 测试：留存评分器（机械层逐维度 / 结构码 / 黑名单变体 / 确定性 / P9-1 错误码 / LLM 层纪律）。

覆盖授权书 §3：
 · 机械层逐维度（Phase 8 两版稿件作夹具）
 · `V3_METADATA_ABSENT` 路径（结构码**不计 FAIL**）
 · 黑名单变体（开场寒暄 + CTA 裸话术）
 · 确定性（同一输入两次运行机械层逐字节一致；CLI `--no-timestamp --json` 逐字节一致）
 · P9-1 错误码场景（content 空 + reasoning_tokens>0 ⇒ LLM_REASONING_BUDGET_EXHAUSTED + usage）
 · LLM 层纪律（无 client ⇒ PARTIAL 且无分数；缓存命中一致；非法输出 ⇒ PARTIAL；有分无证据 ⇒ 拒绝）

运行: python tests/retention_check_test.py
"""
from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core import retention as RT                                      # noqa: E402
from video_studio.core.visual_requirement import canonical                         # noqa: E402
from video_studio.llm.router import DeepSeekClient, LLMError                       # noqa: E402
from video_studio.ops import retention as OPS                                      # noqa: E402

PASS, FAIL = [], []


def check(name, ok, detail=None):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name,
                             "" if ok else json.dumps(detail, ensure_ascii=False,
                                                      default=str)[:240]))
    return bool(ok)


LOGS = ROOT / "docs" / "regression_2x" / "logs"
V2 = json.loads((LOGS / "phase8_ab_v2.json").read_text(encoding="utf-8"))["script"]
V3 = json.loads((LOGS / "phase8_ab_v3.json").read_text(encoding="utf-8"))["script"]
PROD = json.loads((ROOT / "projects" / "p_96efdc03e1aa" / "artifacts" /
                   "a_49b58fb3dc01.json").read_text(encoding="utf-8"))

R_V2 = RT.analyze(V2, source={"path": "phase8_ab_v2.json"})
R_V3 = RT.analyze(V3, source={"path": "phase8_ab_v3.json"})
R_PROD = RT.analyze(PROD, source={"path": "a_49b58fb3dc01.json"})

# ---------------- 1. 机械层：逐维度（Phase 8 两版稿件夹具） ----------------
check("1 机械层 schema/校验：三份稿件均通过 validate",
      all(RT.validate(r) == [] for r in (R_V2, R_V3, R_PROD)))
check("1b v3 稿件：0 FAIL；emotion 由元数据直接判定 PASS；CTA 因 at_segment 越界报结构违规码"
      "（P10-1 钉死 0-based 后的**预期行为变更**，见 PHASE10_REPORT）",
      R_V3["status_counts"]["FAIL"] == 0 and R_V3["status_counts"]["NOT_ASSESSABLE"] == 0
      and R_V3["dimensions"]["emotion_beats"]["status"] == "PASS"
      and R_V3["dimensions"]["cta"]["status"] == "WARN"
      and "CTA_AT_SEGMENT_OUT_OF_RANGE" in R_V3["dimensions"]["cta"]["codes"],
      {d: v["status"] for d, v in R_V3["dimensions"].items()})
check("1c v3 稿件：CTA 计数 ≤2 且无裸话术（阈值镜像 v3 §2.3）",
      R_V3["dimensions"]["cta"]["measured"]["count"] <= 2
      and R_V3["dimensions"]["cta"]["measured"]["bare_count"] == 0,
      R_V3["dimensions"]["cta"]["measured"]["count"])
check("1d v2 稿件：hook 窗口超限 ⇒ WARN + 证据（段落下标 + 原文引用）",
      R_V2["dimensions"]["hook_structure"]["status"] == "WARN"
      and "HOOK_WINDOW_EXCEEDED" in R_V2["dimensions"]["hook_structure"]["codes"]
      and R_V2["dimensions"]["hook_structure"]["evidence"][0]["segment_index"] == 0
      and bool(R_V2["dimensions"]["hook_structure"]["evidence"][0]["quote"]))
check("1e 生产正片稿（21 段/1530 s）基线：机械层得分 85.7、hook 间隔 WARN（真实基线锚点）",
      R_PROD["mechanical_score"] == 85.7 and R_PROD["segment_count"] == 21
      and R_PROD["dimensions"]["hook_interval"]["status"] == "WARN",
      {"score": R_PROD["mechanical_score"], "segs": R_PROD["segment_count"]})
check("1f 判据①：逐维度 v3 ≥ v2（v2 缺元数据以结构码呈现、不计 FAIL；用 STATUS_RANK 比较）",
      all(RT.STATUS_RANK[R_V3["dimensions"][d]["status"]] >=
          RT.STATUS_RANK[R_V2["dimensions"][d]["status"]]
          for d in RT.DIMENSIONS),
      {d: (R_V2["dimensions"][d]["status"], R_V3["dimensions"][d]["status"])
       for d in RT.DIMENSIONS})

# ---------------- 2. V3_METADATA_ABSENT 路径 ----------------
check("2 v2 稿件（无 v3 元数据）⇒ 结构码 V3_METADATA_ABSENT 单独计数，且 0 FAIL",
      R_V2["structural_codes"].get("V3_METADATA_ABSENT", 0) >= 2
      and R_V2["status_counts"]["FAIL"] == 0
      and "不计 FAIL" in R_V2["structural_code_note"], R_V2["structural_codes"])
check("2b 元数据缺失的维度标 NOT_ASSESSABLE，并**不计入评分分母**",
      R_V2["dimensions"]["emotion_beats"]["status"] == "NOT_ASSESSABLE"
      and "NOT_ASSESSABLE 不计入分母" in R_V2["mechanical_score_basis"])
check("2c 元数据在位时同一维度可评估（v3 覆盖 1.0、无非法枚举）",
      R_V3["dimensions"]["emotion_beats"]["measured"]["coverage"] == 1.0
      and R_V3["dimensions"]["emotion_beats"]["measured"]["illegal"] == [])
check("2d 机械层**不评事实**（out_of_scope 明示，报告自称 not_a_fact_check）",
      any("事实" in s for s in RT.OUT_OF_SCOPE) and R_V3["not_a_fact_check"]
      and R_V3["applied"] is False and R_V3["executed"] is False)

# ---------------- 3. 黑名单变体 ----------------
def mk(segs, **top):
    s = {"segments": segs, "summary": "t"}
    s.update(top)
    return s


def seg(text, dur=30.0, **kw):
    d = {"narration": text, "duration_s": dur}
    d.update(kw)
    return d


greet_cases = ["大家好，今天我们聊一个话题。", "哈喽各位，欢迎来到本频道。",
               "咱们聊聊这件事吧。", "话不多说，直接开始。", "今天我们来聊聊数学。"]
greet_hits = [RT.dim_hook_structure(mk([seg(t)])) for t in greet_cases]
check("3 开场寒暄黑名单：5 个变体全部命中 GREETING_BLACKLIST_HIT（WARN，不判 FAIL）",
      all("GREETING_BLACKLIST_HIT" in r["codes"] and r["status"] == "WARN" for r in greet_hits),
      [r["codes"] for r in greet_hits])
bare_cases = ["感谢观看，我们下期再见。", "记得点赞关注，一键三连！", "点赞订阅走一波，评论区告诉我。",
              "求个三连，关注一下。", "别忘了三连。"]
for i, t in enumerate(bare_cases):
    r = RT.dim_cta(mk([seg(t)], cta_plan=[{"at_segment": 1, "type": "outro", "line": t}]))
    check("3b 裸话术变体 #{} ⇒ FAIL（CTA_BARE_CLICHE）".format(i + 1),
          r["status"] == "FAIL" and "CTA_BARE_CLICHE" in r["codes"], r["codes"])
ok_cta = RT.dim_cta(mk([seg("正文")], cta_plan=[
    {"at_segment": 0, "type": "content_hook", "line": "这个数字后来被推翻了——想知道的看完。"}]))
check("3c 内容型 CTA（at_segment=0，0-based 合法）⇒ PASS（无裸话术、≤2 处）",
      ok_cta["status"] == "PASS" and ok_cta["measured"]["bare_count"] == 0)
check("3d CTA 超 2 处 ⇒ WARN（CTA_TOO_MANY）",
      "CTA_TOO_MANY" in RT.dim_cta(mk([seg("a"), seg("b"), seg("c")], cta_plan=[
          {"at_segment": i, "type": "t", "line": "这个反例值得看到最后，想知道的看完。"}
          for i in (0, 1, 2)]))["codes"])
# P10-1：at_segment 语义钉死为 0-based（越界/非整数 ⇒ 结构违规码，不计 FAIL）
oob = RT.dim_cta(mk([seg("a"), seg("b")], cta_plan=[
    {"at_segment": 2, "type": "t", "line": "内容型互动句，想知道的看完。"}]))
neg = RT.dim_cta(mk([seg("a"), seg("b")], cta_plan=[
    {"at_segment": -1, "type": "t", "line": "内容型互动句，想知道的看完。"}]))
bad_type = RT.dim_cta(mk([seg("a")], cta_plan=[
    {"at_segment": "1", "type": "t", "line": "内容型互动句，想知道的看完。"}]))
check("3e at_segment 越界（2 段用下标 2）⇒ CTA_AT_SEGMENT_OUT_OF_RANGE + WARN（不计 FAIL）",
      oob["status"] == "WARN" and "CTA_AT_SEGMENT_OUT_OF_RANGE" in oob["codes"]
      and "CTA_AT_SEGMENT_OUT_OF_RANGE" in neg["codes"],
      {"oob": oob["codes"], "neg": neg["codes"]})
check("3f at_segment 非整数 ⇒ CTA_AT_SEGMENT_INVALID",
      "CTA_AT_SEGMENT_INVALID" in bad_type["codes"]
      and bad_type["measured"]["at_segment_semantics"].startswith("0-based"))

# ---------------- 4. 确定性 ----------------
a = RT.analyze(copy.deepcopy(V3), source={"path": "x"})
b = RT.analyze(copy.deepcopy(V3), source={"path": "x"})
check("4 机械层确定性：同一输入两次 ⇒ 输出逐字节一致（canonical 相等 + 同 hash）",
      canonical(a) == canonical(b) and a["artifact_hash"] == b["artifact_hash"])
c = RT.analyze(copy.deepcopy(V3), source={"path": "OTHER-LABEL"})
check("4b 哈希绑定脚本内容（script_sha256），来源标签不参与 ⇒ 不同标签同 hash",
      c["artifact_hash"] == a["artifact_hash"]
      and a["script_sha256"] == hashlib.sha256(canonical(V3).encode("utf-8")).hexdigest())
env = {"PYTHONPATH": str(ROOT / "src"), **{k: v for k, v in __import__("os").environ.items()}}
out1 = subprocess.run([sys.executable, "run.py", "retention-check", "--script",
                       "docs/regression_2x/logs/phase8_ab_v2.json", "--no-llm", "--json",
                       "--no-timestamp"], cwd=str(ROOT), capture_output=True, env=env).stdout
out2 = subprocess.run([sys.executable, "run.py", "retention-check", "--script",
                       "docs/regression_2x/logs/phase8_ab_v2.json", "--no-llm", "--json",
                       "--no-timestamp"], cwd=str(ROOT), capture_output=True, env=env).stdout
check("4c CLI `--json --no-timestamp` 两次运行逐字节一致（只读、键排序）",
      bool(out1) and out1 == out2)

# ---------------- 5. P9-1 错误码 ----------------
class _Resp:
    def __init__(self, content, reasoning):
        self.status_code = 200
        self.text = ""
        self._c, self._r = content, reasoning

    def json(self):
        return {"choices": [{"message": {"content": self._c}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 64,
                          "completion_tokens_details": {"reasoning_tokens": self._r},
                          "prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 12}}


def _patch_requests(resp):
    class _R:
        @staticmethod
        def post(*a, **k):
            return resp

        class exceptions:                                                  # noqa: N801
            class Timeout(Exception):
                pass

            class RequestException(Exception):
                pass
    sys.modules["requests"] = _R


_patch_requests(_Resp("", 64))
cl = DeepSeekClient({"api_key_env": "P9_NO_SUCH_KEY"})
cl.api_key = "k"
try:
    cl.complete("deepseek-flash", "s", "u", 64)
    code9, usage9 = None, None
except LLMError as exc:
    code9, usage9 = exc.code, getattr(exc, "usage", None)
check("5 P9-1：content 空 + reasoning_tokens>0 ⇒ LLM_REASONING_BUDGET_EXHAUSTED（附 usage 明细）",
      code9 == "LLM_REASONING_BUDGET_EXHAUSTED" and usage9
      and usage9.get("reasoning_tokens") == 64 and usage9.get("max_tokens_requested") == 64,
      {"code": code9, "usage": usage9})
_patch_requests(_Resp("正常内容", 64))
cl2 = DeepSeekClient({"api_key_env": "P9_NO_SUCH_KEY"})
cl2.api_key = "k"
res = cl2.complete("deepseek-flash", "s", "u", 64)
check("5b content 非空 ⇒ 行为不变（不误报错误码）", res["text"] == "正常内容")
_patch_requests(_Resp("", 0))
cl3 = DeepSeekClient({"api_key_env": "P9_NO_SUCH_KEY"})
cl3.api_key = "k"
try:
    r3 = cl3.complete("deepseek-flash", "s", "u", 64)
    empty_ok = r3["text"] == ""
except LLMError:
    empty_ok = False
check("5c content 空但 reasoning_tokens=0 ⇒ 沿用原语义（不新增错误码）", empty_ok)

# ---------------- 6. LLM 层纪律 ----------------
rep_partial = OPS.evaluate(V3, source={"path": "v3"}, llm=True)
check("6 无 client ⇒ llm.status=PARTIAL 且**无任何分数**（禁止编造）",
      rep_partial["llm"]["status"] == "PARTIAL" and not rep_partial["llm"].get("rubric")
      and rep_partial["llm"]["reason_code"] == "LLM_CLIENT_UNAVAILABLE"
      and OPS.validate_report(rep_partial) == [])
key = OPS.cache_key(rep_partial["script_sha256"], "deepseek-v4-pro")
rubric = {"hook_strength": {"score": 4, "evidence": ["引用A"], "rationale": "r"},
          "cta_naturalness": {"score": 3.5, "evidence": ["引用B"], "rationale": "r"},
          "tension_curve": {"score": 4, "per_segment": [3, 4, 4, 3, 5, 4, 3, 4],
                            "low_points": [0, 3, 6], "evidence": ["引用C"], "rationale": "r"}}
cache = {key: {"rubric": rubric, "suggestions": [
    {"target": "opening", "action": "把首段 40 s 内的认知冲突前置", "why": "w"}]}}
r_c1 = OPS.evaluate(V3, source={"path": "v3"}, cache=cache, llm=True)
r_c2 = OPS.evaluate(V3, source={"path": "v3"}, cache=cache, llm=True)
check("6b 缓存命中 ⇒ status=OK、cache_hit=true、两次输出逐字节一致（键=prompt_version+model+sha）",
      r_c1["llm"]["status"] == "OK" and r_c1["llm"]["cache_hit"] is True
      and canonical(r_c1) == canonical(r_c2)
      and r_c1["llm"]["prompt_version"] == OPS.PROMPT_VERSION
      and key == OPS.cache_key(rep_partial["script_sha256"], "deepseek-v4-pro"),
      r_c1["llm"]["prompt_version"])
check("6c 缓存命中时 rubric 与建议齐备且带原文引用证据（top-3 上限）",
      r_c1["llm"]["rubric"]["hook_strength"]["evidence"]
      and len(r_c1["top_suggestions"]) <= 3 and r_c1["llm"]["temperature"] == 0.0)
check("6d 校验器拒绝『PARTIAL 却带分数』（防编造）",
      bool(OPS.validate_report({**r_c1, "llm": {**r_c1["llm"], "status": "PARTIAL"}})))
check("6e 有分无证据 ⇒ rubric 校验拒绝",
      bool(OPS._validate_rubric({"rubric": {**rubric, "hook_strength": {"score": 5}},
                                 "suggestions": []})))
fake_invalid = type("C", (), {"complete": staticmethod(
    lambda *a, **k: {"text": "not json", "prompt_tokens": 1, "completion_tokens": 1,
                     "model": "deepseek-v4-pro", "latency_ms": 1})})()
rep_inv = OPS.judge_script(V3, mechanical=R_V3, client=fake_invalid)
check("6f LLM 输出非法 ⇒ PARTIAL / LLM_OUTPUT_INVALID（不编造分数）",
      rep_inv["status"] == "PARTIAL" and rep_inv["reason_code"] == "LLM_OUTPUT_INVALID"
      and not rep_inv.get("rubric"), rep_inv.get("reason_code"))
rep_err = OPS.judge_script(V3, mechanical=R_V3, client=type("E", (), {"complete": staticmethod(
    lambda *a, **k: (_ for _ in ()).throw(LLMError("LLM_REASONING_BUDGET_EXHAUSTED", "x", None)))})())
check("6g LLM 抛 P9-1 错误码 ⇒ PARTIAL 且 reason_code 如实透传（失败不静默）",
      rep_err["status"] == "PARTIAL" and rep_err["reason_code"] == "LLM_REASONING_BUDGET_EXHAUSTED")
check("6h 职责边界与 out_of_scope 写入报告；只读三标记齐备",
      "critic" in json.dumps(rep_partial["responsibility_boundary"], ensure_ascii=False)
      and rep_partial["read_only"] is True and rep_partial["zero_write"] is True
      and rep_partial["dispatches_tasks"] is False
      and rep_partial["applied"] is False and rep_partial["executed"] is False)

# ---------------- 7. 只读静态证据（ops/CLI 不写） ----------------
ops_src = (ROOT / "src" / "video_studio" / "ops" / "retention.py").read_text(encoding="utf-8")
check("7 ops/retention.py 只读：mode=ro + query_only，且无写文件/写库调用",
      "mode=ro" in ops_src and "query_only=ON" in ops_src
      and not any(t in ops_src for t in ("write_text(", "write_artifact", "INSERT ", "UPDATE ",
                                         "DELETE ", "create_task", "run_cycle")))
check("7b 机械层为纯函数模块（无 I/O、无 LLM、无网络）",
      not any(t in (ROOT / "src" / "video_studio" / "core" / "retention.py").read_text(
          encoding="utf-8") for t in ("open(", "requests", "sqlite3", "subprocess")))

# ---------------- 8. P11-1：无 CTA 稿件的 CTA 维度统一 NOT_ASSESSABLE ----------------
_CACHE_PATH = LOGS / "phase10_retention_cache.json"
_p11_cache = json.loads(_CACHE_PATH.read_text(encoding="utf-8")) if _CACHE_PATH.is_file() else {}
_na_v2 = OPS.judge_script(V2, mechanical=R_V2, cache=_p11_cache, samples=3)
_na_v3 = OPS.judge_script(V3, mechanical=R_V3, cache=_p11_cache, samples=3)
check("8 P11-1：无 CTA 稿件（机械层 CTA_ABSENT）⇒ 全部采样一致 NOT_ASSESSABLE（null，不折算 0）",
      _na_v2["status"] == "OK"
      and ((_na_v2.get("rubric") or {}).get("cta_naturalness") or {}).get("score") is None
      and (_na_v2.get("aggregation") or {}).get("cta_naturalness", {}).get("agreement")
      == "NOT_ASSESSABLE"
      and (_na_v2.get("aggregation") or {}).get("cta_naturalness", {}).get("scored_samples") == 0
      and "cta_absent_semantics" in _na_v2,
      json.dumps(_na_v2.get("aggregation", {}).get("cta_naturalness"), ensure_ascii=False)[:200])
check("8b P11-1：修复 Phase 10 的『仅 1/3 采样给分』不一致（原 median=1.0 现为 null）",
      (_na_v2.get("aggregation") or {}).get("cta_naturalness", {}).get("median") is None
      and (_na_v2.get("aggregation") or {}).get("cta_naturalness", {}).get("samples")
      is not None)      # 原始采样值仍留档（可审计）
check("8c P11-1：有 CTA 的稿件**不**受该规则影响（CTA 维度照常评分）",
      (_na_v3.get("rubric") or {}).get("cta_naturalness", {}).get("score") is not None
      and (_na_v3.get("aggregation") or {}).get("cta_naturalness", {}).get("agreement")
      in ("STABLE", "UNSTABLE"),
      json.dumps(_na_v3.get("aggregation", {}).get("cta_naturalness"), ensure_ascii=False)[:160])
check("8d P11-1：单采样路径同样应用（samples=1 ⇒ cta null，其余维度不受影响）",
      ((OPS.judge_script(V2, mechanical=R_V2, cache=_p11_cache, samples=1).get("rubric") or {})
       .get("cta_naturalness") or {}).get("score") is None
      and "samples" not in OPS.judge_script(V2, mechanical=R_V2, cache=_p11_cache, samples=1))

print("\n结果: {}/{} 通过".format(len(PASS), len(PASS) + len(FAIL)))
if FAIL:
    print("失败项:", FAIL)
sys.exit(1 if FAIL else 0)
