# 2.x 基线回归：三组测试输入（逐字保存，训练/验收证据）

来源：用户 2026-09-13 指令原文。

## A. 简单选材
```
做一期介绍黑洞的短视频。
```

## B. 复杂选材
```
做一期介绍脑机接口发展现状的视频，要求区分真实技术、实验阶段和未来推测。
```

## C. 带约束选材
```
制作一条60秒科技科普视频，面向普通观众，节奏适中，包含开头钩子、分镜、旁白、字幕和结尾总结。
```

## 回归口径（用户硬标准）
输入选材 → 生成视频规划 → 生成分镜与素材需求 → 执行视频流程 → **成功输出视频**。
只验证文本/分镜/规划不算通过；必须真实产出视频文件。

## D. 3.x Phase 2-A/2-B 真实素材装配选材（2026-09-13）
```
做一期介绍 VR 与脑机接口设备长什么样的短视频。
```
配套素材（3 张本地真图，**人工逐张看过内容后按所见命名**，先 `ingest` 再 `plan`）：
| ingest 名称 | 来源文件 | sha256 |
|---|---|---|
| `VR头显_镜片特写.jpg` | `output/run03/asset_cache/files/r3_S01-B01_3.img.jpg` | `3bd63424e48866db95efb058faeb3f3dce208…`（完整见 `logs/phase2_evidence.md`） |
| `VR头显_手柄_笔记本.jpg` | `output/run03/asset_cache/files/r3_S01-B01_0.img.jpg` | `f304650dbc24803c…` |
| `脑电头环_假人头模_陈列柜.jpg` | `output/run03/asset_cache/files/r3_S01-B02_1.img.jpg` | `3af507571a33f029…` |

驱动：`python docs/regression_2x/phase2_accept.py`（支持 `--resume/--redo/--verify`）；
证据汇总：`python docs/regression_2x/phase2_evidence.py <项目ID>`。
