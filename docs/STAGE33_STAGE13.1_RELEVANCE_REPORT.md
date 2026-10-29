# Stage 13.1:Correspondence 真值补全报告

> 纯测量:48 个 `MATERIAL_BUT_MISMATCH` beat 用**原素材 + 原 CV-2 prompt + 原调用签名**(`vision_call(key, image_path, narration, visual_intent[:200]`)重新调用冻结 CV-2;narration 与 visual_intent 同源(recovery_v2 narration + sha 缓存);绝大多数 beat 直接使用**原始 stage meta 中的原始已下载文件**(即原判定时看过的同一图像)。6 个 CORRESPONDING 未重测(按授权)。零冻结改动、零新模型、零新素材源、零搜索。

## 1. 三口径真值谱系(90 拍 / 508.16s)

| 口径 | 拍数 | 时长 | 拍占比 | 时长占比 | **距 60% 缺口** |
|---|---|---|---|---|---|
| **M1:USABLE only**(冻结历史判定) | 6 | 28.5s | 6.7% | **5.6%** | **48 拍 / 276.4s** |
| **M2:USABLE + relevance=HIGH** | 26 | 141.8s | 28.9% | **27.9%** | **28 拍 / 163.1s** |
| **M3:USABLE + relevance=HIGH/MEDIUM** | 54 | 296.0s | 60.0% | **58.2%** | **0 拍 / 8.94s** |

口径规则(计算前锁定):M1 = 冻结历史判定,重测方差**不并入**(只记录);M2/M3 = M1 ∪ 重测 `semantic_relevance` 达标的拍;36 个 EMPTY 不计入任何口径;6 个锚点拍(USABLE)按授权未重测,计入全部三口径。

## 2. 48 拍语义相关性分布(重测)

| relevance | 拍数 | 占 48 |
|---|---|---|
| HIGH | 20 | 41.7% |
| MEDIUM | 28 | 58.3% |
| LOW | **0** | 0% |

**关键读数:48 个"有素材但不直接对应"的拍中,没有一个 LOW**——它们全部至少语义相关(MEDIUM),其中 20 个 HIGH。即 Stage 12 留下的素材库没有"语义错位"素材,只有"相关性强度未分级"素材。真实对应率因此被夹在 **5.6%–58.2%** 之间,具体落点取决于"明确语义对应"的裁决口径(用户决策项,本轮不预设)。

## 3. 重测一致性(只记录,不改冻结决策)

**12/48(25%)拍的重测 label 与历史不一致**,全部为 CONDITIONALLY_USABLE → 重测偏 USABLE(fit 0.75–0.85):
S08-B02、S11-B01、S11-B02、S12-B02、S13-B03、S16-B01、S18-B01、S20-B03、S23-B03、S29-B03、S30-B01、S34-B01。
反向不一致(降级)为 0。这是冻结判定在 run 级方差的真实体现:CONDITIONAL 与 USABLE 的边界带较宽。**所有 banked 状态与冻结决策原样保留**,方差仅记录在 `correspondence_spectrum.json` 的 `inconsistencies_recorded_only` 字段。

## 4. 逐拍 provenance

`stage13_1_relevance/correspondence_spectrum.json`:90 行完整谱系,每行含 `beat / asset / old_label / semantic_relevance / reason / new_label / new_fit / consistent / final_class / duration_s`;原始逐拍响应在 `relevance_results.json`(含 confidence 与 reason 全文)。48/48 全部测得,90/90 全部有 final 分类。

## 5. 结论与下一步选项(仅列示,待授权)

- **当前真实对应率**(三口径):5.6% / 27.9% / 58.2%;
- **距 60%**:276.4s / 163.1s / 8.94s——若采用 M3 口径,差距仅 8.94 秒(几乎全部 EMPTY 时长拖累),拍数口径已达标;
- 若采用 M1/M2 口径,缺口主要来自 CONDITIONAL 素材的相关性天花板(重测已给出每拍 reason,可供逐拍裁决)与 36 个 EMPTY 拍;
- 可选项(均需授权,本轮未动):① 采纳某一口径为正式标准;② VALID_FALLBACK 消除文字卡(影响时长占比);③ 对低相关(HIGH 之外)素材做逐拍处置。

```
STAGE13.1 = PASS · STOP(等待授权)
真值谱系:M1 5.6% / M2 27.9% / M3 58.2% · 48/48 重测完成 · 12 项方差已记录 · 冻结决策零改动
```
