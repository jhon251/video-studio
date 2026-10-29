# Stage 20.1:B1 Fallback 段池内离线重指派报告

> 唯一研究问题:**在不检索、不下载、不调用 CV2、不修改冻结模块的前提下,能否用已有且已通过冻结链判定的存量素材,替换部分 198.9s Fallback 氛围段,使其真正承担叙事功能?**
> 全程零网络、零新候选、零新 CV2;只用 verdict store(1226→181→196 谱系)+ 19.8 ledger + 已有 provenance;60.86% 与 60% 标准原值不动。

## 1. 全 34 个 fallback beat 的离线候选审计(先审计,后决定)

**候选存量盘点**:verdict store 共 164 条冻结 CV2 判决(12 USABLE + 59 CU + 93 NOT_USABLE),其中未显示的合格 spare 28 个。

**预注册合法 B 定义**(先于结果注册,分两档):
- **Tier 1(强)**:spare 在**回退槽自身的叙述/intent 上**经冻结链判定合格(USABLE/CU),fit ≥ 槽 SBQ,单使用,无相邻碰撞,不在 Analogue ledger 管辖内;
- **Tier 2(移植)**:spare 在其他拍判定,槽叙述相似度须 ≥ 冻结 subject_same 阈值 **0.34**——低于此即"制造伪对应",禁止(约束 11)。

**审计结果**:

| 类别 | 数量 | 明细 |
|---|---|---|
| **Tier 1 合法 B** | **1** | S18-B02 ← "Crowd enjoying a sunny day at Alexanderplatz" **0.92 USABLE** |
| Tier 1 但被排除 | 3 | S04-B01 Dubinsky(Analogue ledger:链不完整伪对应证据)、S21-B02 LabCoat(复用)、S28-B02 Tempi(内容风险)——**均不得借"literal 重指派"绕过 Analogue 管辖** |
| Tier 2 拒绝 | 7 | 最高相似度 0.167,全部低于 0.34 冻结阈值 → 拒绝制造伪对应 |
| 无候选 | 23 | 维持现状(HONEST_NEUTRAL 语义) |

**S18-B02 的完整 provenance 链**(本候选为何合法):
`stage12_23 pexels 检索发现 → stage12_26 冻结链在本槽自身叙述上判定 0.92 USABLE(verdict_store_1226)→ 判决经 181/182/193/196 store 存续且从未被推翻 → stage13_2 empty_lever_scan 明确认证 "production_path_releasable"(LEGAL RELEASE EXISTS)但从未执行 → 生产 t1-fix 重跑自身搜索失败(cv2_not_usable)→ 槽位成为 fallback 借用 S17-B01 剪影填充`。
即:**这是一个被 Stage 13 文档化认证为可合法释放、却因流程冻结而搁置的现成判定**。本地文件 `stage12_23_pexels/asset_cache/files/b46_S18_B02_9951446.img.jpg` 经消去法确认(S18-B02 的 cv2 候选中 pexels 系仅此一个;12.x 缓存中 S18-B02 的 pexels 下载亦仅此一个)——零下载。

## 2. 预注册停止条件分支

**实得 1 个合法 B → 命中"1–2 个:仅报告局部收益,不扩大"分支**:只对 S18-B02 做局部 A/B,不扩大到其他拍。

## 3. 局部 A/B(冻结 A–E,离线重算)

| 指标 | A(现状) | B(重指派) | Δ |
|---|---|---|---|
| W42 [S16-B02, S17-B01, S18-B01] | 80.0 | 86.0 | **+6.0** |
| W43 [S17-B01, S18-B01, S18-B02] | 85.2 | 94.2 | **+9.0** |
| W44 [S18-B01, S18-B02, S18-B03] | 84.6 | 94.2 | **+9.6** |
| **净(受影响窗)** | | | **+24.6,PASS** |

- **SBQ**:0.45 → 0.92(非牺牲,大幅提升);
- **fallback duration / correspondence**:类别不动——仍 34 拍 / 198.9s / **60.86%**(原值 = 实验值,无 correspondence 认定);
- **ATMOSPHERE stacking**:该槽 et ATMOSPHERE→REAL_EVENT(真实人群广场影像,5.62s 真实视觉信息净增);全片双 ATMOSPHERE 对 16→16(该槽邻拍本非 ATMOSPHERE,收益来自 CONT/ALI);
- **reuse**:单使用素材,multi_use 29→29,无相邻碰撞;
- **RA**:槽位仍为 fallback 类,RA 计数不变(重指派记为 pool-reallocation 标注,非表征升级)——Literal/Analogue/Neutral 不混算;
- **Provenance**:beat → 槽叙述 → 候选 → 冻结判决(0.92 USABLE,store 谱系)→ 13.2 releasable 认证 → 五锁 → 序列判定 → 决定,全链入档。

## 4. 局部 A/B 视频(冻结管线)

`stage20_experiment/render_201/`:W42/W43/W44 三窗 B 态视频(17.15s / 17.92s / 22.02s),冻结逐拍管线(composition/motion/timing 决策原样),字幕烧录成功,**0 黑帧**;provenance manifest + 信号审计在 render_201/。

## 5. 诚实结论

- **"池内可解"假设:部分成立但边界极窄**——34 个 fallback 槽中仅 1 个存在完整合法 B(S18-B02,且是 13.2 早已认证未执行的存量)。B1 的主体(198.9s 中的 ~193s)**不在池内可解范围**:其余槽位的自身链搜索当时即已失败(如 S18-B02 的 t1-fix 重跑),或候选属 Analogue 管辖/复用受限;
- 按预注册,**不扩大**:其余 33 槽维持 HONEST_NEUTRAL 语义,无伪对应、无冻结件改动、无 correspondence 变化;
- 该 1 槽的收益(W42–W44 净 +24.6)证明:**若未来授权更宽的池内或检索线,fallback 槽的叙事功能升级仍有真实空间**——但那是新授权决策,不是本阶段内容。

## 产物

本报告;`stage20_1_results.json`(扫描/合法 B/A-B/门禁/渲染);`stage20_1_scan.json`(全 34 槽审计明细);`render_201/`(3 窗视频 + manifest + 信号审计)。零检索、零下载、零 CV2、零冻结件修改。

```
STAGE20.1 = PASS · STOP
全 34 槽离线审计先行 · 预注册 Tier1/Tier2(0.34 冻结阈值) · 合法 B 恰 1 个:S18-B02 ← Alexanderplatz 0.92 USABLE(自槽冻结判定,13.2 认证 releasable 未执行,本地副本消去法确认,零下载) · 3 个 Analogue-ledger 候选拒绝借道 · 7 个 Tier-2 移植全部拒绝(<0.34,拒绝伪对应) · 受影响窗净 +24.6(W42 +6.0/W43 +9.0/W44 +9.6) · SBQ 0.45→0.92 · 类别不动,60.86% 原值=实验值 · reuse 29→29 · 3 窗 B 态视频渲染(0 黑帧) · 其余 33 槽维持 HONEST_NEUTRAL · 池内可解假设:仅 1 槽成立,主体不可池内解
STOP——不自动进入 20.2;等待授权
```
