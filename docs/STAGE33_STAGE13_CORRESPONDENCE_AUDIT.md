# Stage 13(1/2):素材-口播对应率现状审计

> 只做诊断与最小实现;零冻结改动、零新模型、零新素材源、零规则临时变更。
> 数据:`stage13_audit/correspondence_audit.json`(90 拍逐拍表)、`mismatch_alt_scan.json`、抽检帧 `frame_*.png`。

## 1. 口径定义(先于计算锁定,见脚本 docstring)

| 类别 | 定义 |
|---|---|
| **CORRESPONDING** | 有 banked 素材且**冻结 CV-2 判定 USABLE**(判定时真实看过下载图像,绿幕/占位图不可能 USABLE) |
| **MATERIAL_BUT_MISMATCH** | 有 banked 素材但冻结判定 **CONDITIONALLY_USABLE**("有素材但不直接对应") |
| **EMPTY** | 无 banked 素材(12.26 生产账本口径) |
| **INVALID_PLACEHOLDER** | 渲染层:EMPTY 拍当前以 `HONEST_EMPTY` 纯文字卡填充——诚实,但**不构成可看覆盖** |
| **VALID_FALLBACK** | 中性/氛围画面合法覆盖(现态为 0,是下一阶段的建设方向) |

关键发现(口径层):冻结 CV-2 schema 本身就有 `semantic_relevance`(HIGH/MEDIUM/LOW)与 `reason` 字段——"语义对应"是冻结判定**原生输出**;但历史 runner 只持久化了 fit+label,**48 个 CONDITIONAL 拍的语义相关性实测值缺失**。因此真实对应率只能界定在区间 **[6.7%, 60%]** 内,精确值需一次测量补全。

## 2. 现状基线(90 拍 / 508.16s)

| 类别 | 拍数 | 占比 | 运行时长 | 时长占比 |
|---|---|---|---|---|
| **CORRESPONDING(USABLE)** | **6** | **6.7%** | **28.5s** | **5.6%** |
| MATERIAL_BUT_MISMATCH(CONDITIONAL) | 48 | 53.3% | 267.5s | 52.6% |
| EMPTY(渲染为文字卡) | 36 | 40.0% | 212.2s | 41.8% |
| VALID_FALLBACK | 0 | 0 | 0 | 0 |

- **严格对应率:6.7%(拍)/ 5.6%(时长)——距 60% 目标差 48 拍 / 276.4s**;
- **Inclusive 率(USABLE+CONDITIONAL):60.0%(拍)/ 58.2%(时长)**——恰好在目标线上,说明 Stage 12 的"工程验收"与 Stage 13 的"语义对应"不是同一个东西;
- fit 分布双峰干净:USABLE 0.80–0.90(均值 0.86),CONDITIONAL 0.35–0.75(均值 0.588),**零重叠**;阈值敏感性:USABLE 拍全部 fit≥0.8,任何 0.5/0.6/0.7 阈值都不改变 6 拍结果。

## 3. 占位与渲染层抽检(审计机制)

- 8 个素材 clip(两类别各 4)过 ffmpeg signalstats:**0 近纯色帧、0 绿幕嫌疑**(YMIN/YMAX/SATMAX 全部正常),抽检帧已导出供人工复核;
- 36 个 EMPTY 槽确认全部为 `HONEST_EMPTY` 文字卡渲染(12.26 A/B `render_all_ok=true` 与构造一致);
- 22 段连续空拍 run(最长 4 拍)——fallback 插入可在 shot 粒度进行。

## 4. 免费杠杆排查(零调用,纯存量扫描)

48 个 MISMATCH 拍的 VerdictCache 中是否存在**另一个已判 USABLE 的候选**(两遍制在 V1 序首个合格处 break,后续候选可能未看)?扫描结果:**0/48**。无免费重选空间——对应率提升不存在"纯登记层"捷径,此路如实关闭。

## 5. 主要瓶颈(排序)

1. **48 个 CONDITIONAL 素材(52.6% 运行时长)的语义相关性未测量**——冻结 schema 本可输出,历史未存;这是"从 6.7% 走向 60%"必须先回答的问题;
2. **36 个 EMPTY 拍以文字卡填充(41.8% 时长)**——按新标准属无效覆盖,需转 VALID_FALLBACK 才可正常观看;
3. 素材池内无 USABLE 备选(0/48)——不新增判定就无法就地改善。

## 6. 下一步最小改动方案(待授权,本轮未执行)

1. **测量补全(最小,≈48 次冻结 CV-2 调用)**:对 48 个 MISMATCH 素材以**同 prompt/同 key/同图**补采 `semantic_relevance` + `reason`(纯测量,不改任何组件,不触碰验收逻辑);产出对应度谱系表;
2. **口径裁决(用户决策)**:基于谱系数据决定 60% 的"明确语义对应"如何计——(a) 仅 USABLE;(b) USABLE + relevance=HIGH 的 CONDITIONAL;(c) 维持 inclusive。本轮**不预设**结论;
3. **VALID_FALLBACK 模块(最小新模块)**:为 36 个空拍从中性氛围画面提供可看覆盖(明确标注 fallback,不计入对应率),消除文字卡;
4. 视谱系结果决定是否需要对低对应拍做素材内替换(同一 banked 拍换更优已判候选——已证无存量空间,故此项预期需新判定,属后续授权)。

```
STAGE13-AUDIT = PASS · STOP(等待授权)
基线:严格 6.7% / inclusive 60.0% · 缺口 48 拍或 276.4s · 主要瓶颈:48 个 CONDITIONAL 语义未测 + 36 文字卡
最小下一步:测量补全(48 次冻结 CV-2)→ 口径裁决 → VALID_FALLBACK
```
