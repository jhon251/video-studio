# Stage 19.1:局部 Visual Evidence Reassignment 实验报告(W07 / W50 / W67)

> 严格约束全程执行:零新检索、零新来源、零 Intent/Query 改动、Gate/V1/CV2/阈值/权重零改动、Reuse Policy 零改动、生产逻辑零改动、无全片重排、narration/timeline/字幕/composition/motion 不变。所有候选均来自**已持有且带冻结判定/provenance** 的素材。

## 1. 实验设计

A = 生产基线(W07=53.7 / W50=55.9 / W67=68.9);B = 在已有候选池内的局部重指派。候选库穷举四类(库存脚本 `inventory_191.py`):

| 候选类 | 内容 | 结果 |
|---|---|---|
| ① 本拍 own-pool 备选(判定在本拍) | S03-B03 备选 0.15 NU;S21-B01 备选 0.15 NU;fallback 拍全池 0.1–0.3 NU | ❌ 全 NOT_USABLE(采用 = 牺牲单拍质量,禁止) |
| ② 跨拍已持有胜出素材(18.1/18.2 冻结判定,未指派) | Garner 0.90、Zamboanga 0.72、LabCoat 0.75、Minister 0.40、CERN 0.95、Westmoreland 0.72 | ❌ **目标拍冻结 CV-2 实测全部 NOT_USABLE(fit 0.0–0.2)**(下表) |
| ③ 当前已指派素材(90 拍全部在用) | — | ❌ 任何挪用 = 复用违规 |
| ④ 17.3 缓存图像 | Mumbai 0.2 / Gaza 0.1+内容风险 / HRC 0.2 / Martin 0.9(工厂工种语义,绑定 S30-B01 叙述) | ❌ 质量/语义均不合 |

**② 的目标拍冻结判定**(frozen vision_call,原始参数,完整 provenance 在 `r191_measurements.json`):

| 候选 → 目标拍 | fit | label | rel |
|---|---|---|---|
| Garner → S03-B02 | 0.0 | NOT_USABLE | LOW |
| Zamboanga → S04-B01 | 0.0 | NOT_USABLE | LOW |
| LabCoat → S21-B02 | 0.2 | NOT_USABLE | HIGH |
| Minister → S28-B02 | 0.0 | NOT_USABLE | LOW |

## 2. 结论:B ≡ A(不存在合规重指派)

四类候选全部被冻结约束排除。唯一合规的 B = 空重指派,即三个窗口保持 A 状态:

| 窗口 | A SQS | B SQS | Δ | 判定 |
|---|---|---|---|---|
| W07 | 53.7 | 53.7 | 0 | ❌ 未达 +10 |
| W50 | 55.9 | 55.9 | 0 | ❌ 未达 +10 |
| W67 | 68.9 | 68.9 | 0 | ❌ 未达 +10 |

验收门槛(每窗 +10,至少 2/3)在约束集内**结构性不可达** → 按验收条款 8:**STOP,不扩大窗口范围**。correspondence / reuse / 冻结链零违规(空变更下平凡成立)。

## 3. 结构性发现(本实验的核心价值)

三个最差窗口差在**narration 本身抽象**(S03"价值定义/存在意义"、S21"共生生态"、S27"创造力凋零"、S28"责任二字")——这正是它们 own-pool 全灭、沦为 fallback 填充的原因;而冻结 CV-2 rubric(narration+focus 直接对应)**结构性地拒绝一切具体证据素材进入抽象叙述**(实测 fit 0.0–0.2)。

→ 序列病灶是**叙述驱动**而非**指派驱动**:在冻结系统内,这三个窗口的序列质量已处于上限。改善路径只剩两条,均在禁区:(a) 为抽象叙述做新检索(Stage 18 已关闭的 Retrieval 边界);(b) 放宽质量判定(禁止)。**"单拍 HIGH 但序列差"的案例(S21-B01 等)由此获得因果解释:叙述抽象 → 素材池薄 → fallback 拼接 → 窗口断裂,与素材本身质量无关。**

## 4. 局部测试视频与真实观看验证

B ≡ A,故无 B 版可渲染;按授权渲染 **3 个 A 基线窗口视频**作为视觉序列验证记录(`render_191/`,provenance manifest `render_191_manifest.json`):
- `window1_A_baseline.mp4`(S03-B02→S04-B01,19.20s)· `window2_A_baseline.mp4`(S21-B01→S22-B01,6.49s)· `window3_A_baseline.mp4`(S27-B03→S28-B02,18.60s)——冻结逐拍管线(16.2 motion 决策、composition、字幕烧录、shot 音频切片)原样复现,字幕烧录全部成功;
- 信号审计:0 黑帧;freeze 事件 4 处均为 16.2 设计内 STATIC 槽(静帧策略),非回归;
- 逐帧 JPG 已存于 `render_191/`(w*_f*.jpg)供人工复核;由于 B ≡ A,不存在"指标改善但真实观看更差"的可能(验收 7 无失效面)。

## 5. 产物

`stage19_experiment/stage19_1_results.json`(A/B 全字段 + 候选拒绝表 + 目标拍判定)、`render_191/`(3 视频 + manifest + 信号审计 + 帧)、本报告。生产文件零改动。

```
STAGE19.1 = FAIL · STOP
合规重指派空间为零(own-pool NU / 跨拍胜者目标拍实测 NU 0.0-0.2 / 在用素材复用违规) · B≡A · 0/3 窗达 +10 · correspondence/reuse/冻结链零违规 · 结构性结论:三窗病灶为叙述驱动(抽象叙述拒绝具体证据),冻结系统内已达序列上限 · 触发验收条款 8,不扩大窗口
STOP——等待下一步授权
```
