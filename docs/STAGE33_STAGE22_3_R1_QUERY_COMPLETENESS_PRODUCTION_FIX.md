# Stage 33 — STAGE 22.3: R1 Query Completeness Production Fix(执行报告)

> **授权**:Stage 22.2 评定 SAFE WITH GUARDRAIL 后,用户授权仅实施 R1。
> **修改文件**:`output/prod01/retrieval_run.py`(Run 01 检索 harness,**非冻结模块**)。
> 机器可读:`output/stage22_visual_quality/stage22_3_r1_production_fix.json`

## 1. 修改了什么(共 3 处)

| # | 行 | BEFORE | AFTER | 目的 |
|---|---|---|---|---|
| 1 | L72 | `for q in (s['t1'][:2] + s['t2'][:1]):` | `for q in (s['t1'][:2] + s['t2'][:1] + s['t3'][:1]):` | 循环执行至 t3(schema 一致;Run 01 计划 t3=0,**如实记录、未伪造**) |
| 2 | L77 | `if len([c for c in cands if c['source']=='wikimedia']) >= 4: break` | 删除(留注释) | 消除错误的 beat 级提前 break |
| 3 | L~73 | 无日志 | `qexec_log.append(query, results, new_unique)` + `query_exec_log.json` sidecar | 查询执行审计日志(0 结果 query 也记录) |

**明确未动**:Visual Intent · Query Generator 语义 · 检索排序 · Gate · V1 · CV2 · Assignment · source quota · 下载 cap(top-4/拍)· dedupe · correspondence 定义 · Honest Neutral · Stage 18–21 · Production Baseline。

## 2. 为什么安全

- 修改对象**不是冻结模块**;冻结的 Stage 12 tier 语义在 pool_precision/two_pass_material 内,未触碰;
- 修复只扩大**候选供给**(执行已计划的搜索),不新增搜索行为(非 Query Expansion)、不改任何评分;冻结 CV2 以相同方式判定更大的池。

## 3. Hash 与备份

| | 值 |
|---|---|
| harness BEFORE | `792b4e8e864db38cfda1d8a1217555186...` |
| harness AFTER | `9e91cfc7fbd06a03cf4e5acb68d54bce...` |
| 备份 | `output/stage22_visual_quality/r1_fix/backup/retrieval_run.pre_r1.py`(+before_lines.json / pre_state.json) |

## 4. 冻结边界验证(BEFORE = AFTER)

- **14/14 冻结指纹 PASS**(修订版 b38a6b11 含 subtitle_pipeline);
- Baseline `render_163` = `7e148585564716cd` 未变;`render_162` = `67627bbe6cb93326` 未变;
- 指纹文件、final_gate.json、assignment.json、cv2_results.json hash 抽查未变(本阶段无重写)。

## 5. Query Execution(BEFORE → AFTER)

| | BEFORE | AFTER |
|---|---|---|
| 计划 / 执行 / 跳过 | 301 / 156 / 145 | 301 / **301** / **0** |
| 完整性 | 51.8% | **100%** |
| 完整执行拍数 | 10/101 | **101/101** |
| 平均池 | 5.2 | 7.4(+42%) |

## 6. 回归测试(5/5 PASS)

| 测试 | 结果 |
|---|---|
| T1 正常多 query 循环(S02-B01,3 计划 3 执行,9 候选,4 下载) | ✅ |
| T2 0 结果 query 被记录(S18-B01 "EEG recording laboratory" = 0,仍执行并留痕) | ✅ |
| T3 首查 ≥4 不再截断(S27-B01 首查 6 结果,后续 2 query 仍执行) | ✅ |
| **T4 S16-B01 可进入 BrainGate 级候选(`File:BrainGate.jpg` 出现在池中)** | ✅ |
| T5 dedupe 不变(无重复 URL) | ✅ |

驱动器实际执行了 harness 自身的 `wiki_search/pexels_search/download` 代码对象(AST 抽取);**CV2 调用 0 次**(R1 不涉及)。

## 7. Cost / Latency(BEFORE → AFTER)

- 平均 query 数/拍:1.54 → 2.98;Wikimedia 请求等价:156 → 301;
- 实测单 query 延迟 1.63s(回归样本 n=12);全片预估 +~2.5 分钟(仅搜索);
- 下载:cap 不变(本阶段仅回归触发 4 次下载至测试目录);**CV2 调用 0**;未引入任何新下载/CV2 策略。

## 8. Rollback

`copy r1_fix/backup/retrieval_run.pre_r1.py -> output/prod01/retrieval_run.py`(hash 回到 792b4e8e);可删 `query_exec_log.json` sidecar。Run 01 母片/账本/baseline 从不依赖渲染后的 harness 文件,回滚零生产影响。

## 9. 硬门槛清单(全绿)

查询执行完整 ✅ · 无提前 break ✅ · 0 结果留痕 ✅ · query 顺序不变 ✅ · dedupe 不变 ✅ · 冻结 14/14 ✅ · baseline 不变 ✅ · Gate/CV2/Assignment 不变 ✅ · 回归全过 ✅ · BrainGate 可达 ✅ · 无范围蔓延 ✅

---

**核心原则达成**:R1 让系统把**已经计划好的**搜索真正执行完——没有多搜一个计划外的东西。

```
STAGE 22.3 = R1 PRODUCTION FIX VERIFIED · STOP
不进入 Stage 22.4 · 不启动 Run 02 · 不自动启用 R2/R3/Visualization/Anchor
```
