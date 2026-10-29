# G10 生产前最终审计 Checklist（接线后）

- 日期: 2026-09-10 · 性质: 只读审计 + 静态核对 + 全量回归（无正式 Run、无 Retrieval/CV2、零冻结件修改）
- 审计脚本: `output/audit_20260910_ds1/g10_preflight_audit.py`（40 项静态断言，含 AST 级旁路检测）

## Checklist 逐项结果（7 大项 / 33 子项全 PASS）

**1. 链路无旁路 — 5/5 PASS**
- 1a Candidate 对象仅在 candidate_gate_stage 构造（AST 函数域断言，G10 过滤在其中）✅
- 1b run() 链含 g10 加载与双点传递（候选级 + prerender）✅
- 1c render plan 仅由 policy 决策构建 ✅
- 1d 执行器仅消费 render_plan（不接触 retrieval/CV2 数据）✅
- 1e prerender 失败即 STOP ✅

**2. R1–R8 优先级与 fail-closed — 8/8 PASS（真实资产探针）**
- R1 自指外来 REJECT ✅ · R2 缺信号/低置信/非法域全 REVIEW ✅ · R4 泛化 LOW（先于 R8，META 拍拼词图仍 LOW）✅ · R5 primary PASS ✅ · R6 近域 REVIEW/签核 PASS ✅ · R7 异域 REJECT ✅ · R8 无期望 ✅ · R4→R8 次序证明 ✅

**3. 信号与锚定 — 4/4 PASS**
- 438/438 parsed ✅ · 本体/ECT/信号 SHA256 与磁盘一致 ✅ · 信号存于 run04 命名空间（非 audit 直读）✅ · 模型=deepseek-flash（pro 禁用）✅

**4. 签核/排除/覆盖 — 7/7 PASS**
- 签核 5 拍 ✅ · S19-B02 排除 ✅ · 签核记录含 authorized_by/at/ref ✅ · S20-B03 覆盖→generic_stock_concept ✅ · shadow 中 S20-B03=FALLBACK(HN) ✅ · S19-B02 未升级 ✅ · 5 签核拍全 CORRESPONDING ✅

**5. CORRESPONDING/BORROW 边界 — 4/4 PASS**
- 全部 CORRESPONDING 展示 g10=PASS/NO_EXPECTATION ✅ · HN/FALLBACK 全角标 ✅ · BORROW 豁免域门（角标=诚实标识）✅ · 已知错配家族素材零上屏（签核后仍隔离）✅

**6. 无污染/绕过/冻结修改 — 7/7 PASS**
- 历史脚本 mtime 未变 ✅ · Run01–04 母片哈希不变 ✅ · AST 级无 os.environ/os.getenv ✅ · CLI 仅 --exec-id ✅ · 授权双钥互锁（flag+签核）✅ · 冻结 14/14 ✅ · g10 拒绝全量入审计日志 ✅

**7. 验收口径语义 — 5/5 PASS**
- manifest 下限=60（**次数口径**）✅ · QA 输出为 0–101 整数计数 ✅ · run() 比较 `count >= 60`（无百分比换算）✅ · shadow 实际判定 60≥60 PASS 且**判定结果已持久化** ✅ · 报告表述 60/101=59.4%（非"≥60%"）✅

## 审计中发现并已修复（1 项）

| 发现 | 修复 |
|---|---|
| 7d：G10 验收判定 `g10_acceptance_ok` 在 **PASS 路径未持久化**回 qa_summary.json（FAIL 路径有）| run() 中 PASS 路径补 `_write`（qa_summary.json + qa/latest.json 双写），重跑 shadow 后 `g10_acceptance_ok: True` 已持久化，40/40 复核通过 |

（另：静态审计脚本自身两处启发式误报——Candidate 行号窗口过窄、"environment" 子串误匹配——已改为 AST 函数域/属性级检测；非生产问题。）

## 回归与完整性

编排器 **17/17** · R1–R8 **8/8** · 模块单测 **12/12** · 冻结 **14/14** · 母片 Run01 `ff119fcd` / Run02 `ad52a0c0` / Run03 `871489f9` / Run04 生产 `074985a5` 全部不变

## 结论

```
PRE-PRODUCTION FINAL AUDIT = PASS（33/33 子项，1 项持久化缺口已当场修复并复验）
shadow 口径 = 域一致 CORRESPONDING 60/101（≥60 次数口径）· 错配上屏 0 · HN/空位全角标
等待指令 = "启动正式 Run"（生产执行器/授权/签核记录均已就绪，不自行启动）
STOP
```
