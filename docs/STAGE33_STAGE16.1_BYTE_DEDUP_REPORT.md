# Stage 16.1:同字节假切换修复 报告

> 实现:测试侧 harness fork(run_15_final.py → run_161_final.py)。零下载(Stage 14 缓存);素材指派账本(material)零改动;bridge_sync 4 拍原样保留(Stage 15.1 设计);M3 口径、Stage 14 运动规则集、字幕/TTS 零触碰。

## 1. 根因更正(重要,如实归因)

Stage 16 将 P1 归因为"URL 级去重盲区"。**16.1 的实施证据表明真正根因是陈旧缓存**:

- run_14 首跑(v1 前向碰撞版)为每个兜底拍下载了 `t14_{拍}` 文件;重跑(v2)时 `acquire_asset` 按 key 命中旧缓存直接复用——**约 10 个兜底拍渲染的是 run-1 的图(v1 前向碰撞对象),而非 v2 账本记录的 origin 图**。
- 实证:`MD5(t14_S16_B02)=4041a9deda == MD5(t14_S17_B01)`(run-1 把 S16-B02 指给 S17-B01),而 v2 账本 origin S15-B01 的真图 `MD5(t14_S15_B01)=9b1e61be6e ≠ 4041a9deda`。10 处 P1 对与 run-1 链列表逐一吻合。
- 结论:Stage 14 v2 策略本身的指派是对的,**渲染产物与 provenance 脱节**。P1 的"URL 盲区"表述予以更正;渲染一致性缺口为真实问题。

## 2. 16.1 修复内容(两层,均为测试侧)

1. **按 origin 键取图**:兜底渲染改用 `t14_{origin_beat}` 缓存键 → 渲染像素与 provenance 严格一致;
2. **兜底指派 v3**:`blocked()` 在 URL 双侧窗口之上增加 **content-hash(MD5)双侧窗口**(前向窗口含 +1/+2 拍素材属主的字节哈希)——34 个兜底全部以 `fallback_nearest_distinct_byte_safe` 重验通过(v3 指派与 v2 账本一致,`changed_vs_v2=0`,无强行替换、无 correspondence 损害);
3. **P2(≥3 连 fallback run)**:run 长度由账本结构决定(EMPTY 拍分布),在不新增素材源约束下不可缩短;run 内相邻字节相异已由 v3 窗口保证——如实记录,未强行处理。

## 3. 前后对照

| 指标 | 15.1(前) | 16.1(后) | 验收 |
|---|---|---|---|
| 非预期相邻同字节对 | **10** | **0** | =0 ✅ |
| bridge_sync 相邻对(设计内,标记) | 2 | 2(同 URL,`bridge_sync`) | 已标记 ✅ |
| 渲染像素 ↔ provenance 一致性 | 10 槽脱节 | **一致** | 修复 ✅ |
| CORRESPONDING | 56 / 309.26s / 60.86% | **不变** | ≥60.86% ✅ |
| 成片时长 / A-V | 508.25s / +0.10s | 508.25s / **+0.10s** | ≤±0.3s ✅ |
| 运动分布 | PAN_LR 28 / PAN_RL 16 / SN 31 / ZI 14 / ZO 5 | **相同**(指派未变,零重推导) | 不回退 ✅ |
| fallback run 直方图 | {4:1, 3:2, 2:7, 1:10} | 相同(run 长度结构性固定,如实保留) | 如实记录 |
| 黑帧/绿幕/纯色/异常静帧/音频空洞 | 0 | **0**(`stage161_verify.json`,94 段逐段) | =0 ✅ |

成片:`stage16_audit/render_161/final_long.mp4`(508.25s,90/90,逐段时长对账通过)。

## 4. Provenance(`stage161_assignments.json` / `stage161_metrics.json` / `stage161_verify.json`)

- 34 个兜底逐条:`v2_origin / v3_origin / changed_vs_v2 / content_hash / source_url / reuse_reason`;
- 2 条 bridge_sync 对显式标记(设计内同图,Stage 15.1 授权);
- 运动重推导列表为空(指派未变,Stage 14 运动原样保留)。

## 5. 结论

10 处假切换清零;渲染产物与指派账本首次严格一致;correspondence、Stage 14/15 全部指标、工程审计六项均无回退。修复未动任何冻结模块、未新增素材、未调整权重。

```
STAGE16.1 = PASS · STOP
假切换 10→0 · 根因=陈旧缓存(已更正归因) · correspondence 60.86% 不变 · bridge_sync 2 对设计内保留 · 工程审计全零 · A/V +0.10s
STOP——等待下一步授权
```
