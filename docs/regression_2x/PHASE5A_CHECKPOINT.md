# 5.x Phase 5-A 完成与交接（2026-09-16）

> **状态：5-A 多模态语义验证器已完成并冻结基线**。结论看 `PHASE5A_REPORT.md`，进度看 `STATUS.md`。
> **只读、默认关闭、fail-closed；未进入 5-B（自动换材）。**

## 0. 一句话结论

引入**真实视觉模型 CLIP ViT-B/32**（本地权重、离线 CPU、确定性）对「旁白期望语义域 ↔ 成片实际画面」做**只读**三态验证；
在 4-B 真值钉定的冻结产物上**独立复现 S04/S06 双 MISMATCH**（与 4-B 6/6 一致）；4-B 结果原样保留、不覆盖不删除；
模型/环境不可用时一律 `UNKNOWN`（fail-closed，禁止伪造）。

## 1. 冻结产物（可直接引用）

| 项 | 值 |
|---|---|
| 前置基线 | `4.x-final-baseline.zip` sha256 `5992da33fa4cb7ed0ec3767b3137d299def623ca2a645bed18a8cbc50bb9f2c0` |
| **新基线** | `5.x-phase5a-baseline`：364 文件 / 7,888,961 字节 / zip sha256 `1f6bb1062dc7a49570cc298992fd6d99a5579cf387c53c9b0d2aa8c1d8232bac`（`verify_baseline.py` **MATCH**） |
| manifest | `baseline/baseline_manifest_5.x-phase5a-baseline.json` |
| 快照（非基线） | `snapshots/5.x-phase5a-20260916.{zip,db,json}`（DB sha256 `67ecfdb3e6f683cf…`） |
| 证据 | `logs/phase5a_multimodal_evidence.json`、`logs/phase5a_evidence_summary.txt` |
| 变更清单 | `logs/phase5a_change_list.json`（代码 修改 1 / 新增 4 / 删除 0） |
| 模型指纹（不入包） | `model.safetensors` sha256 `a63082132ba4f97a…`、`config.json` sha256 `b575ef3c36f2a057…`、快照 `3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268` |

## 2. 交接要点（继续时先看这里）

1. **只读不可破**：`ops/multimodal.py` 只能走 `readonly_connection`；不要给它加写库/写产物/派发任务的能力
   （`tests/multimodal_test.py` G2 做静态检查：无写库 SQL / `write_artifact` / `set_task_status` / `run_cycle` / `build_engine`）。
2. **4-B 不得被覆盖**：多模态是**新增证据层**；`core/semantics.py` 与 `semantics_v1.json` 未改，真值仍钉 `a_2ed5f41d6b58`。
3. **阈值与规则改动要同步**：`min_sim=0.20`、`margin=0.02`、每镜头 3 帧；改动会改变 UNKNOWN/MISMATCH 比例，
   必须同步更新 `PHASE5A_REPORT.md`、证据 JSON 与测试断言。
4. **模型/环境**：CLIP 权重在 `models/clip/…`（**不入基线包**），运行时用 `.venv_tts\Scripts\python.exe`
   （torch 2.13.0+cpu / transformers 4.57.6）；缺失即 fail-closed → UNKNOWN（不影响既有行为）。
5. **期望域推导**：4-B 词表为主、4-E 检索词典回退；拉丁形式**按词边界**命中（`car`⊄`Cardboard`）。
6. 既有阶段开关默认值均未变：BGM 默认关闭、检索 v2 默认关闭、供给缓存默认关闭；`provider=none` 仍为默认。
7. 两项 Wikimedia 真实网络用例仍记 `PENDING（环境）`（本轮实测通过，**状态不得改写**）。
8. 进入 5-B（自动换材）或任何自动改片能力：**需要新的授权**。

## 3. 复现命令（离线，约 1–3 分钟）

```powershell
cd C:\mp4agent\video-studio
C:\python3.13\python.exe run.py multimodal-check p_f4b466a4a024                      # 当前成片（v5）
C:\python3.13\python.exe run.py multimodal-check p_f4b466a4a024 --artifact a_2ed5f41d6b58  # 4-B 真值冻结产物
C:\python3.13\python.exe tests\multimodal_test.py                                    # 34/34
C:\python3.13\python.exe docs\regression_2x\phase5a_evidence.py                       # 证据（两版成片 + 4-B 对照）
C:\python3.13\python.exe docs\regression_2x\run_all_suites.py                         # 42/42
C:\python3.13\python.exe docs\regression_2x\verify_baseline.py 5.x-phase5a-baseline
```
