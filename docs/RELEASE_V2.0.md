# V2.0 Release 记录

- **版本号**：V2.0.0（封版）
- **验收日期**：2026-08-15
- **验收方式**：真实 SAO 项目全管线运行（p_fcaceb2de684）+ V2_SPEC 7 条标准逐项验收 + 全量回归
- **状态**：V2 正式验收通过，封版；不再修改 V2 核心架构与已验收模块

## 验收结果（7/7 PASS）

| # | 标准 | 结果 |
|---|---|---|
| 1 | 25 Agent 注册 + V1 回归通过 | PASS |
| 2 | 绝对化表述自动 CRITICAL + claims_map 一致 | PASS |
| 3 | fact_check 离线可运行、证据输出 | PASS |
| 4 | 冲突 → CONFLICT + 人工审核 | PASS |
| 5 | 人工审核落 decisions+changelog、可打回 script 复检 | PASS |
| 6 | 用户可见输出零 [CLAIM:xxx] 标记 | PASS |
| 7 | claim→evidence→source→status 全链可追溯 | PASS |

## 全量测试结果（验收日）

| 测试 | 结果 | 说明 |
|---|---|---|
| smoke_mock.py | 12/12 | V1 核心闭环回归 |
| pipeline_mock.py | 12/12 | V1 全管线回归（已适配 26 任务） |
| schema_v2_test.py | 10/10 | 数据层 + 追溯链 |
| agents_v2_test.py | 27/27 | claim/evidence/conflict 三 Agent |
| factcheck_v2_test.py | 23/23 | 逐 Claim 核查 + Skeptic + SearchProvider |
| strip_v2_test.py | 14/14 | 标记剥离全链路 |
| hitl_v2_test.py | 19/19 | Claim 级人工审核闭环 + 生产闸门 |

## 真实验收项目数据

- 项目 `p_fcaceb2de684`：26/26 任务 SUCCEEDED；80 条 Claim 全部人工处置；
  9 条 Claim 带证据链路；58 条 changelog 全部 human_confirmed；62 条 decisions；成片 11.51MB
- 三路径闭环演示项目 `p_ce26dbdd63bd`：revise / reject / approve 实测（reject 重建 script+提取链）

## V2.0 已知限制（记录，不在本版修复）

1. claim_extractor 规则引擎会把含描述性"可能"的句子归为 PREDICTION（如"随时可能被砸"）
   ——分类噪声；安全失败模式（PREDICTION+CRITICAL 组合必进人工），未造成错误放行
2. 在线 SearchProvider 仅有接口与测试桩（fake_search）；真实搜索服务接入后需按各家
   API 响应格式实现 extract_evidence
3. Skeptic 的 time / causality / headline_gap 三维度主要依赖 LLM 攻击维度（按用户
   第四阶段决定，未加确定性规则，避免误报）
4. conflict_detector "可靠性差≥2"仅为潜在冲突触发条件，不等同事实矛盾（原则已入代码注释）
5. REJECTED 后的重做链仅自动重建 script + claim_extract；后续核查任务需人工/管线再触发

## 版本控制说明

项目目录未初始化 Git（验收日检查确认）。按用户指示不引入版本控制体系，
版本状态以本文档 + STATUS.md + CHANGELOG.md 记录为准。
