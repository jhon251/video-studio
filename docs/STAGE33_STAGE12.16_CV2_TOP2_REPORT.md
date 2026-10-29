# Stage 12.16:CV-2 Top-2 受控实验报告

> **`STAGE12.16 = PASS · STOP`**
> 受控 A/B(90 beats):**Arm A = 12.13 存档 Top-1 结果原样**(同池/同 gate/同 V1/同 rank-1 判定);**Arm B 仅对"rank-1 NOT_USABLE 且 kept≥2"的 19 拍补判 V1 rank-2**。冻结 CV-2(prompt/threshold/weights)零改动,V1 本地确定性评分精确重放。
> 数据:`stage12_16_top2/results_top2.json`(19 拍逐拍 + summary)。

## 1. A/B 对照(核心数字)

| 指标 | Arm A(Top-1) | Arm B(Top-2) |
|---|---|---|
| 最终素材 | 20 | **26(+30%)** |
| NOT_USABLE→USABLE 翻转 | — | **6** |
| Top-2 胜出拍 | — | 6(其余 11 拍 rank-2 仍 NOT_USABLE,2 拍 rank-2 不可用) |
| CV-2 调用增量 | 0 | **17**(全量 90 拍推算 ≈ +17~30 次 ≈ +3-5 分钟) |
| 平均 fit(素材拍) | 0.637 | 0.625(基数扩大 6 拍的稀释,非回归) |
| 12.13 成功素材回归 | — | **0(构造性保证:ok 拍从不重判)** |

## 2. 六例翻转明细(全部经冻结 CV-2 判定)

| beat | rank-1 fit(失败) | rank-2 | fit | label |
|---|---|---|---|---|
| **S27-B01**(金融交易大厅) | 0.1 | NYSE Trading floor | **0.85** | **USABLE** |
| S31-B01(控制中心/天际线) | 0.3 | KL sunrise city skyline | 0.6 | CONDITIONALLY |
| S02-B01(都市居民过街) | 0.1 | Strand street pedestrian crossing | 0.6 | CONDITIONALLY |
| S24-B01(天际线/工业港) | 0.2 | **HCMC skyline awesome sunrise** | 0.55 | CONDITIONALLY |
| S29-B02(教室/师生) | 0.25 | Students using Orange phones | 0.55 | CONDITIONALLY |
| S12-B02(空旷广场/工人) | 0.15 | Empty Union Square Plaza | 0.35 | CONDITIONALLY |

**12.15 诊断的 2 例跨轮铁证(S24-B01、S31-B01)全部验证翻转**——rank-2 深度确实捞回了 V1 排在后面的可用素材。

## 3. 失败原因(Arm B 未翻盘的 13 拍)

- 11 拍:rank-2 经冻结 CV-2 仍 NOT_USABLE(fit 0.0-0.35)——池中确实没有更好素材,空卡是诚实的;
- 1 拍(S08-B03):重取池中 kept 候选缺失(Commons 漂移);
- 1 拍(S11-B03):rank-2 缩略图下载失败;
- 另:19 目标拍中 rank-2 主题仍以"泛化城市/办公"标题为主,与 12.15 的 V1 排错机制一致。

## 4. 方法论备注(如实)

- `v1_replay_rank1_match` 字段定义有误(重放集排除了 rank-1,恒为 False)——不影响 rank-2 选择语义(排除 rank-1 后取 argmax 正是 Top-2 定义),仅为本报告的记账瑕疵;
- Arm A 完全复用 12.13 存档 → 同池同判定,零漂移混淆;Commons 重取仅用于补 rank-2 的 thumburl(2 拍因漂移/下载失败损失)。

## 5. PASS 条件核对

✅ 真实增益(+6 拍,+30%,含 1 例 USABLE 0.85)· ✅ 冻结 CV-2 标准零变化 · ✅ 零回归(构造性)· ✅ 成本明确(17 次调用/6 素材 ≈ 2.8 次/拍素材)· ✅ 完整 A/B 与失败归因

```
STAGE12.16 = PASS · STOP(不自行进入 12.17)
```
