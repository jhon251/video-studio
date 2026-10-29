# Stage 33 — PRODUCTION BASELINE SWITCH(正式记录)

> **授权**:用户本轮授权;范围仅限 Baseline 状态切换及正式记录。
> **日期**:2026-09-06 · 机器可读:`output/baseline_switch/baseline_switch.json`

## 1. 切换结果

| 角色 | 路径 | SHA256[:16] | 时长 | 状态 |
|---|---|---|---|---|
| **当前 Production Baseline** | `render_163_subtitle_repair/final_long.mp4` | `7e148585564716cd` | 508.290s | **ACTIVE** |
| 历史 pre-repair Baseline | `render_162/final_long.mp4` | `67627bbe6cb93326` | 508.290s | 保留(不删/不覆盖) |

- render_163 字幕人工 QA:**APPROVED / PASS(9/9)**(`output/pre_flight_signoff/master_subtitle_timing_qa.md`);
- render_163 provenance:va 复用 + 位级一致 SRT + 修复版 burn_in(build_log 全 success;SRT 拷贝字节级一致已核);
- 冻结指纹:14/14 一致(subtitle_pipeline = `b38a6b11b1428602`,授权修订)。

## 2. 随切换继续生效的约束

- **B2 / S20–S22 = REJECTED**:缺真实视觉证据的抽象叙事段不得带入 Production Run 01(出现即 Honest Neutral 显式标注,按 B1 处置);
- **S28-B02 / Tempi = REJECTED**:真实灾难类素材禁入任何生产,不得自动寻找替代绕过风险锁;
- Production Entry / Final Quality Gate / Residual Register / analogue ledger **未改写**(CONDITIONAL GO · 60.86% · 9 条 ledger 记录均原样),两项 REJECTED 为追加签核。

## 3. 切换前一致性核验(13/13 PASS)

指纹 14/14 · 三份签核存在且结论一致 · 双母片存在且 hash 不同 · SRT 拷贝位级一致 · build_log 全 success · va 源在位 · Production Entry / Final Gate / ledger 原值核验。明细:`_preswitch_checks.json`。

## 4. 本记录不授权

Production Run 01 启动 · Residual Register / Gate 修改 · 任何视觉/素材优化 · 重开已关闭研究线。

```
PRODUCTION BASELINE SWITCH = PASS · render_163 ACTIVE · STOP
```
