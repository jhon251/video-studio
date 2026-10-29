# Stage 19.3:Abstract Analogue Focus Canary → W07 Local Experiment 报告

> 冻结全程:Stage 12–18 生产链、Gate/V1/CV2、Stage 18 Intent Decoupling、Stage 19 A–E 指标、correspondence 记账、reuse policy、全部阈值/权重/Gold/Prompt 零改动;零新检索、零新来源、零生产代码修改。A 基线复现校验:**与 Stage 19 基线最大漂移 0.000**(逐窗精确一致)。

## 第一阶段:S03-B02 单点确认 —— PASS

使用 19.2 生成的 Real-world Analogue focus(唯一变化变量),仅已持有素材(Garner,18.1 胜出、未指派),冻结 vision_call 原样验证:

| focus 版本 | fit | label | rel |
|---|---|---|---|
| 19.1 旧抽象 intent | 0.0 | NOT_USABLE | LOW |
| 19.2 概念词 focus(禁用通道) | 0.1 | NOT_USABLE | — |
| 19.2 analogue focus(canary) | 0.78 | USABLE | — |
| **19.3 analogue focus(本阶段新鲜实测)** | **0.82** | **USABLE** | **HIGH** |

CV-2 评语:"图片为真实拍摄,准确匹配镜头焦点中会议室内人群围绕桌子查看文件并讨论的场景……群体讨论、文件审阅的核心视觉表达成立。"
- SBQ:0.45(grade 垫底)→ **0.82**;
- 伪对应检查:focus 仅含具体主语(人群/会议室/圆桌)+可观察动作(查看/讨论),零概念词;语义链仅存 provenance:**价值定义 ←(机制)人类通过协商定义价值 ←(场景)会议室讨论**;
- 4 次独立测量(19.1/19.2×2/19.3)方向一致,结论稳定。→ **进入第二阶段**。

## 第二阶段:W07 局部重测 —— 全部门槛 PASS

B = 按 19.2 Representation Decision Policy 的单点重指派(唯一变更):**S03-B02 ← Garner**(analogue focus,0.82 USABLE/HIGH)。三拍决策记录:

| Beat | 策略决策 | 动作 | 原因 |
|---|---|---|---|
| S03-B02 | REAL_WORLD_ANALOGUE | **重指派 Garner** | 机制链可审计;目标拍 CV-2 0.82 USABLE;SBQ 0.45→0.82 不降反升 |
| S03-B03 | 保留现状 | 不变 | own-pool 备选全 NU;隐喻素材未持有;当前实拍(0.4 CU)保留 |
| S04-B01 | **HONEST_NEUTRAL** | 不变 | "解释权"无诚实视觉,强行 = 伪对应;中性画面为合法结果 |

**W07 及受影响相邻窗口(W05/W06 共享 S03-B02)**(Stage 19 指标定义原样 + 19.1 预注册 displayed-real 规则):

| 窗口 | A SQS | B SQS | Δ | 组成变化 |
|---|---|---|---|---|
| **W07** | **53.7** | **85.4** | **+31.7** | RED 0.333→0.2,PROG 0.65→0.9,ALI 0.501→0.974,CONT 0.25→0.7 |
| W06 | 55.0 | 91.7 | **+36.7** | 同一重指派的正外溢 |
| W05 | 72.9 | 84.5 | **+11.6** | 同上 |

**验收核对(8 条)**:
1. W07 SQS +31.7 ≥ +10 ✅;2. correspondence 不降(类未动,56/309.26s/60.86% 不变)✅;3. 单拍质量未被牺牲(0.82 ≥ 0.45,唯一变更拍且为提升)✅;4. reuse 不恶化(multi_use 30→30,相邻重复 0,Garner 由 0 次使用转 1 次,"Formal business meeting"重复实例反而减少)✅;5. 零伪对应(focus 程序化审计通过,概念词禁入)✅;6. analogue 语义链入档(provenance manifest + verdict_store_193)✅;7. 已达标,无需 STOP;8. 依条款,**允许提出 19.4**。

## W07 局部渲染与真实观看验证

- `stage19_experiment/render_193/window1_B_analogue.mp4`(19.20s,与 A 基线等长,timeline 零改动)——冻结逐拍管线:16.2 冻结 motion 决策、composition、字幕烧录(成功)、shot 音频切片;A 对照:`render_191/window1_A_baseline.mp4`;
- 信号审计:0 黑帧;freeze 事件 2 处 = 16.2 设计内 STATIC 槽(与 A 版相同,非回归);
- 逐帧 JPG(b_f1/f4/f7.jpg)存于 render_193 供人工复核;B 版诊断角标:S03-B02"B·重指派素材"、S04-B01"中性画面"(类标记,非生产改动);
- provenance manifest:`render_193/provenance_manifest.json`(逐拍 title/origin/类/策略决策/motion/素材文件/字幕数)。

## 意义

Stage 19.1 证明"原 intent 下重指派不可行";19.2 设计了中间层;**19.3 完成闭环:同一冻结链、同一素材库,仅 focus 生成方式改变,W07 SQS +31.7、相邻窗 +36.7/+11.6,零门槛违反**。"抽象命题 → fallback"病灶首次获得一条**不新检索、不放宽质量、可审计**的修复路径。

## 产物

本报告;`stage19_3_results.json`(A/B 全量 + 门禁核对 + 策略决策);`verdict_store_193.json`(copy 协议自 verdict_store_181,新增 S03-B02×Garner 0.82 USABLE 判定 + provenance);`render_193/`(W07 B 视频 + manifest + 信号审计 + 帧)。

```
STAGE19.3 = PASS · STOP
Phase1 单点确认 0.0→0.82 USABLE/HIGH(4 次测量稳定,零伪对应) · W07 53.7→85.4(+31.7 ≥ +10) · W06/W05 +36.7/+11.6 零回退 · correspondence/reuse/SBQ 全部不恶化 · 语义链全量入档 · W07 B 版已渲染并通过信号审计 · 依条款 8 允许提出 19.4
STOP——等待下一步授权
```
