# Stage 33 — EXP-21.1: Full-Film Semantic Reuse / Material Fatigue Audit

> **性质**:离线 · 只读 · 诊断实验(已获授权)。零网络 / 零检索 / 零下载 / 零 CV2 / 零渲染 / 零冻结模块修改 / 零决策改写。
> 对象:母片 `render_162/final_long.mp4`(508.29s,90 拍,B-state 含 3 个两锁 Analogue)。
> 机器可读:`output/stage21_visual_quality/stage21_1_semantic_reuse.json`(证据链:`_exp211_workmap.json` → `_exp211_analysis.json`)。

## 1. 研究问题与结论

> 核心假设:"同一素材的重复问题不应简单定义为 usage_count,而应区分是否产生新的视觉语义/叙事功能。"

**结论:假设被精化(refined),且比预期更彻底——**

1. **全片 33 次重复事件,100% 显示完全相同的视觉信息**(静态图片,同字节同内容)。**没有找到任何一次"新视觉信息"型复用**;
2. 其中 **11/33 次连叙事角色也相同**(纯同功能疲劳);**22/33 次叙事角色变化,但第二次使用全部是 fallback 借用**(换旁白不换信息,信息增量为零);
3. **疲劳的机械成因是 fallback 借用**:34 个 fallback 拍借用邻近拍素材充当氛围填充,直接制造了 2/3 的重复事件。B1(198.9s fallback)与素材疲劳是同一现象的两面;
4. **"相邻不重复"≠"不疲劳"被实证**:全片 0 次相邻重复(与冻结 adjacent same-byte=0 一致),但 33 次重复全部为短程(2–10 拍内),旗舰案例:Strand 街口人行道在前 ~40s 内出现 3 次;
5. **高质量素材不能豁免**:医生/MRI(frozen LITERAL_STRONG,审片 8/10)第二次使用是 fallback 氛围借用,对该拍旁白(价值定义/共生)零信息贡献——semantic fatigue 成立;
6. 审片的长程"又看到了"印象对应**素材族级重复**(不同资产、同一内容族),不是字节级复用。

## 2. 账本重建与交叉验证

全 90 拍账本:`build_ledger()`(banked33 + 12.26 pexels 释放 + 13.2 释放,56)⊕ `fallbacks_v3`(34)⊕ 3 个 Analogue 采纳叠加 = **90/90 全覆盖**。

**交叉验证(ENGINEERING_VERIFIED)**:独立重算 multi_use = **29**,与 19.3/19.4/19.6 冻结统计精确一致 → 账本重建有效。

Asset Identity:`source_url` 优先,fallback 层有 `content_hash`;未定义新 Asset Contract。

## 3. 核心指标(全部为诊断量,不是生产阈值)

| 指标 | 值 | 说明 |
|---|---|---|
| unique_assets | 57 | — |
| total_asset_usages | 90 | — |
| reuse_rate(用法位) | **68.9%** | 62/90 次显示来自 29 个多用途素材 |
| asset_reuse_rate | 50.9% | 29/57 素材被复用 |
| adjacent_duplicate_rate | **0.0** | 33 事件中 0 次相邻(与冻结一致) |
| short_range_reuse_rate | **100%** | 33/33 全部在 2–10 拍内 |
| long_range_reuse_rate | **0.0** | 0 次 >10 拍 |
| same_function_reuse_rate | **33.3%**(11/33) | 纯同功能疲劳 |
| new_function_reuse_rate | 66.7%(22/33) | 角色变化但信息零增量(其中 22 次第二用全为 fallback 借用) |
| unknown_reuse_rate | 0.0 | 无需 UNKNOWN 的事件级判定 |
| material_fatigue_candidates | **25 / 29** | 多用途素材中 25 个带疲劳事件 |
| generic_asset_share / duration_share | 78.9% / **49.5%** | GENERIC 45 拍 |
| evidence_asset_share / duration_share | 36.8% / **23.0%** | EVIDENCE 21 拍 |
| (其余)METAPHOR | 10 拍 / 12.1% | HONEST_NEUTRAL 3 / 2.6% · UNKNOWN(MISMATCH_RISK) 11 / 12.8% |

Generic 判定方法:Stage 21 框架作用于冻结标签,优先级 HONEST_NEUTRAL > METAPHOR(et=REAL_METAPHOR)> EVIDENCE(grade LITERAL_*)> GENERIC > UNKNOWN;**未使用关键词规则**。

## 4. MATERIAL_FATIGUE_CASEBOOK(Top 20,全量见 JSON)

| # | Asset | 用次 | Beats | Same Fn | New Fn | 风险 |
|---|---|---|---|---|---|---|
| 1 | Newport university building under scaffolding(工地脚手架) | 3 | S07-B01/S08-B02/S09-B02 | 1 | 1 | HIGH |
| 2 | A focused young man typing on a computer(人+屏幕) | 3 | S04-B02/S06-B02/S07-B02 | 0 | 2 | HIGH |
| 3 | Strand street pedestrian crossing(花坛/人行道) | 3 | S01-B01/S02-B01/S03-B01 | 0 | 2 | HIGH |
| 4 | City skyline at dusk(天际线) | 3 | S05-B03/S06-B03/S08-B01 | 0 | 2 | HIGH |
| 5 | Silhouette of a man using a smartphone(白T手机类) | 2 | S17-B01/S18-B02 | 1 | 0 | HIGH |
| 6 | A person in a pink jacket squats(蹲姿人) | 2 | S04-B01/S05-B02 | 1 | 0 | HIGH |
| 7 | Adult using smartphone indoors(白T手机) | 2 | S01-B02/S02-B02 | 1 | 0 | HIGH |
| 8 | Business professionals collaborative meeting(会议室) | 2 | S26-B01/S27-B02 | 1 | 0 | HIGH |
| 9 | Department of Traffic and Engineering worker(控制室邻类) | 2 | S16-B01/S17-B02 | 1 | 0 | HIGH |
| 10 | Silhouette businessman in luxury apartment(剪影人) | 2 | S31-B03/S33-B01 | 1 | 0 | HIGH |
| 11 | Formal business meeting(会议室) | 2 | S05-B01/S06-B01 | 1 | 0 | HIGH |
| 12 | Raphael in his Studio(油画/创造力象征) | 2 | S11-B02/S13-B03 | 1 | 0 | HIGH |
| 13 | Aerial view of people crossing city street(街口) | 2 | S01-B03/S02-B03 | 1 | 0 | HIGH |
| 14 | Senior adults attend a computer class(课堂) | 2 | S22-B03/S23-B03 | 1 | 0 | HIGH |
| 15 | Lone office worker(办公室) | 2 | S23-B02/S24-B02 | 0 | 1 | HIGH* |
| 16 | HCMC skyline(天际线族) | 2 | S24-B01/S25-B02 | 0 | 1 | MED |
| 17 | Tesla giga press robot megacasting(工厂机械臂) | 2 | S30-B01/S31-B02 | 0 | 1 | MED |
| 18 | Close-up office workers tech project(办公室) | 2 | S15-B01/S16-B02 | 0 | 1 | MED |
| 19 | Atlanta City Night Lights(城市夜景) | 2 | S25-B01/S26-B02 | 0 | 1 | MED |
| 20 | Panama City skyline aerial(天际线族) | 2 | S09-B01/S10-B02 | 0 | 1 | MED |

\* #15 为**叙事冗余特例**:两次使用的旁白主题几乎相同("白领岗位自动化率超 50%"),图像与论点双重重复,全片最强疲劳案例。
另有 Medical professional reviewing MRI scans(医生/MRI)×2(S20-B02→S21-B02)未入 Top20 排序但为**授权要求的专项案例**,见 §5。

每个案例可通过 JSON 中 `semantic_reuse_cases`(33 条,含逐事件 narration、kind、et/grade、role、距离、判定)回溯至 `stage19_diagnostic.json` / `stage161_assignments.json` / `production_bank.json` / `stage19_experiment/abstract_analogue_ledger.json` 原始记录。

## 5. 专项案例:医生/MRI —— 高质量素材的 semantic fatigue(授权要求验证)

| | 第一次使用 S20-B02 | 第二次使用 S21-B02 |
|---|---|---|
| 层级 | MATERIAL(冻结 LITERAL_STRONG) | FALLBACK 借用 |
| 旁白 | "像电力一样融入日常——从**医疗诊断**到法律判决…" | "人类的工作重心转向定义价值与目标,AGI 负责执行与优化…" |
| 画面贡献角色 | DEMONSTRATE(旁白点名医疗诊断,影像工作站直接承载) | ATMOSPHERE_BACKDROP(旁白谈价值定义/共生,MRI 画面零信息贡献) |

**结论:成立**——素材质量(8/10)不豁免 semantic fatigue。第二次使用的信息增量 = 0。这直接证明 Stage 21 的核心主张:需要"证据质量"评价层,而不是更好的"相关"门。

## 6. 素材族聚类(analyst 分组,方法透明,非生产定义)

对账本标题做显式 token 分组(可复现):person_with_screen **17 拍 / 99.5s** · street_crossing_traffic **17 拍 / 82.1s** · skyline_city_aerial 14 拍 · office_meeting 14 拍 / 77.2s · classroom_school 12 拍 / 63.7s · robot_arm_industrial 7 拍。审片的"万能素材反复出现"对应这些族级重复:**字节级 reuse=29 无法捕捉,族级才是观众疲劳的感知单位**。

## 7. 审片报告 vs 工程核验(归因)

| 审片观察(均 OBSERVED_BY_REVIEWER) | 工程核验 |
|---|---|
| 整体 4.5/10、AI 卡片感 | 无对应工程量(CARD_FEEL 为设计态,21.1 未计算) |
| 花坛/人行道 ≥5 次 | Strand 同一资产 **3 次**(前 ~40s 内);街口/街道族 17 拍(analyst 分组) |
| 白 T 恤打手机 ~3 次 | smartphone 族 **4 次** / 2 个资产(精确) |
| 工地脚手架 ~3 次 | 资产级精确 **3 次**(S07-B01/S08-B02/S09-B02)✅ |
| 控制室大屏 ~2 次 | City tv control room 精确 **2 次** ✅(另有独立的高雄交通控制室资产 ×1) |
| 伦敦天际线 ~2 次 | skyline 标题族 **7 拍** / 3 资产(高于审片估计) |
| Pete 走路男子 2–3 次 | 账本无法唯一标识 → **UNKNOWN** |
| 医生/MRI ~8/10 | ×2 实证 + semantic fatigue 确认(§5) |
| Generic 60–65% | 工程 GENERIC 时长 49.5%;+MISMATCH_UNKNOWN 12.8% = 62.3% 非强证据材料——审片印象与工程普查兼容 |
| (隐含)reuse 25–30% | asset_reuse_rate 50.9% / 用法位 68.9% |

## 8. 假设更新

- **H1(Generic 60–65%)**:PARTIALLY SUPPORTED(工程 49.5% 时长;口径差异已量化);
- **H4(Semantic Reuse 分型)**:REFINED——100% 重复信息恒同,22/33 角色变化但零信息增量;"新功能允许复用"在本片**无支持实例**;
- **H7(相邻≠不疲劳)**:**CONFIRMED**(旗舰案例 Strand 3 次/40s);
- **H8(高质量素材豁免)**:**REFUTED**(MRI 案例);
- **H9(fallback 借用是疲劳机械成因)**:**SUPPORTED**(22/33)。

## 9. 成功标准自检

1. reuse 有多严重?→ 68.9% 用法位集中在 29 个素材;25/29 多用途素材带疲劳事件;
2. 哪些是同功能重复?→ 11/33(FATIGUE_SAME_FUNCTION,JSON 逐条);
3. 哪些是新功能重复?→ 22/33 角色变化,但**全部零视觉信息增量**,其中 14 次为借用填充、8 次为有叙事关联的二次使用(CONTESTABLE);
4. 相邻不重复但长程疲劳?→ 短程簇为主(33/33 ≤10 拍),长程疲劳为**族级**现象(§6);
5. Generic 能否稳定识别?→ 可从冻结标签按显式优先级导出(MISMATCH_RISK 留 UNKNOWN 待 EQS);
6. 下一步是否值得?→ **值得**:EXP-21.2(E1–E7 逐拍标注)、21.3(CARD_FEEL)、21.4(Minimum Unit)、21.2b(族级多样性)已具数据基础。

## 10. 冻结边界

零冻结模块/生产代码修改,零决策改写,零渲染,零检索/下载/网络,零新 APPROVED;Production Status = CONDITIONAL GO 不变;Pre-flight = BLOCKED 不变。本实验产物仅为审计文档 + JSON + 中间证据文件。

```
EXP-21.1 = COMPLETE · STOP
90/90 拍账本重建(multi_use 29 与冻结统计精确吻合) · 33 次重复事件全短程(2–10 拍) · 0 相邻 · 0 长程 ·
100% 重复信息恒同(0 新信息复用) · 11 同功能疲劳 / 22 角色变化(全为 fallback 借用填充 14 + 关联复用 8) ·
25/29 多用途素材带疲劳事件 · 旗舰案例 Strand 3 次/~40s · 医生/MRI 高质量素材 semantic fatigue 确认 ·
族级聚类:人+屏幕 17 拍 / 街道 17 拍 / 会议室 14 拍 / 天际线 14 拍 · 审片数字全部保持 OBSERVED_BY_REVIEWER ·
指标全部为诊断量,不成为生产阈值
STOP——不进入 21.2,等待授权
```
