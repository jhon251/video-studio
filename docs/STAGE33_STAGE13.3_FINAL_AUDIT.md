# Stage 13.3:Final Video Audit 报告

> 纯审计:零模型重调用、零冻结模块改动、零新增素材、M3 口径未变。
> 方法:冻结判定存量证据的语义一致性扫描 + 全 90 clip signalstats + 全片 blackdetect/freezedetect/silencedetect + 账本相邻重复分析。
> 原始数据:`stage13_3_audit/final_audit.json`。

## 1. CORRESPONDING(56 拍)语义误判检查 — PASS(1 项 borderline 记录)

| 层 | 数量 | 检查方式 | 结果 |
|---|---|---|---|
| USABLE 锚点 | 6(S06-B02、S15-B01、S23-B01、S23-B02、S26-B03、S27-B01) | fit 0.80–0.90 + 冻结 USABLE 判定(历史未存 reason,按授权不重调用) | 无矛盾证据 |
| 13.1 重测拍 | 48 | reason 文本强负面词扫描("无关/完全不符/不能使用/无法使用") | **0 命中** |
| 13.2 释放拍 | 2 | 同上 + borderline 检查 | **1 项 borderline** |

**Borderline 记录(唯一)**:S01-B03(口播:"选择权面临终极拷问";素材:城市十字路口俯拍)reason 含"仅能作为背景素材使用"——relevance=MEDIUM,按 M3 口径(USABLE + relevance HIGH/MEDIUM)计入对应,**口径内成立**,但功能上接近氛围画面,如实记录供口径裁决参考。S19-B02 的 reason 为正向吻合("沉思动作与身份危机主题吻合"),仅背景要素偏差,无问题。

## 2. VALID_FALLBACK(34 拍)— PASS

- 34/34 全部复用**真实素材图像**(同 shot/近邻对应拍的 URL,`fallback_assignments.json` 可溯),无文字卡、无生成占位;
- 全 34 clip signalstats:**0 近纯色帧、0 绿幕嫌疑**;
- 角标「中性画面」在 vf 链中渲染(视觉不可伪装);
- 不计入对应率,账本分类独立。**无变相文字/占位。**

## 3. 全片技术审计 — PASS

| 检查项 | 方法 | 结果 |
|---|---|---|
| 黑帧 | blackdetect(d=0.5, pic_th=0.98)全片 | **0 段** |
| 异常静帧 | freezedetect(n=0.001, d=2s)全片 | **0 段**(STATIC/SOURCE_NATIVE 拍亦未触发) |
| 纯色/绿幕 | 全 90 clip signalstats(YMIN/YMAX/SATMAX) | **0 / 0** |
| 音频空洞 | silencedetect(-35dB, d=1.5s) | **0 段** |
| A/V 同步 | 时长对账 | +0.14s(与 12.26 基线一致) |
| 流规格 | probe | h264 High 1920x1080 25fps + AAC;508.29s(8:28) |
| 渲染完整性 | 逐 clip 时长对账(±0.25s) | 90/90 通过 |

## 4. 问题清单(全部为记录项,无 FAIL 项)

1. **[borderline] S01-B03**:"背景素材使用"caveat——M3 口径内成立,如上;
2. **[量化记录] 18 组相邻同素材切换**(89 个过渡中占 20%):兜底复用近邻素材的固有代价(34 个兜底全部来自既有素材,不新增源的约束所致),同一 shot 内语境连续,非无源突兀;已逐对记录于 `final_audit.json`;
3. **[记录] 6 个锚点拍无 reason 文本**(历史 runner 未持久化;fit 0.8–0.9 + USABLE 判定证据充分,按授权不重调用);
4. **[记录] S18-B02(USABLE)未释放**:候选 ID/URL 不在已获取范围,13.2 保守放弃。

## 5. 最终裁定

```
STAGE13.3 FINAL AUDIT = PASS
语义误判:0 项(1 borderline 记录)· 兜底:34/34 合法可看 · 黑帧/绿幕/纯色/异常静帧/音频空洞:全部 0
问题清单:4 项记录,0 项 FAIL · 成片 508.29s / 60.86% CORRESPONDING / 39.14% VALID_FALLBACK
STOP——等待下一步授权
```
