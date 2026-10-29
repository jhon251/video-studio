# 3.x Phase 1.1 报告：成本计量与稳定性收口

- 日期：2026-09-13
- 范围：**仅**三项——① LLM 费用对账 ② GBK 异常 ③ 语义级分镜↔旁白（**仅方案设计，不实现**）。
- 未开发：BGM、外部素材 provider、自动发布、UI、新 Agent、Phase 2 功能。未删除任何 PENDING；未放宽 Claim/HITL/append-only/exec isolation/断点恢复；未改既有 task/artifact/事件类型（仅**新增** `LLM_CALL`、`TASK_DEPENDENCY_REWIRED` 两个事件类型，Phase 1 已记录）。

---

## 1. LLM 费用对账

### 1.1 结论先行

- **本地台账内部自洽，不是台账算错**：token 数取自 API 返回、`reasoning ⊆ completion` 已实测、时段判定与官方中文价目页一致、单价取自官方页。
- **差额机制已查明**：provider **余额是异步/批量结算**的 —— 实测 3 分钟内**零 API 调用**，余额仍分三步下降 ¥0.79。
- **残余金额无法在客户端归因**（≈¥3.24）→ **PENDING（PARTIALLY_EXPLAINED）**。**没有修改任何数字去凑平两边。**

### 1.2 逐项核查（按要求清单）

| 检查项 | 结果 |
|---|---|
| 真实 API 返回的 usage | 每次调用均记录 `prompt_tokens / completion_tokens / total_tokens / prompt_cache_hit_tokens / prompt_cache_miss_tokens / completion_tokens_details.reasoning_tokens`（`LLM_CALL` 事件） |
| input tokens | 台账合计 **52,128**（全部 cache_miss，命中 0） |
| output tokens | 台账合计 **166,221** |
| cache tokens | API 返回 `prompt_cache_hit_tokens=0`、`prompt_cache_miss_tokens=prompt_tokens`；计价按命中/未命中分档（未命中 ¥1/M flash、¥4.5/M pro） |
| 模型 | `deepseek-flash` 37 次、`deepseek-v4-pro` 12 次（A/B/C 合计 49 次） |
| thinking/reasoning tokens | 台账合计 **87,434**，且实测 `completion_tokens ⊇ reasoning_tokens`（探针：completion 28 / reasoning 26）→ **计费公式未漏算 reasoning** |
| retry（HTTP 层） | 仅 C 组 1 次调用 `attempts>1`；重试的失败尝试所用 token 未被记录（服务端若计费则属漏账，量级极小） |
| schema repair retry | 每次 repair 都走 `Router._call` → **各记一条** `LLM_CALL`（成本测试已断言 records==calls==2） |
| HTTP 失败是否产生费用 | 401/402/400/422 立即抛出（不发重试）；429/5xx/超时按退避重试，失败尝试无 usage 可记 → 若服务端计费则属**不可观测漏账**（本期未观测到该类失败） |
| 首次埋点前 6 次调用 | A 组首次尝试（`p_f2587e967ba8`）在埋点前发生，**未入台账**；但该次早于余额基线读数（15.95），**不在差额区间内**；估算量级 <¥0.01 |
| 官方计价规则 | 中文价目页：flash 输入命中 ¥0.02/¥0.04、未命中 ¥1/¥2、输出 ¥4/¥8；v4-pro 输入命中 ¥0.15/¥0.30、未命中 ¥4.5/¥9.0、输出 ¥13.5/¥27.0（每 1M tokens，空闲/高峰） |
| 峰谷判断 | 高峰=**北京时间周一至周五 9:00-12:00、14:00-18:00**；本会话 49 次调用均在 **10:18–11:17 UTC = 北京 18:18–19:17 → 空闲时段**（判定正确；若判反则费用 ×2 = $0.3035） |
| USD/CNY | 本地台账按官方**美元**表计算；账户余额为 **CNY**。英文页 USD 数值 ≈ 中文页 CNY 数值 ÷ 7.1（自洽），但**具体换算率未在客户端可验证** → 归因不确定项 |
| 是否存在未纳入台账的 API 调用 | **发现一条真实漏账通道**：三个 judge 工具（`evidence_signal` / `llm_semantic_judge` / `sufficiency_judge`）用 `router.client.complete(...)` **直连**，绕过 `Router.complete` → 既无费用也无 `LLM_CALL` 事件。**本期该通道未被触发**（`llm_judge_cache` 0 行、无证据可判），但风险真实 → 已修复（见 1.4） |
| 其它可能的 API 调用 | 已全量搜索 `DeepSeekClient(` / `.complete(` / `router.client`：除 agent 主链与上述三个 judge 工具外，仅 `scripts/stage8_demo.py`（脚本，未在本次运行） |

### 1.3 差额为何存在 —— 实测证据

**证据 A：余额结算异步且成批**
```
t(s)  balance(CNY)        窗口内本项目 API 调用数 = 0（仅免费的 /balance 读取）
   0  11.96
  20  11.84  <- -0.12
  90  11.67  <- -0.17
 140  11.17  <- -0.50
 180  11.17
```

**证据 B：单次受控调用的扣费远小于理论值且延迟到账**
```
调用: deepseek-v4-pro, prompt 86,483 tokens(cache miss) + completion 256 (reasoning 256)
官方空闲价理论: ¥0.3926
余额: 调用前 12.00 → 立即 12.00（未变） → 20s 后 11.96（-0.04，仅 0.10x）
```
→ 说明余额**不是逐调用实时扣减**，不能用"某时刻余额差"反推某次调用的真实单价。

**证据 C：会话期间余额下降总量 vs 本地可归因量**

| 口径 | 金额 |
|---|---|
| 余额：15.95 CNY → 11.17 CNY | **-4.78 CNY** |
| 本地台账 A/B/C（49 次 / 218,349 tokens） | $0.1517 ≈ **¥1.08**（按 7.1） |
| 本期诊断性调用（3 次探针 + 2 次受控测量，理论值合计） | ≈ **¥0.46** |
| 合计可归因 | ≈ **¥1.54** |
| **无法归因残余** | ≈ **¥3.24** |

**残余的候选解释（客户端无法进一步区分，故不强行归因）**
1. **同一 API key 被其它调用方使用**：证据 A 显示在"本项目零调用"的窗口里余额仍在下降（3 分钟 ¥0.79）。
2. **更早窗口的费用仍在陆续结算**（结算延迟以分钟计，已在证据 A/B 中直接观测）。
3. **客户端不可观测的计价细节**（USD/CNY 换算率、服务端舍入/阶梯）。

### 1.4 本期修复（对账能力，而非改数字）

| 改动 | 说明 |
|---|---|
| `Router.account_direct_call(model, result, tag)` | 新增：给绕过 `complete()` 的直连调用记账（计入 `spent_usd`/`calls`，返回 cost 与 usage） |
| 三个 judge 工具 | 调用后即 `router.account_direct_call(...)`，并把 `cost_usd` 写入 `llm_judge_cache` 行（此前该列为空） |
| `tests/cost_accounting_test.py`（新增） | **19 项**：计价数学（按当前时段取价）、峰谷边界（北京 9-12/14-18 ↔ UTC）、未知模型不猜价、Schema 修复重试各记一条、预算闸门在发请求前拦截、**台账完整性守卫（client.calls == LLM_CALL 事件数）**、**judge 直连通道记账守卫** |

**判定**：费用对账 **PENDING（机制已解释、金额未完全归因）**。禁止把 PENDING 改成 PASS。

---

## 2. GBK 异常

### 2.1 事实

| 项 | 内容 |
|---|---|
| 观测 | CLI 层一次 `UnicodeDecodeError: 'gbk' codec can't decode byte 0x8c in po…`（消息被截断） |
| 落库情况 | **未进入数据库任何表**（`events`/`tasks` 全库搜索 0 命中）→ 属**CLI 进程级异常**，非任务失败；随后管道正常 settled |
| 本机默认编码 | `locale.getpreferredencoding(False)` = **cp936（GBK）** |
| 风险类别复现 | 用 cp936 解码 UTF-8 中文路径字节确实抛错：`'gbk' codec can't decode byte 0xad in position 9: illegal multibyte sequence`（与观测同类，**具体触发点未复现**） |

### 2.2 排查

- 代码内文本读取：`src/video_studio` 全量扫描 `read_text()`/`open()`，**全部显式 `encoding="utf-8"`**（含 `cli.py`、`memory/repo.py`、`engine._write_manifest`）→ 非文件读取问题。
- 唯一符合"仅 Windows 触发 + 与中文路径/文件名相关"的类别：**`subprocess.run(..., text=True)` 未指定 `encoding=`** → Python 用本地编码解码子进程输出。
- 实测扫描：`src/video_studio` 内共 **15 处** `subprocess(text=True)` 调用，其中 **9 处**（`stage32b/*`：assemble/qc/render；`stage33/*`：asset_render_resolver/executor/subtitle_pipeline）**未指定编码**；Phase 1 已加固的 `ffmpeg_tool.py` 6 处已合规。
- **处置**：15/15 全部补齐 `encoding="utf-8", errors="replace"`（`ffmpeg_tool` 6 处本阶段之前已改，本轮再补 9 处，涉及 6 个文件）。

### 2.3 是否定位

- **风险类别：已定位并消除**（编码缺失 + 中文路径触发 + Windows GBK 默认编码）。
- **该次具体触发的调用点：ROOT_CAUSE_NOT_REPRODUCED**（未落库、未复现；不做伪造归因）。缓解措施：全部 subprocess 显式编码 + 失败时仍抛可诊断 `ToolError`（实测中文路径探测返回 `ToolError(PROBE_FAILED)` 而非 `UnicodeDecodeError`）。

### 2.4 新增回归测试

`tests/subprocess_encoding_test.py`（**6 项**）：
1. 断言本机默认编码为 GBK 族（风险类别成立的前提）
2. 演示 UTF-8 中文路径字节按 GBK 解码必然失败（同类错误可复现）
3. **AST 静态守卫**：`src/video_studio` 内所有 `subprocess(text=True/universal_newlines=True)` **必须**给定 `encoding=`（当前 15/15 通过；新写的漏点会被立刻抓住）
4. 守卫覆盖度 > 0（防止"扫描为空即通过"的假阳性）
5. 运行时：含中文文件名/目录的目标探测不抛 `UnicodeDecodeError`
6. 失败时给出可诊断错误（`ToolError`）

---

## 3. 语义级分镜↔旁白：方案设计（**不实现**）

保留现状：结构化检查（镜头字段完整性、镜头数/时长）作为判定依据；跨模态 2-gram 重叠仅作信息项（实测 2.1%，**不作为判定依据**）。

若后续需要增强，建议按下列次序推进（本期**不实现**）：

- **方案 A（首选，零 API 成本）**：复用已存在的**本地文本嵌入**路径（`src/video_studio/stage31/semantic.py` 已加载本地模型），对每对 (镜头描述+gen_prompt, 旁白段) 计算余弦相似度，输出"最低分的 N 对"供人工复核；阈值只做**告警**不做判定。优点：无外网、无费用、可离线回归；缺点：仅 text-text 相似度，不能证明"画面就是旁白说的那个东西"。
- **方案 B（次选，需 API 预算）**：对每对做一次 LLM 判定（JSON：`aligned|partial|mismatched` + 理由），批处理（一次调用判 5–10 对）以控成本；结果写入既有的 `llm_judge_cache`（含 `cost_usd`，本期已补齐该列），并作为**人工复核队列**而非自动判定。成本量级估算：A 组 10 镜 ≈ 2 次调用（<¥0.01）。
- **方案 C（不建议本期做）**：引入 CLIP 类跨模态模型做图文相似度。需新模型权重（外部依赖/体积），与本阶段"最小"原则冲突。
- **共同前置条件**：需要"镜头 ↔ 旁白段"的**时间对齐关系**（当前 `visual_plan.shots[]` 与 `script.segments[]` 无显式映射，只有顺序与时长）；建议先由 editing 计划落一份 `shot→segment` 映射（加法字段，不改契约），再做语义判定，否则相似度会算错对象。
- **判定口径建议**：语义对齐作为**人工复核提示**，与 G10 域一致性、字幕↔旁白一致性并列；在拿到"人工确认的对齐率"之前，任何自动分数都不得写进 PASS 结论。

---

## 4. 修改文件（Phase 1.1）

| 文件 | 改动 |
|---|---|
| `src/video_studio/llm/router.py` | 新增 `account_direct_call()`（直连调用记账） |
| `src/video_studio/tools/llm_semantic_judge.py` | 直连调用后记账 + `cost_usd` 落缓存行 |
| `src/video_studio/tools/sufficiency_judge.py` | 同上 |
| `src/video_studio/tools/evidence_signal.py` | 同上 |
| `src/video_studio/tools/ffmpeg_tool.py` | （Phase 1 已加固）6 处 subprocess 显式编码 |
| `src/video_studio/stage32b/assemble.py`、`qc.py`、`render.py` | 5 处 subprocess 显式编码 |
| `src/video_studio/stage33/asset_render_resolver.py`、`executor.py`、`subtitle_pipeline.py` | 4 处 subprocess 显式编码 |
| `tests/cost_accounting_test.py` | **新增**（19 项） |
| `tests/subprocess_encoding_test.py` | **新增**（6 项） |
| `docs/regression_2x/*` | 新增对账/测量/诊断脚本（reconcile_cost、cost_hypotheses、cost_probe_measure、cost_probe_large、balance_trajectory、patch_subprocess_encoding、real_small_test、phase1_cost_report 等） |

---

## 5. 全量回归结果

| 回归项 | 结果 |
|---|---|
| 工程测试套件 | **27/27 rc=0**（原 25 套 + 新增 `cost_accounting_test.py`、`subprocess_encoding_test.py`） |
| 三组选材机械 E2E | A `p_306e3f41c959` / B `p_fc0259fe628c` / C `p_a3f07eb5067e`，均 **SETTLED 并出片** |
| 真实 LLM 小测 | **2 次调用 / 5,565 tokens / $0.003037**（`deepseek-flash`, 空闲时段, attempts=1）；**MockLLM 调用 0**；**任务行累计 == 台账合计**（$0.003037）；无失败/阻塞 |
| 本地素材装配 | **PASS**（`material_mode=local_ingest`、候选命中、`material_assembly=SUCCEEDED`、成片 2 流） |
| ffprobe 真实性 | **PASS**（真实 ffprobe，输出 streams/codec/duration/width/height，且与 ffmpeg 非同一二进制） |
| ffmpeg 解码 | 6 个成片（3 组机械 E2E + Phase 1 真实三片）全部 **rc=0** |
| 关键帧抽检 | 已抽出并核对（`%TEMP%\v161audit\p11_A_*.png`） |
| 成本记录测试（新增） | **19/19 通过** |
| Windows subprocess 编码回归（新增） | **6/6 通过**（静态守卫 15/15 调用均带编码） |
| 基线 | `docs/regression_2x/baseline/3.x-phase1.1-baseline.zip`（sha256 `028202759de6181a52967004207ffa6646dd184d0ea6b901f22951d137e0fb7b`，325 文件，**零漂移 MATCH**） |

---

## 6. 判定

| 项 | 状态 |
|---|---|
| LLM 费用对账 | **PENDING（PARTIALLY_EXPLAINED）**：机制查明（异步批量结算 + 客户端不可观测的其它用量），残余 ≈¥3.24 未归因；**未修改数字凑平** |
| GBK 异常 | **类别已定位并消除**（15/15 subprocess 显式编码 + 静态守卫测试）；**该次具体触发点 ROOT_CAUSE_NOT_REPRODUCED** |
| 语义级分镜↔旁白 | **仅方案设计（未实现）**，保留现有结构化检查 |
| 新增测试 | `cost_accounting_test.py` 19/19、`subprocess_encoding_test.py` 6/6 |
| BLOCKED / FAILED | 无 |
