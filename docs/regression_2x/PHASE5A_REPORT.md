# 5.x Phase 5-A 报告：多模态语义验证器（真实视觉模型 CLIP，只读）（2026-09-16）

**授权**：只做 5-A，不进入 5-B/自动换材。要求：① 引入**真实视觉模型**对「旁白/镜头语义 ↔ 实际画面」做**只读**验证；
② 输出 `MATCH / MISMATCH / UNKNOWN` + 可复核证据、置信度、模型/版本、输入指纹；③ **保留 4-B 结果**（不覆盖、不删除），
多模态作为**新增证据层**；④ 不自动改选材/时间轴、不自动 redo、不自动写入生产决策；⑤ **默认关闭**；模型不可用/超时/解析失败
→ `UNKNOWN`/fail-closed，**禁止伪造结果**；⑥ 先用**已有真实真值 S04/S06** 做回归，并各增加至少一组明确的
MATCH / MISMATCH / UNKNOWN 测试；⑦ 验证确定性/可复算性，记录模型、输入、输出与版本；⑧ DB schema、HITL、append-only、
许可闸门、旁白完整性、响度、4-A～4-G 不得退化；⑨ 完整回归 + 5-A baseline + SHA256 + DoD/已知问题；⑩ 完成后 STOP。

**前置校验（基线）**：`docs/regression_2x/baseline/4.x-final-baseline.zip`
sha256 `5992da33fa4cb7ed0ec3767b3137d299def623ca2a645bed18a8cbc50bb9f2c0`（实测一致，5,988,237 字节）。

**结论：PASS**（真实 CLIP 本地权重、离线 CPU；真值回归 S04/S06 双 MISMATCH 且与 4-B 完全一致；4-B 结果原样保留；实现只读、默认关闭、fail-closed、可复算）。

---

## 1. 真实视觉模型与运行方式

| 项 | 值 |
|---|---|
| 模型 | **OpenAI CLIP ViT-B/32**（本地权重，非下载、非伪造） |
| 权重路径 | `models/clip/models--openai--clip-vit-base-patch32/snapshots/3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268`（**不入基线包**，见 §8） |
| 权重指纹 | `model.safetensors` sha256 **`a63082132ba4f97a…`**（全量记录在证据 JSON）；`config.json` sha256 `b575ef3c36f2a057…` |
| 运行环境 | `.venv_tts\Scripts\python.exe`（torch **2.13.0+cpu**、transformers **4.57.6**、Python 3.13.2），**CPU 单线程**，`HF_HUB_OFFLINE=1` |
| 隔离方式 | 主解释器（`C:\python3.13\python.exe`）**无 torch** → 模型推理放在独立 worker（`core/mm_worker_clip.py`）以**子进程**调用；主流程零新增依赖 |
| 输入 | 按镜头窗口 25%/50%/75% 从**成片**抽帧（ffmpeg，固定参数）；文本侧 = 12 个语义域的**英文提示词**（`DOMAIN_PROMPTS`，来源：4-B 词表语义 + 人工书写，**不含被测素材名称**，避免循环论证） |
| 输出 | 逐帧 × 逐域**归一化余弦相似度**（6 位小数）→ 按帧平均 → 逐镜头三态判定 |

## 2. 判定规则（显式、可复算）

1. **期望域**（文本侧）：由该镜头**旁白文本**机械推导 —— 先查 **4-B 词表**（`semantics_v1.json`）的域表面形式；
   无命中时回退 **4-E 检索词典**（`retrieval_synonyms_v1.json`）；两级都无命中 → `UNKNOWN / MM_UNKNOWN_DOMAIN`。
   拉丁形式**按词边界命中**（`car` 不得命中 `Cardboard`；实测该缺陷曾在 S06 旁白触发，**已修正并写成测试** B7）。
2. **画面侧**：CLIP 对 12 个域提示词打分 → 每域取提示词均值 → **画面最像的域**。
3. **三态**：`expected_sim ≥ min_sim(0.20)` 且领先最强其它域 `≥ margin(0.02)` → **MATCH**；
   最强其它域达到下限且反超 `≥ margin` → **MISMATCH**；其余 → **UNKNOWN**（`MM_LOW_SIGNAL` / `MM_AMBIGUOUS`）。
4. 阈值可在 `tools.multimodal` 覆盖（非法值回退默认，**不放松**）。

## 3. 真值回归（授权第 6 项，**核心**）

在**4-B 真值钉定的冻结产物** `a_2ed5f41d6b58`（3-A 时点成片：S04/S06 是鲨鱼照）上，两套独立证据层的结果：

| 镜头 | 4-B（既有，类别式规则） | **多模态（CLIP 像素级）** | 期望域 | 期望相似度 | 画面最像的域 | Δ |
|---|---|---|---|---|---|---|
| S01 | MATCH（R4） | MATCH | xr_device | 0.2897 | xr_device(0.2897) | +0.0597 |
| S02 | MATCH（R4） | MATCH | xr_device | 0.2775 | xr_device(0.2775) | +0.0893 |
| S03 | MATCH（R4） | MATCH | xr_device | 0.2409 | xr_device(0.2409) | +0.0355 |
| **S04** | **MISMATCH**（`R3_DOMAIN_DISJOINT`） | **MISMATCH** | xr_device | 0.1852 | **wildlife(0.2426)** | **−0.0574** |
| S05 | MATCH（R4） | MATCH | xr_device | 0.2855 | xr_device(0.2855) | +0.0679 |
| **S06** | **MISMATCH**（`R2_SENSE_CONFLICT`） | **MISMATCH** | xr_device | 0.2039 | **wildlife(0.2420)** | **−0.0381** |
| **一致率** | — | — | — | **6/6 判定方向完全一致** | | |

→ **真值回归通过**：多模态层在真实冻结产物上独立复现了 4-B 的 S04/S06 `MISMATCH`。

**当前成片**（4-C 修复后的 v5 `a_e369526c2f47`）：4-B `MATCH=6`；多模态 **MATCH=5 / UNKNOWN=1**（S05 Δ=0.0175 < 0.02 → `MM_AMBIGUOUS`）。
两个方向一致（**MISMATCH=0**），多模态层**更保守**（把边际不足的镜头记为 UNKNOWN 而不是硬判）。

## 4. 明确的 MATCH / MISMATCH / UNKNOWN 测试（授权第 6 项）

| 类型 | 用例 | 结果 |
|---|---|---|
| **MATCH** | 当前成片 S01（VR 头显画面 ↔ 旁白讲 Quest 3/PSVR2/PICO 4 外观） | `MATCH`，Δ=+0.0597，置信 HIGH（测试 C6） |
| **MISMATCH** | 冻结产物 S04/S06（鲨鱼照 ↔ 旁白讲 VR 佩戴/边界） | `MISMATCH`，Δ=−0.0574 / −0.0381（测试 C2/C3） |
| **UNKNOWN** | 当前成片 S05（"戴眼镜的人怎么办…" ↔ 画面更像 xr_device 但边际 0.0175 < 0.02） | `UNKNOWN / MM_AMBIGUOUS`（测试 C7） |
| **UNKNOWN（fail-closed）** | 模型目录不存在 / worker 解释器不存在 / 无帧 / 空作业 | `MM_MODEL_MISSING` / `MM_PYTHON_MISSING` / `MM_NO_FRAMES` / `MM_EMPTY_JOB`，**全部镜头 UNKNOWN**（测试 D1–D4） |

## 5. 确定性、可复算与记录（授权第 2/7 项）

| 项 | 证据 |
|---|---|
| 确定性 | 同一批帧两次推理 → 报告**逐字节一致**（测试 E1）；CLI 两次运行判定与相似度完全一致（E3，剔除路径字段后逐字节一致） |
| 抽帧可复算 | 固定时间点 → 帧 sha256 稳定（E2） |
| 模型/版本 | `model.snapshot` / `architecture` / `config_sha256` / `weights_sha256`；`versions{torch, transformers, python, device=cpu, torch_threads=1, hf_offline=1}`（测试 H1） |
| 输入指纹 | `render_output`/`script_output` 的 artifact_id + sha256、**成片 sha256**、**逐帧 sha256**、**旁白 sha256**（测试 H2） |
| 输出证据 | 逐镜头：期望域 + 来源（4-B/4-E）+ 命中词、12 域相似度排序、top-k、Δ、置信度、判定依据文本 |

## 6. 只读与"不覆盖 4-B"（授权第 3/4 项）

- **只读**：数据库以 `file:…?mode=ro` 打开；抽帧写系统临时目录；**不写库、不写任何生产产物**、
  不建任务、不改选材/时间轴/旁白/BGM、不触发 redo（报告 `policy` 显式声明）。
- **不覆盖 4-B**：4-B（`core/semantics.py` + `semantics_v1.json`）**未被修改**（词表 sha256 前缀仍 `083e8d55c9899706`），
  真值仍钉 `a_2ed5f41d6b58`；多模态报告声明 `overwrites_4b_results=false`，两套结论在证据里**并列保存**（§3 表格）。
- 静态证明：多模态层源码不含写库 SQL / `write_artifact` / `set_task_status` / `run_cycle` / `build_engine`，
  也不调用 4-B 的判定函数（测试 G2）。
- 只读实测：全部运行（含 3 次 CLIP 推理 + 2 次 CLI）之后，真实 DB **字节未变**、五张表行数未变、
  项目 **74 个文件（含 5 个成片）逐字节未变**（测试 F1/F2 与证据 §确定性与只读）。

## 7. 默认关闭与命令行（授权第 5 项）

- 配置 `tools.multimodal`：**缺省不存在** → `enabled=false`（`mm_settings()` 返回 `_source=default(disabled)`）；
  管线（plan/run/redo）**从不调用**本模块，只能由人工显式执行只读命令：
  ```powershell
  python run.py multimodal-check <project_id> [--json] [--artifact <render_output_id>] [--out <path>]
  ```
- 该命令与 `report`/`metrics`/`semantic-check`/`rhythm` 同列：**不经过 `build_engine()`**，无副作用。
- fail-closed 一览：`MM_DISABLED`、`MM_MODEL_MISSING`、`MM_PYTHON_MISSING`、`MM_BACKEND_MISSING`、
  `MM_WORKER_FAILED`、`MM_TIMEOUT`、`MM_PARSE_FAILED`、`MM_EMPTY_JOB`、`MM_NO_FRAMES`、`MM_NO_NARRATION`、
  `MM_UNKNOWN_DOMAIN`、`MM_LOW_SIGNAL`、`MM_AMBIGUOUS` —— **任一出现都只记 UNKNOWN，绝不产出 MATCH/MISMATCH**。

## 8. 变更文件与影响面

| # | 文件 | 类型 | 影响面 |
|---|---|---|---|
| 1 | `src/video_studio/core/multimodal.py` | **新增** | 配置读取（默认关闭）、期望域推导（4-B 主 / 4-E 回退，词边界）、抽帧计划、三态判定规则、worker 调用与 fail-closed、报告组装 |
| 2 | `src/video_studio/core/mm_worker_clip.py` | **新增** | 真实 CLIP worker（离线 CPU 单线程；只返回相似度与版本，不编造结果） |
| 3 | `src/video_studio/ops/multimodal.py` | **新增**（只读） | 读库（`mode=ro`）→ 抽帧 → 调用 → 人读/JSON 报告 |
| 4 | `tests/multimodal_test.py` | **新增** | 5-A 单测 **34/34**（A–H 八组） |
| 5 | `docs/regression_2x/phase5a_evidence.py` | **新增**（docs，不入基线） | 证据收集（两版成片 + 4-B 并列对照 + 确定性/只读/fail-closed） |
| 6 | `src/video_studio/cli.py` | 修改（**加法**） | 新增只读子命令 `multimodal-check` |

**未改动**：`db/schema.py`（无表/列变更）、`core/semantics.py` + `semantics_v1.json`（**4-B 原样**）、
`core/materials.py`、`core/narration.py`、`core/audio.py`、`core/supply.py`、`core/retrieval_quality.py`、
`core/bgm.py`、`core/rhythm.py`、`config/config.json`（`tools.multimodal` **未写入默认配置**）。

**模型权重说明（如实登记）**：CLIP 权重在 `models/` 下，按基线口径 `models/` **不入 ZIP**（体积 + 属外部工件）；
因此报告以 **sha256** 钉定模型版本（`a63082132ba4f97a…`），任何人可用同目录权重复算。

## 9. 回归（授权第 8/9 项）

| 项 | 结果 |
|---|---|
| 全部套件 | `run_all_suites.py` → **42 total / 42 rc=0 / FAILED: []**（41 + 新增 `multimodal_test` **34/34**） |
| 回归批次 | `phase3a_regression_batch.py` → **24/24 as_expected（非预期 0）** |
| 3-A / 3-B | 3-A **16/16 PASS**；3-B **32/32** + 失败路径 **12/12** |
| 4-A / 4-B | **18/18** / **29/29**（4-B 真值仍钉 `a_2ed5f41d6b58`） |
| 4-C / 4-D | **18/18**（版本链仍 v5）/ **55/55**（八路径 fail-closed 8/8） |
| 4-E / 4-F / 4-G | **35/35** / **48/48** / **34/34** |
| `provider=none` | `config/config.json` 与基线 manifest 一致；未新增 provider；BGM/检索/缓存默认值未变 |
| 网络 PENDING | 两项 Wikimedia 真实网络用例**状态与期望值未改写**（本轮实测通过仅作记录） |

## 10. 新 baseline、DoD 与已知问题

| 项 | 值 |
|---|---|
| 标签 | `5.x-phase5a-baseline` |
| ZIP | `docs/regression_2x/baseline/5.x-phase5a-baseline.zip`（6,011,955 字节） |
| **zip sha256** | **`1f6bb1062dc7a49570cc298992fd6d99a5579cf387c53c9b0d2aa8c1d8232bac`** |
| 文件数 / 源码字节 | **364 文件 / 7,888,961 字节**（`src/ config/ tests/ scripts/` + 根文件，**排除 `docs/` 与 `models/`**） |
| manifest | `baseline/baseline_manifest_5.x-phase5a-baseline.json`（逐文件 sha256 由 ZIP 内字节重算） |
| 零漂移校验 | `verify_baseline.py 5.x-phase5a-baseline` → **MATCH**（zip 哈希一致、清单 == ZIP 条目、0 缺失、0 漂移） |
| 断点快照 | `snapshots/5.x-phase5a-20260916.{zip,db,json}`（DB sha256 `67ecfdb3e6f683cf…`，17,272,832 字节） |
| 上一冻结基线（未动） | `4.x-final-baseline.zip` sha256 `5992da33…f2c0` |
| 相对上一基线（`baseline_delta.py` 实测） | **代码 修改 1 / 新增 4 / 删除 0**：改 `cli.py`（新增只读子命令）；增 `core/multimodal.py`、`core/mm_worker_clip.py`、`ops/multimodal.py`、`tests/multimodal_test.py`；另 `CHANGELOG.md`/`STATUS.md` 两处文档登记。`config/config.json` 与 DB schema **未变** |
| 回归批次 | `phase3a_regression_batch.py` → **24 项全部 rc=0，非预期结果 = 0** |
| 模型工件（不入包） | `models/clip/…/clip-vit-base-patch32`：`model.safetensors` sha256 `a63082132ba4f97a…`、`config.json` sha256 `b575ef3c36f2a057…`（以 sha256 钉定版本，可用同目录权重复算） |

## 11. 未做与已知限制（如实登记）

1. **未做自动换材/自动改选材/自动 redo**（授权明确禁止；5-B 未进入）——多模态只产出证据与建议。
2. **CLIP 文本塔只支持英文**：期望域由**词表机械推导**（4-B 主 / 4-E 回退），未接入机器翻译或 LLM；
   旁白若完全不含词表命中词 → `UNKNOWN / MM_UNKNOWN_DOMAIN`（**不猜**）。
3. **域级粒度**：判定回答"画面最像的**语义域**是否就是旁白期望的域"，不判断"这张图是否最佳/是否专业级"。
4. **阈值为工程默认值**（`min_sim=0.20`、`margin=0.02`，每镜头 3 帧）：边际接近的镜头会如实记 UNKNOWN
   （当前成片 S05 即如此）。
5. **模型权重不在基线包内**（`models/` 排除）：复算需要本地存在同一目录（sha256 已钉定）。
6. **未写库**：结论不落库（新增 artifact 类型未授权）；报告只在命令行/`--out` 输出。

## 12. 冻结结果

冻结基线的完整字段（ZIP / sha256 / 文件数 / manifest / 零漂移校验 / 快照 / 变更清单 / 模型工件指纹）
见 **§10 表格**；核心值：`5.x-phase5a-baseline.zip` = **364 文件 / 7,888,961 字节 /
zip sha256 `1f6bb1062dc7a49570cc298992fd6d99a5579cf387c53c9b0d2aa8c1d8232bac`**，
`verify_baseline.py 5.x-phase5a-baseline` → **MATCH**（0 缺失、0 漂移）。

**停止点**：按授权完成 5-A 即 **STOP**，不进入 5-B。
