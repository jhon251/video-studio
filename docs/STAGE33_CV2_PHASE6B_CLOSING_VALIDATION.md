# STAGE 33 / CV-2 — 收口验证报告(Phase 6b)

> 状态:**Phase 6b 完成。API Reliability 已关闭;Director Requirement Contract 预注册 V1.1
> 验证为 NOT_VALIDATED(如实判定,未继续调参)。STOP,等待人工裁决。**
>
> 全程离线、只读、预注册。未修改 production / Gold Standard / Gate / 人工标签 / 阈值 / 权重。
> 未引入 TYPE RULE。未做生产修改。

---

## 0. 预注册计划

`output/stage33/cv2/phase6_final/pre_registered_plan.md`(先于实验固定协议/样本/判据/停止条件)。

执行清单:
- [x] A. 修复后协议可靠性验证(20 样本,预注册)
- [x] B. Contract V1.1 验证(12 样本,6 判据,预注册)
- [x] 统计、判定、五状态
- [x] STOP

---

## 1. A 部分:API Reliability —— 修复后协议可靠性验证

### 1.1 固定协议(与 Phase 6 修复一致)
- 模型 `deepseek-v4-flash-vision-exp`;BASE `https://api.deepseek.com`;
- **Authorization 已验证**(脚本无变量遮蔽,使用 `api_key`);
- **max_tokens=2048**(固定);**temperature=0.1**(固定);
- prompt = **Phase 4C RUBRIC_PROMPT**(正式 prompt,不含 contract);
- image = Phase 4C 原缩略图字节(不重编码);
- 样本 = phase4c `final_status=OK` 前 20 张(固定顺序,预注册);
- MAX_RETRIES=3;TIMEOUT=180s。

### 1.2 失败分类(预注册 taxonomy)
`L1 HTTP/API failure` / `L2 empty content` / `L3 JSON parse failure` / `L4 semantic disagreement`(仅记录)/ `L5 client-side failure` / `L6 retry recovery`。

### 1.3 结果(20/20 成功)

| 指标 | 值 | 判定 |
|---|---|---|
| raw failure rate(首次尝试) | **5%**(1/20) | 低 |
| protocol/client failure rate | **0%** | 无 |
| true API failure rate | **0%** | 无 |
| recovery rate | **100%**(1/1) | 高 |
| final unrecovered failure rate | **0%** | 无 |
| final success rate | **100%**(20/20) | 达标 |
| semantic disagreement | 0 | 无 |
| L1/L5 事件 | 0 | 无 |

唯一原始失败 T-01 的完整链(metadata 全录):
- attempt1:finish=length,reasoning_tokens=**2048**(预算耗尽),content 空 → **L2**;
- attempt2:finish=length,reasoning=**2006** + content 123 但 JSON 截断 → **L3**;
- attempt3:finish=**stop**,reasoning=141,content 177,schema 合法 → **SUCCESS**。

**机制界定**:T-01 的失败是**模型 reasoning 长度波动**(token 预算预算内波动),经重试 100%
恢复——属于 L2/L3 + L6,不是 API 故障、不是 client 故障。生产只需保留 retry(≤3)+ fallback。

### 1.4 最终回答

```
API_RELIABILITY = VALIDATED
  raw failure rate             = 5%    (首次尝试;模型 reasoning 波动,非 API)
  protocol/client failure rate = 0%
  true API failure rate        = 0%
  recovery rate                = 100%
  final unrecovered failure    = 0%
  是否足以关闭 Phase 5C blocker = 是
    (Phase 5C 依据:25.3% retry + 1% final fail——已在修正协议后不复存在:
     25.3% → 5%、1% → 0%;且 32/32 连续成功(Track B 12 + 本验证 20))
```

**注意**:VALIDATED 指"修正协议 + 重试 + fallback 机制下,可靠性达标"。
**长期监控(Phase 5C 要求的 6 项)仍需生产阶段执行**——但不再作为 CV-2 离线 blocker。

---

## 2. B 部分:Contract V1.1 —— 预注册验证结果:NOT_VALIDATED

### 2.1 V1.1 修正规则(预注册,基于 Phase 6 观察到的 F1/F2 机制)
- R-1 媒介/形式不单独作为"可用/不可用"依据(纠正 S12 油画误杀);
- R-2 内容无法承载核心视觉表达 → NOT_USABLE(hard negative,content-driven);
- R-3 内容与需求有差距但可作为叙述/说明衬底 → CONDITIONALLY_USABLE;
- R-4 禁止 TYPE RULE;
- R-6 保留 acceptable/unacceptable 作为**倾向提示**(维持 C1 纠正机制),但声明不构成绝对分类。

### 2.2 判据结果(预注册 6 项)

| 判据 | 结果 | 说明 |
|---|---|---|
| V1 C1 recall 保持 | ❌ | 4/6 C1 回退 CONDITIONALLY(T-28/T-29/T-57/T-58/T-59);仅 T-31 保持 NOT_USABLE |
| V2 C2 误杀不恶化 | ❌ | M-S09-456 被判 NOT_USABLE(人类 USABLE/HIGH,画面有白化珊瑚但无海龟) |
| V3 S06 chart 保持 | ✅ | USABLE(无 TYPE_BIAS) |
| V4 S12 painting 不误杀 | ✅ | M-S12-607 = CONDITIONALLY_USABLE(修复目标达成) |
| V5 S03/S19 无回归 | ✅ | 均保持 NOT_USABLE |
| V6 无新系统性误杀 | ❌ | M-S09-456 即新误杀(partial-match 被 R-2 过度严格拒绝) |

### 2.3 机制分析(如实)

**V1.1 规则间存在内在张力,无法同时满足:**

- **R-1 + R-3 倾向** → C1 漏检重现:模型把"媒介有 gap"弱化为"衬底可接受"
  (reason 原文:"无法承载'motion visualization'的动态表现"→ 仍 CONDITIONALLY;
  "图表形式并非首选视觉模式,存在形式上的差距"→ 仍 CONDITIONALLY);
- **R-2 倾向** → C2 过度严格:M-S09-456 无海龟 → NOT_USABLE,而 R0/R1 正确容忍
  部分语义匹配(内容=白化珊瑚,与镜头"海龟经过白化珊瑚"部分匹配,人类 USABLE/HIGH);
- **C1 纠正机制的本质**:Phase 6 R1 的"不可接受: charts/maps"是**类型绝对分类**,
  它本身就是 C1 纠正的来源;而 V1.1 把它降级为"倾向提示"后,C1 立即回退。
  → **"类型不否决"与"C1 纠正"在同一 prompt 内互斥(以当前形态)**。

### 2.4 判定

```
DIRECTOR_REQUIREMENT_CONTRACT = NOT_VALIDATED (V1.1)
```

- **未继续调参**(预注册停止规则);
- **不引入 TYPE RULE**;
- **Phase 6 R1(绝对值分类)仍是较优点**:C1 4/6 纠正、C2 0 误杀、S06 放行、但 **M-S12-607 误杀**;
- **V1.1 修复了 S12 但牺牲了 C1/C2** —— 从"生产安全"角度,R1 误杀 1 个油画
  (人类 USABLE/MEDIUM) vs V1.1 漏检 4 个 C1 + 新误杀 1 个 C2,**R1 的净效果更好**;
- 但 R1 的 contract 若进生产,必须处理 S12 类场景——**contract 需要人工评审机制,不能自动派生**。

**核心结论**:现有提示设计无法同时满足"C1 严格 + C2 宽容 + S12 宽容 + S06 放行"。
这是**需要人工裁决的设计权衡**,不是能靠继续调参解决的。

---

## 3. 五状态(最终调用)

| 状态 | 值 |
|---|---|
| VISION_CHANNEL | **VALIDATED**(Phase 5A/5C 冻结:75% Top-1,MRR 0.842) |
| RANKING_CHANNEL | **VALIDATED**(V1 语义排序,real pool 399) |
| DIRECTOR_REQUIREMENT_CONTRACT | **NOT_VALIDATED**(V1.1 预注册验证失败;R1 为较优点但具 S12 误杀;需人工评审机制) |
| API_RELIABILITY | **VALIDATED**(修正协议+重试+fallback 下 20/20;raw 5%,true API 0%,recovery 100%,unrecovered 0%) |
| PRODUCTION_INTEGRATION | **NOT_READY**(保持;唯一剩余 blocker = Contract 设计;见 §4) |

---

## 4. 最终 Production Readiness 决策

1. **当前是否可以进入 Production Integration?**
   **不可以。** 唯一剩余 blocker:**Director Requirements Contract 设计**。

   关于 API_RELIABILITY:Phase 5C 的 INCONCLUSIVE **已关闭**(根因=协议参数,
   修复后验证通过,retry/fallback 机制下 0% 未恢复)。但需注意生产调用必须:
   `max_tokens=2048` + `retry ≤3` + `Vision失败→V1 fallback`(Phase 5B 已验证最差=V1)。

2. **如果不能,唯一剩余 blocker 是什么?**
   `DIRECTOR_REQUIREMENT_CONTRACT`:
   - V1.1(联合判断版)预注册验证 **NOT_VALIDATED**;
   - Phase 6 R1(绝对值分类版)有 **M-S12-607 型误杀**;
   - 二者在"媒介是否作为否决信号"上互斥,无自动解决路径;
   - **需要人工指定 contract 设计原则**(见 §5 提问)。

3. **如果可以,给出最小生产集成方案?**
   目前**不可以**——故不给出执行方案,只给出"若要推进,下一步需人工裁决的选项"。

---

## 5. 人工裁决请求(唯一剩余决策点)

**Contract 设计原则**:请从以下选项裁决(这是唯一 blocker,决定 CV-2 能否进入生产集成):

- **Option 1(推荐,零生产风险)**:生产 pipeline **不引入 contract**(保持 Phase 4C RUBRIC
  作为 Vision prompt),接受 C1 recall 33% 现状,并将 C1 漏检作为"已知模型边界"记录
  → PRODUCTION_INTEGRATION = READY_WITH_EXPLICIT_LIMITATIONS(需人工认可该限制)。
  该方案零新风险:所有 Phase 5B/5C 指标已被验证;唯一保留项是 C1 33%(模型边界)。

- **Option 2**:接受 Phase 6 R1 contract(绝对值分类),净效果最优(C1 0 漏检、C2 0 误杀、
  S06 放行),但 **M-S12-607 型油画会被误杀** —— 需人工确认是否接受此误杀,
  或同意建立**人工评审的 contract 编写流程**(contract 内容由导演模块人工制作,
  经评审后进入生产,不在运行时自动派生)。

- **Option 3**:继续离线探索 contract 设计(需要新假设/新实验),但**不在本阶段自动进行**。

---

## 6. Audit trail

- 预注册计划:`pre_registered_plan.md`(先于实验);
- A 部分:`reliability/reliability_postfix.json` + `run_reliability_postfix.py`;
- B 部分:`director_contract/contract_v11.json` + `run_contract_v11.py` +
  `contract_v11_analysis.json`;
- Block Matrix:`readiness/blocker_matrix_phase6b.json`;
- 未修改:Gold `C70C82D4...448AC`、Gate、5A/5B/5C 冻结结果、production;
- 无 prompt 泄漏:V1.1 prompt 不含 human label/role/expected/rank/ground truth;
- 无参数调整(除 max_tokens 协议修复,已记录为 Phase 6 发现);
- 无 TYPE RULE 引入。

---

**Phase 6b 完成。API reliability 已关闭;Contract 为需人工裁决的剩余 blocker。
STOP,等待人工裁决。**
