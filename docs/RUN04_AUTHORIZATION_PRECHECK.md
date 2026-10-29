# RUN04 Production Authorization Precheck

- 日期: 2026-09-10 · 性质: 只读授权前检查（零代码修改、零生产 Render、零 Retrieval/CV2 调用）
- 对象: `output/run04/`（orchestrator_core.py + run04_render_orchestrated.py + manifest + exec 产物）
- 结论: **10/10 检查 PASS——具备授权条件；授权开关为"双钥互锁"（见 C），当前代码状态下生产物理上不可启动**

## A. Authorization Precheck（10/10）

| # | 检查 | 结果 | 证据 |
|---|---|---|---|
| 1 | 授权开关唯一且 fail-closed | **PASS（双钥互锁，比单开关更严）** | 开关只存在于 manifest 一处字段；但 preflight_v2:73 要求它 `is False`——仅翻转为 True 会使 preflight FAIL → STOP。授权 = manifest 翻转 **且** preflight 互锁显式放行（两次独立、可审计的动作）。无任何单点误触可启动生产 |
| 2 | 无其他绕过面 | **PASS** | core/entry 中 **零** `subprocess`/`ffmpeg`/`vision_call`/`os.environ`（grep 实证）——渲染执行器物理不存在；CLI 仅 `--exec-id`；`core.run(manifest_override)` 为测试参数且未暴露于 CLI，即使 override 翻转也会被 preflight 互锁停下 |
| 3 | VIZ 与生产授权分别 fail-closed | **PASS** | 两枚独立开关：`production_run_authorized`（preflight:73 + render_plan:276，`is True` 严格身份比较）与 `production_viz_rollout`（preflight:76 + plan_viz_guard:122）。互不引用：翻生产不开 VIZ，开 VIZ 不启生产；各自同样需要 preflight 放行 |
| 4 | 未授权只产 DEFERRED plan | **PASS** | render_plan.mode 仅在 `is True` 时为 PRODUCTION_READY；plan 只含 clip 规格（路径/布局/角标/旁白），**无任何 ffmpeg 命令**；无渲染执行器链接 |
| 5 | 全链可持久化可追溯 | **PASS** | 正式 exec 11 件全落盘：preflight/gate(433)/namespace(433)/assignment_policy/prerender/crop(101)/ledger(101)+rows/render_plan(101 specs)/shot_provenance(101 全链)/qa_summary + run04/qa/latest.json |
| 6 | exec 隔离覆盖全部中间产物 | **PASS** | 全部 JSON 产物在 `exec/<id>/`；run04 根目录无散落文件；重复 exec_id 拒绝；影子模式无 ffmpeg 副产物；唯一跨 exec 文件 = qa/latest.json（设计上的指针）。注：授权后 render 执行器必须把 clips/母片也写进 exec 目录（已列入 D 计划） |
| 7 | 授权后仍不读实验命名空间 | **PASS** | namespace 判定代码不读取任何授权标志——blocked_markers 恒生效；allowed 仅=注册表资产命名空间（run03/asset_cache）；G8 的 allow_registry 在编排配置中恒为空；T2/T9 实证 |
| 8 | 历史 render_v3 与 Run01–03 只读 | **PASS** | run03 四脚本 mtime 均早于本阶段（render_v3 09-10 16:21 / 其余 09-09）；四条母片 + run03 assignment 哈希复验不变（ff119fcd/ad52a0c0/871489f9/7e148585/b220eeb8）；编排器对它们的全部操作为读 |
| 9 | T1–T10+R1–R8 可作固定回归套件 | **PASS（附条件）** | 套件可重复执行（本阶段已跑 3+ 次）；条件：授权后每次生产 Run 必须先跑全套并归档结果到 exec QA（列入 D 计划第 1 步） |
| 10 | 人工确认条件清单 | **见 B/C** | 授权签核 + 互锁放行 + 渲染执行器交付 + 首母片人工 QA |

## B. Remaining Blockers（生产授权前必须闭合）

| # | 阻塞项 | 性质 |
|---|---|---|
| BLK-1 | **渲染执行器未实现**：编排器止于 render_plan（按本轮授权边界）；授权后需交付消费 render_plan 的执行器（clips→concat→字幕烧录→母片，全部写 exec 目录）+ T4/T5 执行级测试 | 代码（需授权的实施变更） |
| BLK-2 | **preflight 互锁放行**：'production_run_not_authorized' 检查需在同一次授权变更中改为校验"授权记录完整性"（建议 manifest 增加 authorized_by / authorized_at / authorization_ref，preflight 验证其存在） | 代码（与 BLK-1 同一变更集） |
| BLK-3 | **人工签核**：manifest 翻转须记录授权人/时间/依据 | 流程 |
| BLK-4 | 首母片人工 QA 清单（字幕抽检/黑帧扫描/av delta/逐 shot provenance 抽查） | 流程 |
| BLK-5 | 外部可选项：CV2 额度（裁切实判）、人工评分者 | 外部 |

## C. Exact Production Authorization Switch

```
文件:   output/run04/run04_manifest.json
字段:   production_run_authorized: false → true   （代码校验为严格 `is True`，真值字符串无效）
同时:   preflight_v2 的 'production_run_not_authorized' 检查在同一授权变更集中
        改为校验授权记录（authorized_by/authorized_at/authorization_ref 存在且非空）
效果:   仅 render_plan_stage 模式翻转为 PRODUCTION_READY；VIZ 守卫、命名空间、
        各确定性门、QA 行为全部不变
无其他: 无环境变量、无 CLI 参数、无第二入口；测试参数 manifest_override 不暴露于 CLI
```

## D. 授权后第一次 Run 的执行计划

1. 变更集（一次授权内）：BLK-1 渲染执行器 + BLK-2 互锁放行 + BLK-3 manifest 签核；执行 T1–T10 + R1–R8 + 模块单测全绿
2. `python run04_render_orchestrated.py --exec-id RUN04_PROD_<id>`：
   - Preflight-v2 全 PASS（含新授权校验）
   - 冻结输入哈希核验 → Candidate Gate（命名空间+完整性）→ 复用 Policy → Pre-render Gate → Crop/Layout（消费 G3 强制 contain）→ Crop Recheck
   - 渲染执行器：逐 clip（cover/contain 按计划、FALLBACK 角标、BLANK 卡片）写 `exec/<id>/clips/` → 分部 concat → 字幕烧录 → 母片 `final_long_<exec_id>.mp4`
3. 持久 QA：av delta / 黑帧与纯色帧扫描 / 字幕 presence / ok_all / 最终 assignment 模式复算 / provenance 101/101 → `exec/<id>/qa_summary.json` + `run04/qa/latest.json`
4. 人工母片 QA（BLK-4）→ 通过后方可对外；报告 `docs/RUN04_PRODUCTION_REPORT.md`

## E. Rollback / STOP 条件

| 触发 | 动作 |
|---|---|
| Preflight 任一 FAIL（含注册表哈希漂移、冻结指纹变化、母片哈希意外） | STOP 于输入加载前 |
| 拍数 ≠ 101 / TTS 缺失 / plan 含 VIZ 意图 | STOP（T5/T6） |
| Policy 出现任何违规（60s/借用上限/内容>2）或全片模式非零 | STOP——视为 policy/实现不一致 |
| Pre-render 任一 BLOCK | STOP（policy/gate 不一致） |
| 单拍 clip 渲染失败 | 整 exec STOP，不写母片（无部分成品） |
| BLANK_CARD > 0 | 不阻断但母片接受前必须人工确认空位拍 |
| QA：av_delta>0.5s 或黑帧>0 或字幕 presence<95% | 母片标记 UNUSABLE，禁止发布 |
| 任何实验标记命中 / ns_leakage>0 | STOP + 事件记录 |
| QA 中 retrieval/cv2 调用数 ≠ 0 | STOP（成本与冻结违规） |
| **回滚** | exec 目录自包含——删除该 exec 目录即完全回滚；母片仅存在于 exec 命名空间，永不覆写 Run01–03 |

```
AUTHORIZATION PRECHECK = PASS (10/10)
可授权 = 是（前提：BLK-1 渲染执行器 + BLK-2 互锁放行 + BLK-3 签核，同一授权变更集）
本轮零修改 · 零生产 Render · 零 Retrieval/CV2 调用
STOP——等待授权
```
