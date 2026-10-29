"""CLI 入口（V1）：创建项目 / 运行调度 / 查看状态 / 人工审批。

用法：
  python run.py init "目标描述" [--name 名字]
  python run.py run <project_id> [--limit N]
  python run.py status <project_id>
  python run.py approve <task_id> approve|reject|modify [--comment 备注]
  python run.py plan <project_id>      # 按标准管线一次性创建全部任务
  python run.py recover                # 崩溃恢复：中断任务回队
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]   # video-studio/src -> video-studio
sys.path.insert(0, str(ROOT / "src"))


def load_config(path: str | None = None) -> dict:
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    cfg = ROOT / "config" / "config.json"
    if cfg.exists():
        return json.loads(cfg.read_text(encoding="utf-8"))
    return json.loads((ROOT / "config" / "config.example.json").read_text(encoding="utf-8"))


def _force_utf8_io() -> None:
    """把所有 CLI 输出固定为 UTF-8。

    历史问题（Phase 3-C 实测）：Windows 上管道/重定向时 Python 用 locale 编码（本机 cp936）
    输出中文 → 外部按 UTF-8 读取会乱码/解码失败（`run.py report` 的输出尤其明显）。
    与 Phase 1.1 的 subprocess 编码收口同一类问题，这里把 CLI 自身的 stdout/stderr 一并收口。
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


def build_engine(config: dict):
    from video_studio.db.schema import Database
    from video_studio.core.engine import Engine
    from video_studio.llm.router import DeepSeekClient, MockLLM, Router

    # 导入全部 agent 以注册（22 个专职角色）
    import video_studio.agents.orchestrator.agent  # noqa: F401
    import video_studio.agents.pm.agent  # noqa: F401
    import video_studio.agents.topic.agent  # noqa: F401
    import video_studio.agents.research.agent  # noqa: F401
    import video_studio.agents.source_verify.agent  # noqa: F401
    import video_studio.agents.structure.agent  # noqa: F401
    import video_studio.agents.script.agent  # noqa: F401
    import video_studio.agents.fact_check.agent  # noqa: F401
    import video_studio.agents.critic.agent  # noqa: F401
    import video_studio.agents.asset.agent  # noqa: F401
    import video_studio.agents.retrieval.agent  # noqa: F401
    import video_studio.agents.visual.agent  # noqa: F401
    import video_studio.agents.editing.agent  # noqa: F401
    import video_studio.agents.voice.agent  # noqa: F401
    import video_studio.agents.audio.agent  # noqa: F401
    import video_studio.agents.subtitle.agent  # noqa: F401
    import video_studio.agents.thumbnail.agent  # noqa: F401
    import video_studio.agents.platform.agent  # noqa: F401
    import video_studio.agents.metadata.agent  # noqa: F401
    import video_studio.agents.compliance.agent  # noqa: F401
    import video_studio.agents.qa.agent  # noqa: F401
    import video_studio.agents.analyst.agent  # noqa: F401
    import video_studio.agents.claim_extractor.agent  # noqa: F401  V2
    import video_studio.agents.evidence.agent  # noqa: F401  V2
    import video_studio.agents.conflict_detector.agent  # noqa: F401  V2
    from video_studio.agents.base import AGENTS

    db = Database(ROOT / "projects" / "video_studio.db")
    llm_cfg = config.get("llm", {})
    if llm_cfg.get("mock"):
        client = MockLLM(llm_cfg["mock"].get("responses", {}), llm_cfg["mock"].get("default", {}))
    else:
        client = DeepSeekClient(llm_cfg.get("deepseek", {}))
    router = Router(llm_cfg, client)
    rules = json.loads((ROOT / "config" / "rules.json").read_text(encoding="utf-8"))
    return Engine(db, router, rules, ROOT / config.get("workspace", {}).get("root", "projects"),
                  config, AGENTS)


def main(argv: list[str] | None = None) -> None:
    _force_utf8_io()          # 管道/重定向下固定 UTF-8（避免 Windows locale=cp936 乱码）
    parser = argparse.ArgumentParser(prog="video-studio", description="AI 视频生产多 Agent 系统 V1")
    parser.add_argument("--config", default=None, help="配置文件路径（默认 config/config.json）")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="创建项目")
    p_init.add_argument("goal")
    p_init.add_argument("--name")

    p_run = sub.add_parser("run", help="推进调度（执行就绪任务）")
    p_run.add_argument("project_id")
    p_run.add_argument("--limit", type=int, default=20)

    p_status = sub.add_parser("status", help="项目状态")
    p_status.add_argument("project_id")

    p_approve = sub.add_parser("approve", help="人工审批")
    p_approve.add_argument("task_id")
    p_approve.add_argument("decision", choices=["approve", "reject", "modify"])
    p_approve.add_argument("--comment", default="")

    p_plan = sub.add_parser("plan", help="按标准管线创建全部任务")
    p_plan.add_argument("project_id")

    p_recover = sub.add_parser("recover", help="崩溃恢复")

    p_redo = sub.add_parser("redo", help="重做任务：以版本+1 重新创建同一任务（回退重做）")
    p_redo.add_argument("task_id")

    # 2026-10-20 人工审稿（梗/人味只能从这里进流程）
    p_srev = sub.add_parser("script-review",
                            help="只读：导出可编辑审稿稿（每段一行 + 字数预算 + 节拍 + 5 问）")
    p_srev.add_argument("project_id")
    p_srev.add_argument("--out", default=None, help="输出路径（默认 <项目>/media/script_review.md）")
    p_srev.add_argument("--json", action="store_true", help="输出 JSON（机器可读，仍为只读）")

    p_sapp = sub.add_parser("script-apply",
                            help="回填审稿稿：校验后写 <项目>/media/script_review.json（不自动重跑）")
    p_sapp.add_argument("project_id")
    p_sapp.add_argument("--file", required=True, help="审稿后的 md 路径")
    p_sapp.add_argument("--checklist", default="",
                        help="审稿 5 问：1/0 串（如 11110）或 key=1,key2=0")
    p_sapp.add_argument("--notes", default="", help="本稿欠账/批注（进审稿台账）")
    p_sapp.add_argument("--allow-drift", action="store_true",
                        help="允许全片字数漂移 >5%（会改变时长/素材窗口/字幕）")
    p_sapp.add_argument("--dry-run", action="store_true", help="只校验，不落盘")

    p_loop = sub.add_parser("loop", help="自动推进：循环 run+approve 直到完成或需要人工")
    p_loop.add_argument("project_id")
    p_loop.add_argument("--auto-approve", action="store_true", help="自动批准全部闸门（演示用；生产应人工审批）")
    p_loop.add_argument("--max-rounds", type=int, default=30)

    p_ingest = sub.add_parser("ingest", help="素材登记：把目录中的媒体文件复制进项目 media/ 并重建索引")
    p_ingest.add_argument("project_id")
    p_ingest.add_argument("source_dir")

    p_claims = sub.add_parser("claims", help="查看项目 Claim 列表（V2 事实核查）")
    p_claims.add_argument("project_id")

    p_claim = sub.add_parser("claim", help="查看单条 Claim：证据/冲突/Skeptic 质疑/核查结论")
    p_claim.add_argument("claim_id")

    p_ac = sub.add_parser("approve-claim", help="人工批准 Claim")
    p_ac.add_argument("claim_id")
    p_ac.add_argument("--comment", default="")

    p_rc = sub.add_parser("reject-claim", help="人工驳回 Claim（重做脚本并重建核查链）")
    p_rc.add_argument("claim_id")
    p_rc.add_argument("--comment", default="")

    p_vc = sub.add_parser("revise-claim", help="人工修订 Claim 表述（重新核查）")
    p_vc.add_argument("claim_id")
    p_vc.add_argument("--text", required=True, help="修订后的表述")
    p_vc.add_argument("--comment", default="")

    # 3.x Phase 3-C：只读运维报告（不修改运行状态、不触发任务）
    p_report = sub.add_parser("report", help="只读项目报告：任务/产物/事件/失败/成本/素材/响度")
    p_report.add_argument("project_id")
    p_report.add_argument("--json", action="store_true", help="输出 JSON（机器可读，仍为只读）")
    p_report.add_argument("--events", type=int, default=8, help="失败事件条数（默认 8）")
    p_report.add_argument("--mm-advisory", default=None, metavar="JUDGE_JSON",
                          help="附加只读多模态质量咨询节（需冻结 Judge JSON 路径；不设则不显示）")

    # 4.x Phase 4-A：只读质量/成本指标（不修改运行状态、不触发任务）
    p_metrics = sub.add_parser("metrics", help="只读质量/成本指标（质量、契约、素材用量、语义核验）")
    p_metrics.add_argument("project_id", nargs="?", default=None, help="省略则配合 --all 汇总全库")
    p_metrics.add_argument("--all", action="store_true", help="汇总全库（含成片的项目）")
    p_metrics.add_argument("--limit", type=int, default=0, help="--all 时只取最近 N 个（0=全部）")
    p_metrics.add_argument("--json", action="store_true", help="输出 JSON（确定性：两次运行逐字节一致）")

    # 4.x Phase 4-B：离线只读三态语义验证器（不写任何状态）
    p_sem = sub.add_parser("semantic-check",
                           help="离线三态语义核验：镜头↔旁白 MATCH/MISMATCH/UNKNOWN（只读）")
    p_sem.add_argument("project_id")
    p_sem.add_argument("--json", action="store_true", help="输出 JSON（含逐镜头信号与规则 ID）")
    p_sem.add_argument("--scenes", action="store_true", help="附逐镜头明细（人读模式）")

    # 4.x Phase 4-C：人审候选替换（只读复核队列 + 记录人工明确选定；不自动改选材）
    p_review = sub.add_parser("review", help="只读复核队列：语义非 MATCH 镜头 + 可选候选池（含许可/验证）")
    p_review.add_argument("project_id")
    p_review.add_argument("--all", action="store_true", help="列出全部镜头（默认只列语义非 MATCH 的）")
    p_review.add_argument("--json", action="store_true", help="输出 JSON（只读）")

    # Phase 9：只读留存评分（机械层 + LLM 评审层）——critic 管事实红线，retention 管留存
    p_ret = sub.add_parser("retention-check",
                           help="只读留存评分：hook/节奏/情绪/CTA（不接入生产链、不改稿）")
    p_ret.add_argument("project_id", nargs="?", help="项目 ID（与 --script 二选一）")
    p_ret.add_argument("--task", default=None, help="指定 task 的 script 产物（默认最新）")
    p_ret.add_argument("--script", default=None, help="独立脚本 JSON 路径（语料回测入口）")
    p_ret.add_argument("--cache", default=None, help="只读 LLM 缓存文件（命中不调用 LLM）")
    p_ret.add_argument("--no-llm", action="store_true", help="只用机械层（零 LLM 调用、零成本）")
    p_ret.add_argument("--samples", type=int, default=3,
                       help="LLM rubric 独立采样次数（默认 3；1 = 单采样，行为与 Phase 9 一致）")
    p_ret.add_argument("--no-timestamp", action="store_true",
                       help="省略 taken_at_utc ⇒ --json 两次运行逐字节一致（可复现）")
    p_ret.add_argument("--json", action="store_true", help="输出 JSON（键排序，确定性）")

    # Phase 10：选题信号快照**人工触发**拉取（单次请求；不访问 DB、不派任务）
    p_fs = sub.add_parser("fetch-signals",
                          help="选题信号：人工触发一次拉取并落盘快照（topic agent 运行期只读）")
    p_fs.add_argument("--provider", choices=["bilibili_popular", "manual"], default=None,
                      help="默认取 config.tools.topic_signals.provider")
    p_fs.add_argument("--manual", default=None, help="manual provider 的本地 JSON 路径")
    p_fs.add_argument("--out", default=None, help="快照输出路径（默认 signals/snapshot_*.json）")
    p_fs.add_argument("--ps", type=int, default=50, help="bilibili_popular 单次请求条目数上限")
    p_fs.add_argument("--json", action="store_true", help="输出 JSON（键排序）")

    # Phase 12：许可数据 join ⇒ 增强覆盖层（只读消费记录；仅写覆盖层文件；原索引零改动）
    p_lo = sub.add_parser("build-license-overlay",
                          help="把系统内已记录的许可声明 join 成增强覆盖层（只读；不推断/不猜测）")
    p_lo.add_argument("--index", default=None, help="P7-2 素材索引路径（默认 logs/asset_index.json）")
    p_lo.add_argument("--db", default=str(ROOT / "projects" / "video_studio.db"))
    p_lo.add_argument("--project-id", default="p_96efdc03e1aa")
    p_lo.add_argument("--project", default=None, help="项目目录（用于定位 media/external/.index.json）")
    p_lo.add_argument("--out", default=None, help="覆盖层输出路径（默认 logs/license_overlay_v1.json）")
    p_lo.add_argument("--json", action="store_true", help="输出 JSON（键排序）")

    # Phase 11：标题/封面候选只读机械校验（长度/震惊体/手法/引用/数字可溯/多样性/首句回声）
    p_tc = sub.add_parser("title-check",
                          help="只读标题校验：长度/震惊体/technique/引用/数字可溯性/多样性/首句回声")
    p_tc.add_argument("--script", required=True,
                      help="脚本 JSON、A/B 日志（内含 script）或 metadata 产物路径")
    p_tc.add_argument("--metadata", default=None, help="可选：另配 metadata 产物以校验候选字段")
    p_tc.add_argument("--json", action="store_true", help="输出 JSON（键排序）")
    p_tc.add_argument("--no-timestamp", action="store_true",
                      help="省略 taken_at_utc ⇒ --json 两次运行逐字节一致")

    p_sel = sub.add_parser("select-candidate",
                           help="记录人工选定的替换候选（写 decisions+changelog；替换生效需再执行 redo）")
    p_sel.add_argument("project_id")
    p_sel.add_argument("--scene", required=True, help="镜头 ID，如 S04")
    p_sel.add_argument("--asset", required=True, help="选定的 asset_id（必须在该镜头候选池中）")
    p_sel.add_argument("--by", required=True, help="人工决策者标识（拒绝无归属决定）")
    p_sel.add_argument("--reason", required=True, help="人工选择理由（拒绝无理由决定）")
    p_sel.add_argument("--dry-run", action="store_true", help="只校验并回显，不写库")

    # 4.x Phase 4-G：只读节奏分析与人工建议（**不自动改时长/时间轴/旁白/素材/BGM**）
    p_rhy = sub.add_parser("rhythm",
                           help="只读节奏分析：镜头时长/旁白段落/覆盖/切换密度/静态画面，输出建议（不执行）")
    p_rhy.add_argument("project_id")
    p_rhy.add_argument("--json", action="store_true", help="输出 JSON（确定性：两次运行逐字节一致）")
    p_rhy.add_argument("--artifact", default=None,
                       help="钉定某个 render_output 产物 artifact_id（默认取最新）")

    # 5.x Phase 5-A：多模态语义验证（真实视觉模型 CLIP，只读；默认关闭，需显式调用本命令）
    p_mm = sub.add_parser("multimodal-check",
                          help="只读多模态语义验证：CLIP 看实际画面 ↔ 旁白期望域，输出 MATCH/MISMATCH/UNKNOWN")
    p_mm.add_argument("project_id")
    p_mm.add_argument("--json", action="store_true", help="输出 JSON（确定性：两次运行逐字节一致）")
    p_mm.add_argument("--artifact", default=None,
                      help="钉定某个 render_output 产物 artifact_id（默认取最新）")
    p_mm.add_argument("--out", default=None, help="把 JSON 报告写到指定路径（默认只打印，不落盘）")
    p_mm.add_argument("--frames-dir", default=None, help="抽帧输出目录（默认系统临时目录）")

    # 5.x Phase 5-B：多模态候选（只生成候选；人工确认仍走 4-C 的 select-candidate + redo）
    p_mmr = sub.add_parser("mm-review",
                           help="只读多模态候选：为 MISMATCH/低置信镜头生成候选（含视觉证据/许可/风险），不自动替换")
    p_mmr.add_argument("project_id")
    p_mmr.add_argument("--json", action="store_true", help="输出 JSON（确定性：两次运行逐字节一致）")
    p_mmr.add_argument("--artifact", default=None,
                       help="钉定某个 render_output 产物 artifact_id（默认取最新）")
    p_mmr.add_argument("--out", default=None, help="把 JSON 报告写到指定路径（默认只打印）")
    p_mmr.add_argument("--frames-dir", default=None, help="抽帧/评分临时目录（默认系统临时目录）")

    # 5.x Phase 5-D：多帧/时序多模态验证（只读平行证据层；不改 5-A/4-B 结果、不换材、不 redo）
    p_mmt = sub.add_parser("mm-temporal",
                           help="只读多帧/时序多模态验证：帧间一致性 + 逐帧投票 → MATCH/MISMATCH/UNKNOWN + 置信度")
    p_mmt.add_argument("project_id")
    p_mmt.add_argument("--json", action="store_true", help="输出 JSON（确定性：两次运行逐字节一致）")
    p_mmt.add_argument("--artifact", default=None,
                       help="钉定某个 render_output 产物 artifact_id（默认取最新）")
    p_mmt.add_argument("--out", default=None, help="把 JSON 报告写到指定路径（默认只打印）")
    p_mmt.add_argument("--frames-dir", default=None, help="抽帧临时目录（默认系统临时目录）")
    p_mmt.add_argument("--no-five-a", action="store_true",
                       help="跳过 5-A 引用副本（省一次 3 帧验证；不影响本层判定）")

    # 5.x Phase 5-E：多模态证据质量校准（只读评估层；不改判定逻辑、不调阈值、不写库）
    p_mmq = sub.add_parser("mm-quality",
                           help="只读证据质量校准：冻结真值集上并列评估 4-B/5-A/5-D + 边界/敏感性/可解释链")
    p_mmq.add_argument("project_id")
    p_mmq.add_argument("--json", action="store_true", help="输出 JSON（确定性）")
    p_mmq.add_argument("--truth-set", default=None, help="真值集路径（默认 tests/fixtures/mm_truth_set_v1.json）")
    p_mmq.add_argument("--out", default=None, help="把 JSON 报告写到指定路径（默认只打印）")
    p_mmq.add_argument("--frames-dir", default=None, help="抽帧/夹具临时目录（默认系统临时目录）")
    p_mmq.add_argument("--no-layers", action="store_true",
                       help="只校验真值集与覆盖度，不跑三层（用于快速自检）")

    # 5.x Phase 5-F：多模态证据 Judge（最终判定；只读、零动作、不调阈值）
    p_mmj = sub.add_parser("mm-judge",
                           help="只读最终判定：4-B/5-A/5-D 三层证据融合 → 最终 MATCH/MISMATCH/UNKNOWN + 理由码 + DoD")
    p_mmj.add_argument("project_id")
    p_mmj.add_argument("--json", action="store_true", help="输出 JSON（确定性）")
    p_mmj.add_argument("--truth-set", default=None, help="冻结真值集路径（默认 tests/fixtures/mm_truth_set_v1.json）")
    p_mmj.add_argument("--judge-truth", default=None, help="Judge 真值覆盖层（默认 tests/fixtures/mm_judge_truth_v1.json）")
    p_mmj.add_argument("--from-calibration", default=None,
                       help="复用既有 5-E 校准报告（只读；缺省则现场重跑三层）")
    p_mmj.add_argument("--out", default=None, help="把 JSON 报告写到指定路径（默认只打印）")
    p_mmj.add_argument("--frames-dir", default=None, help="抽帧/夹具临时目录（默认系统临时目录）")

    # 5.x Final Gate: mm-review-confirm（append-only 人工决策记录；对评估/判定系统只读）
    p_mrc = sub.add_parser("mm-review-confirm",
                           help="append-only 人工决策记录：accept/replace/keep_unknown（只读评估系统；不自动执行）")
    p_mrc.add_argument("project_id")
    p_mrc.add_argument("--decisions", required=True,
                       help="人工决策 JSON 文件路径（数组，每项含 scene_id/case_id/decision/…）")
    p_mrc.add_argument("--judge-json", required=True,
                       help="冻结 Judge JSON 路径（用于 input_fingerprint）")
    p_mrc.add_argument("--truth-set", default="tests/fixtures/mm_truth_set_v1.json",
                       help="真值集路径（用于 input_fingerprint）")
    p_mrc.add_argument("--decided-by", required=True, help="决策人（姓名或 ID）")

    # 6-A / M1：Production Integrity + Directorial Quality **只读度量**（只诊断，不接线、不阻断）
    p_int = sub.add_parser("integrity",
                           help="只读生产完整性度量 PI-1…PI-6（覆盖率/双侧时长/静音/AV轨/字幕orphan/边界漂移）")
    p_int.add_argument("project_id")
    p_int.add_argument("--json", action="store_true", help="输出 JSON（机器可读；仍为只读）")
    p_int.add_argument("--film-task", default=None, help="指定 render 任务 ID（默认取最近一次成功渲染）")
    p_int.add_argument("--film", default=None, help="直接指定成片路径（默认取 render 产物 output）")
    p_int.add_argument("--out", default=None, help="把 JSON 报告写到指定路径（默认只打印）")
    p_dir = sub.add_parser("direction",
                           help="只读导演质量诊断 DQ-1…DQ-7（hook/复用/静态保持/密度/对齐/高潮/片尾）")
    p_dir.add_argument("project_id")
    p_dir.add_argument("--json", action="store_true", help="输出 JSON（机器可读；仍为只读）")
    p_dir.add_argument("--film-task", default=None, help="指定 render 任务 ID（默认取最近一次成功渲染）")
    p_dir.add_argument("--film", default=None, help="直接指定成片路径（默认取 render 产物 output）")
    p_dir.add_argument("--evidence", default=None,
                       help="既有只读多模态证据 JSON（4-B/5-A/5-D/Judge）；缺省则语义项为 NOT_ASSESSABLE")
    p_dir.add_argument("--no-freeze", action="store_true", help="跳过 freezedetect（更快；静态保持仅用时间轴）")
    p_dir.add_argument("--out", default=None, help="把 JSON 报告写到指定路径（默认只打印）")

    # Phase 14 / P14-2：VLM 视觉相关性判定**只读**评测门禁（真实 API 调用；成本上限；默认关闭）
    p_vlm = sub.add_parser("vlm-eval",
                           help="只读：VLM 视觉相关性判定 vs 冻结人工真值（P14-2 评测门禁）；"
                                "不写 DB、不改生产链；未配置凭据 ⇒ 不发起任何调用")
    p_vlm.add_argument("--truth", default=None,
                       help="冻结真值集 JSON（默认 tests/fixtures/vlm_relevance_truth_v1.json）")
    p_vlm.add_argument("--out", default=None, help="报告输出路径（默认 logs/phase14_eval_report.json）")
    p_vlm.add_argument("--budget-usd", type=float, default=2.0, help="成本硬上限（美元；超出即停）")
    p_vlm.add_argument("--max-pairs", type=int, default=None, help="只跑前 N 对（探价用）")
    p_vlm.add_argument("--json-only", action="store_true", help="只输出摘要（不做逐对打印）")
    p_vlm.add_argument("--prompt-variant", default="main", choices=["main", "diag_anchor"],
                       help="main=门禁口径（默认）；diag_anchor=诊断专用变体，不参与门禁判定")
    # 该分派块统一读取 args.project_id；vlm-eval 与项目无关，给一个被忽略的默认值。
    p_vlm.add_argument("--project-id", dest="project_id", default=None,
                       help=argparse.SUPPRESS)

    # 6-B / M2：DQ finding → 人工审片决策**只读闭环**（append-only 台账；本阶段禁止自动执行）
    p_dqr = sub.add_parser("dq-review",
                           help="DQ finding → 人类决策（ACCEPT/REJECT/DEFER）只读闭环；append-only 台账；"
                                "不执行任何修改、不接入 TASK_BLOCKED")
    p_dqr.add_argument("project_id")
    p_dqr.add_argument("--json", action="store_true", help="输出 JSON（机器可读；仍为只读）")
    p_dqr.add_argument("--film-task", default=None, help="指定 render 任务 ID（默认取最近一次成功渲染）")
    p_dqr.add_argument("--film", default=None, help="直接指定成片路径（默认取 render 产物 output）")
    p_dqr.add_argument("--evidence", default=None,
                       help="既有只读多模态证据 JSON（4-B/5-A/5-D/Judge）")
    p_dqr.add_argument("--ledger", default=None, help="决策台账路径（JSONL；append-only + 哈希链）")
    p_dqr.add_argument("--no-freeze", action="store_true", help="跳过 freezedetect（更快）")
    p_dqr.add_argument("--out", default=None, help="把 JSON 报告写到指定路径（默认只打印）")
    p_dqr.add_argument("--decide", default=None, help="对指定 finding_id 追加一条决策（append-only）")
    p_dqr.add_argument("--decision", default=None, choices=["ACCEPT", "REJECT", "DEFER"],
                       help="决策值（与 --decide 同用）")
    p_dqr.add_argument("--reason", default=None, help="决策理由（与 --decide 同用，必填）")
    p_dqr.add_argument("--by", default=None, help="决策者标识（与 --decide 同用，必填）")
    p_dqr.add_argument("--provenance", default=None, help="决策依据/来源（与 --decide 同用，必填）")

    # 6-B / M3：人工 REJECT → **局部修改方案**（只生成方案，禁止执行）
    p_rev = sub.add_parser("revision-plan",
                           help="把人工 REJECT 的 DQ finding 转成局部修改方案（只生成；禁止执行；"
                                "DEFER/UNKNOWN 只产出待补证据项）")
    p_rev.add_argument("project_id")
    p_rev.add_argument("--json", action="store_true", help="输出 JSON（机器可读；仍为只读）")
    p_rev.add_argument("--film-task", default=None, help="指定 render 任务 ID")
    p_rev.add_argument("--film", default=None, help="直接指定成片路径")
    p_rev.add_argument("--evidence", default=None, help="既有只读多模态证据 JSON")
    p_rev.add_argument("--ledger", default=None, help="6-B/M2 人工决策台账（JSONL）")
    p_rev.add_argument("--specs", default=None,
                       help="人工撰写的方案模板 JSON（按 finding_id 或 metric/kind 匹配）")
    p_rev.add_argument("--register", default=None, help="方案登记表（append-only JSONL）")
    p_rev.add_argument("--no-freeze", action="store_true", help="跳过 freezedetect（更快）")
    p_rev.add_argument("--out", default=None, help="把 JSON 报告写到指定路径（默认只打印）")

    args = parser.parse_args(argv)

    # Phase 12（P12-2）：许可数据 join ⇒ 生成**增强覆盖层**（只读消费记录；不访问 DB 写入路径、
    # 不建 engine；仅落盘一个新 artifact 文件；P7-2 原索引零改动）
    if args.cmd == "build-license-overlay":
        from video_studio.core import asset_license_join as _alj
        logs_dir = ROOT / "docs" / "regression_2x" / "logs"
        index_path = Path(args.index) if args.index else logs_dir / "asset_index.json"
        if not index_path.is_file():
            print("FAIL-CLOSED: 索引不存在 {}".format(index_path), file=sys.stderr)
            sys.exit(2)
        index = json.loads(index_path.read_text(encoding="utf-8"))
        prj = Path(args.project) if args.project else ROOT / "projects" / args.project_id
        cache_indexes = sorted((prj / "media" / "external").glob(".index.json"))
        recs, manifest, notes = _alj.collect_records(
            db_path=args.db, project_id=args.project_id, logs_dir=logs_dir,
            h5_path=logs_dir / "phase6g_exec_h5.json", cache_index_paths=cache_indexes)
        overlay = _alj.build_overlay(index=index, records=recs, sources_manifest=manifest,
                                     notes=notes)
        errs = _alj.validate_overlay(overlay)
        if errs:
            print("FAIL-CLOSED 覆盖层自检失败: {}".format(errs[:3]), file=sys.stderr)
            sys.exit(3)
        out = Path(args.out) if args.out else logs_dir / "license_overlay_v1.json"
        if not out.is_absolute():
            out = ROOT / out
        before = hashlib.sha256(index_path.read_bytes()).hexdigest()
        out.write_text(json.dumps(overlay, ensure_ascii=False, indent=1, sort_keys=True),
                       encoding="utf-8")
        after = hashlib.sha256(index_path.read_bytes()).hexdigest()
        payload = {"overlay_path": str(out), "artifact_hash": overlay["artifact_hash"],
                   "join_rule_version": overlay["join_rule_version"],
                   "records": len(recs), "counts": overlay["counts"],
                   "index_sha256_before": before, "index_sha256_after": after,
                   "index_untouched": before == after,
                   "zero_network": True, "zero_llm": True}
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True))
        else:
            print("许可覆盖层已生成：{}".format(out))
            print("  记录数={} 三态={} 索引零改动={}（sha256 {}）".format(
                len(recs), json.dumps(overlay["counts"], ensure_ascii=False),
                payload["index_untouched"], before[:16]))
            print("  提示：覆盖层默认不存在 ⇒ 绑定路径行为与 P7-6 完全一致；消费需显式传入")
        return

    # Phase 11（P11-3）：标题/封面候选**只读机械校验**（不访问 DB、不建 engine、不写任何东西）
    if args.cmd == "title-check":
        from video_studio.core import title_check as _tc
        def _load_json(p: str):
            path = Path(p)
            if not path.is_file():
                print("文件不存在: {}".format(path), file=sys.stderr)
                sys.exit(2)
            return json.loads(path.read_text(encoding="utf-8"))
        raw = _load_json(args.script)
        extra = _load_json(args.metadata) if args.metadata else None

        def _classify(obj):
            """按内容判定角色：script（含 segments）/ metadata（含 platforms 或候选字段）/ 二者皆有。"""
            if not isinstance(obj, dict):
                return None, None
            if isinstance(obj.get("script"), dict):        # A/B 日志
                inner = obj["script"]
                meta = obj if ("platforms" in obj or "title_candidates" in obj) else None
                return inner, meta
            is_script = "segments" in obj
            is_meta = any(k in obj for k in ("platforms", "title_candidates", "ab_plan",
                                            "cover_text_candidates"))
            return (obj if is_script else None), (obj if is_meta else None)

        s1, m1 = _classify(raw)
        s2, m2 = _classify(extra) if extra is not None else (None, None)
        script = s1 or s2
        metadata = m2 or m1
        rep = _tc.check_metadata(script, metadata,
                                 source={"script": args.script, "metadata": args.metadata,
                                         "roles": {"script": bool(script),
                                                   "metadata": bool(metadata)}})
        errs = _tc.validate(rep)
        if errs:
            print("报告自检失败: {}".format(errs[:3]), file=sys.stderr)
            sys.exit(3)
        payload = dict(rep)
        if args.no_timestamp:
            payload.pop("taken_at_utc", None)
        else:
            payload["taken_at_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True, default=str))
        else:
            print("标题/封面机械校验（只读；机械门为必要不充分条件，语义级不失实需人工终审）")
            print("  能力: {} | 结构码: {}".format(rep["capability"],
                                                  rep["structural_codes"] or "无"))
            for c in rep["candidates"]:
                print("  [{:>2}] {:>4} {} | {} 字 | technique={}".format(
                    c["index"], c["status"], c["text"][:44], c["length"], c["technique"]))
                for v in c["codes"]:
                    print("        违规: {}".format(json.dumps(v, ensure_ascii=False)[:110]))
            for c in rep["cover_texts"]:
                print("  [封面{}] {:>4} {} | {} 字 | pairing={}".format(
                    c["index"], c["status"], c["text"][:30], c["length"],
                    c.get("technique")))
                for v in c["codes"]:
                    print("        违规: {}".format(json.dumps(v, ensure_ascii=False)[:110]))
            print("  A/B 方案: {}".format(json.dumps(rep["ab_plan"], ensure_ascii=False)[:150]))
            print("  计数: {}".format(json.dumps(rep["counts"], ensure_ascii=False)))
        return

    # Phase 10（P10-2）：选题信号**人工触发的只读拉取**（不访问 DB、不建 engine、不派任务）。
    # 联网只发生在这一条命令；topic agent 运行期只读快照文件。
    if args.cmd == "fetch-signals":
        from video_studio.tools import topic_signals as _ts
        cfg = load_config(args.config)
        # 现实差异登记（Phase 10）：不读被基线钉定的 config.json 里的新键，改用
        # 内置解析（config.tools.topic_signals 若有则优先；否则 config/topic_signals.json；否则 none）
        ts_cfg, ts_cfg_source = _ts.resolve_config(cfg, root=ROOT)
        provider = args.provider or str(ts_cfg.get("provider") or "manual")
        if provider not in ("manual", "bilibili_popular"):
            print("FAIL-CLOSED [PROVIDER_UNKNOWN]: 仅支持 manual / bilibili_popular（当前 {}）"
                  .format(provider), file=sys.stderr)
            sys.exit(2)
        try:
            if provider == "bilibili_popular":
                snap = _ts.fetch_bilibili_popular(ps=args.ps)
            else:
                mp = args.manual or ts_cfg.get("manual_path")
                if not mp:
                    raise _ts.TopicSignalsError("PROVIDER_NOT_CONFIGURED",
                                                "manual provider 需要 --manual 或 "
                                                "tools.topic_signals.manual_path")
                snap = _ts.build_manual_snapshot(
                    mp if Path(mp).is_absolute() else ROOT / mp)
        except _ts.TopicSignalsError as exc:
            print("FAIL-CLOSED [{}]: {}".format(exc.code, exc.detail), file=sys.stderr)
            sys.exit(2)
        out = Path(args.out) if args.out else (ROOT / str(ts_cfg.get("snapshot_dir")
                                                         or "signals") /
                                               _ts.default_snapshot_name(provider))
        if not out.is_absolute():
            out = ROOT / out
        written = _ts.write_snapshot(snap, out)
        payload = {"provider": snap["provider"], "request_count": snap["request_count"],
                   "entries_raw": snap["entries_raw"], "entries_kept": snap["entries_kept"],
                   "dropped_count": snap["dropped_count"], "kinds": snap["kinds"],
                   "path": str(written), "entries_sha256": snap["sha256_of_entries"]}
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True))
        else:
            print("选题信号快照已落盘：{}".format(written))
            print("  provider={} 请求数={} 原始条目={} 保留={} 丢弃={} 类型={}".format(
                snap["provider"], snap["request_count"], snap["entries_raw"],
                snap["entries_kept"], snap["dropped_count"], snap["kinds"]))
            print("  提示：topic agent 只读该快照（运行期不联网）")
        return

    # report / metrics / semantic-check / review / select-candidate / rhythm 均为**只读或仅记录人工决定**的路径：
    # 不走 build_engine（避免建库/建目录/派发任务等副作用）
    if args.cmd in ("report", "metrics", "semantic-check", "review", "select-candidate", "rhythm",
                    "multimodal-check", "mm-review", "mm-temporal", "mm-quality", "mm-judge", "mm-review-confirm",
                    "integrity", "direction", "dq-review", "revision-plan", "retention-check",
                    "vlm-eval", "script-review", "script-apply"):
        config = load_config(args.config)
        db_path = Path(config.get("db", {}).get("path") or "projects/video_studio.db")
        if not db_path.is_absolute():
            db_path = ROOT / db_path
        project_dir = db_path.parent / args.project_id if args.project_id else db_path.parent
        if args.cmd == "report":
            from video_studio.ops.report import build_report, format_report
            rep = build_report(db_path, args.project_id, project_dir=project_dir,
                               recent_events=args.events)
            if not rep.get("found"):
                print("项目不存在: {}".format(args.project_id), file=sys.stderr)
                sys.exit(2)
            if args.json:
                print(json.dumps(rep, ensure_ascii=False, indent=1, default=str))
            else:
                print(format_report(rep, recent_events=args.events))
            if args.mm_advisory:
                from video_studio.ops.report import format_mm_advisory
                adv = format_mm_advisory(args.mm_advisory)
                if adv:
                    print()
                    print(adv)
            return
        if args.cmd == "metrics":
            from video_studio.ops.metrics import (corpus_metrics, format_metrics,
                                                  project_metrics)
            if args.all or not args.project_id:
                m = corpus_metrics(db_path, db_path.parent, limit=args.limit)
            else:
                m = project_metrics(db_path, args.project_id, project_dir=project_dir)
                if not m.get("found"):
                    print("项目不存在: {}".format(args.project_id), file=sys.stderr)
                    sys.exit(2)
            print(json.dumps(m, ensure_ascii=False, indent=1, default=str) if args.json
                  else format_metrics(m))
            return
        if args.cmd == "semantic-check":
            from video_studio.ops.metrics import project_metrics as _pm
            from video_studio.ops.metrics import semantic_report
            m = _pm(db_path, args.project_id, project_dir=project_dir)
            if not m.get("found"):
                print("项目不存在: {}".format(args.project_id), file=sys.stderr)
                sys.exit(2)
            rep = semantic_report(db_path, args.project_id)
            if args.json:
                print(json.dumps(rep, ensure_ascii=False, indent=1, default=str))
            else:
                print("项目 {} | 语义核验计数 {}（{}）".format(
                    args.project_id, rep["counts"], rep["version"]))
                print("  词典 sha256 {} | 判定口径：类别式规则，无数值阈值".format(
                    (rep["lexicon_sha256"] or "")[:16]))
                for s in rep["scenes"]:
                    a = s.get("asset") or {}
                    print("  {:<5s} {:<9s} {:<24s} {}".format(
                        s["scene_id"], s["verdict"], s["rule"] or "-", s["reason"][:110]))
                    print("        素材: {}".format(str(a.get("name"))[:96]))
                print("（只读：未修改任何状态、未触发任务、未访问网络）")
            return
        if args.cmd == "review":
            from video_studio.ops.selection_review import format_review, review_queue
            q = review_queue(db_path, args.project_id, only_flagged=not args.all)
            if not q.get("found"):
                print("项目不存在: {}".format(args.project_id), file=sys.stderr)
                sys.exit(2)
            print(json.dumps(q, ensure_ascii=False, indent=1, default=str) if args.json
                  else format_review(q))
            return
        if args.cmd == "script-review":
            from video_studio.core import script_review as SR
            rev = SR.build_review(project_dir, project_id=args.project_id, db_path=db_path)
            if not rev.get("found"):
                print("未找到 script_output 产物（{}）".format(rev.get("reason")),
                      file=sys.stderr)
                sys.exit(2)
            if args.json:
                print(json.dumps(rev, ensure_ascii=False, indent=1))
                return
            md = SR.render_markdown(rev)
            out = Path(args.out) if args.out else (project_dir / SR.REVIEW_MD_REL)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(md, encoding="utf-8")
            head = md.split("---")[0]
            print(head)
            print("已写出：{}".format(out))
            print("改完执行：python run.py script-apply {} --file \"{}\" --checklist 11111".format(
                args.project_id, out))
            return
        if args.cmd == "script-apply":
            from video_studio.core import script_review as SR
            base_path, base = SR.find_script_artifact(project_dir, project_id=args.project_id, db_path=db_path)
            if base is None:
                print("未找到 script_output 产物", file=sys.stderr)
                sys.exit(2)
            fp = Path(args.file)
            if not fp.is_file():
                print("审稿文件不存在：{}".format(fp), file=sys.stderr)
                sys.exit(2)
            new_map = SR.parse_markdown(fp.read_text(encoding="utf-8"))
            res = SR.apply_review(base, new_map,
                                  checklist=SR.parse_checklist(args.checklist),
                                  notes=args.notes, allow_drift=args.allow_drift)
            st = res.get("stats") or {}
            print("基线：{}".format(base_path))
            print("改写：{} 段 / {} → {} 字（{:+.1%}）/ 预估 {}s → {}s".format(
                len(new_map), st.get("old_chars"), st.get("new_chars"),
                st.get("delta_ratio") or 0.0, st.get("old_est_s"), st.get("new_est_s")))
            for w in res.get("warnings") or []:
                print("  ! {}".format(w))
            for e in res.get("errors") or []:
                print("  x {}".format(e))
            if not res.get("ok"):
                print("\n未落盘（校验不通过）。")
                sys.exit(1)
            if args.dry_run:
                print("\n--dry-run：校验通过，未落盘。")
                return
            p = SR.save_review(project_dir, res["payload"])
            print("\n已落盘：{}".format(p))
            print("下一步（人工审稿优先于 LLM，redo 后仍生效）：")
            try:
                import sqlite3 as _sq
                con = _sq.connect(str(db_path))
                rows = con.execute(
                    "select task_id, task_type from tasks where project_id=? and task_type in "
                    "('script','voice','render') order by rowid desc", (args.project_id,)
                ).fetchall()
                seen = set()
                for tid, ttype in rows:
                    if ttype in seen:
                        continue
                    seen.add(ttype)
                    print("  python run.py redo {}        # {}".format(tid, ttype))
                con.close()
            except Exception:                                  # noqa: BLE001
                print("  （无法列出任务，请用 status 查看 script/voice/render 任务 ID）")
            print("  随后：python run.py run {} --limit 4".format(args.project_id))
            return
        if args.cmd == "rhythm":
            from video_studio.ops.rhythm import format_rhythm, rhythm_report
            rep = rhythm_report(db_path, args.project_id, artifact_id=args.artifact,
                                config=config)
            if not rep.get("found", True):
                print("项目不存在: {}".format(args.project_id), file=sys.stderr)
                sys.exit(2)
            print(json.dumps(rep, ensure_ascii=False, indent=1, default=str) if args.json
                  else format_rhythm(rep))
            return
        if args.cmd == "retention-check":
            # Phase 9：只读留存评分（机械层 + LLM 评审层）。**不接入生产判定链**、
            # 不阻断任务、不自动改稿；DB 以 mode=ro 打开、零写入。
            from video_studio.ops.retention import (TemperatureZeroClient, evaluate,
                                                    format_retention, load_latest_script,
                                                    validate_report)
            if args.script:
                spath = Path(args.script)
                if not spath.is_file():
                    print("脚本不存在: {}".format(spath), file=sys.stderr)
                    sys.exit(2)
                payload = json.loads(spath.read_text(encoding="utf-8"))
                script = payload.get("script") if isinstance(payload, dict) else None
                script = script if isinstance(script, dict) else payload
                source = {"mode": "script-file", "path": str(spath)}
            else:
                if not args.project_id:
                    print("需要 project_id 或 --script <path>", file=sys.stderr)
                    sys.exit(2)
                found = load_latest_script(db_path, args.project_id, task_id=args.task)
                if not found.get("found"):
                    print("未找到 script 产物: {} ({})".format(args.project_id,
                                                              found.get("reason")),
                          file=sys.stderr)
                    sys.exit(2)
                script, source = found["script"], {"mode": "project-latest-script",
                                                  "project_id": args.project_id,
                                                  "artifact_id": found["artifact_id"],
                                                  "path": found["path"]}
            cache = None
            if args.cache:
                cpath = Path(args.cache)
                if cpath.is_file():                      # **只读**缓存（本命令从不写缓存）
                    cache = json.loads(cpath.read_text(encoding="utf-8"))
            client = None
            if not args.no_llm:
                cfg_llm = (config.get("llm") or {}).get("deepseek") or {}
                client = TemperatureZeroClient(cfg_llm)
                if not client.available:
                    print("提示：LLM 不可用（缺 API key）⇒ 仅机械层结果（PARTIAL）",
                          file=sys.stderr)
                    client = None
            rep = evaluate(script, source=source, cache=cache, client=client, llm=not args.no_llm,
                           taken_at=("OMITTED_FOR_DETERMINISM" if args.no_timestamp else None),
                           samples=(1 if args.no_llm else max(1, int(args.samples))))
            errs = validate_report(rep)
            if errs:
                print("报告自检失败: {}".format(errs[:3]), file=sys.stderr)
                sys.exit(3)
            if args.json:
                print(json.dumps(rep, ensure_ascii=False, indent=1, sort_keys=True, default=str))
            else:
                print(format_retention(rep))
            return
        if args.cmd == "multimodal-check":
            from video_studio.ops.multimodal import format_mm, multimodal_report
            rep = multimodal_report(db_path, args.project_id, artifact_id=args.artifact,
                                    config=config,
                                    frames_dir=(Path(args.frames_dir) if args.frames_dir
                                                else None))
            if not rep.get("found", True):
                print("项目不存在: {}".format(args.project_id), file=sys.stderr)
                sys.exit(2)
            payload = json.dumps(rep, ensure_ascii=False, indent=1, default=str)
            if args.out:
                Path(args.out).write_text(payload, encoding="utf-8")
                print("报告已写入 {}".format(args.out))
            print(payload if args.json else format_mm(rep))
            return
        if args.cmd == "mm-review":
            from video_studio.ops.mm_candidates import format_mm_review, mm_review_report
            rep = mm_review_report(db_path, args.project_id, artifact_id=args.artifact,
                                   config=config,
                                   frames_dir=(Path(args.frames_dir) if args.frames_dir
                                               else None))
            if not rep.get("found", True):
                print("项目不存在: {}".format(args.project_id), file=sys.stderr)
                sys.exit(2)
            payload = json.dumps(rep, ensure_ascii=False, indent=1, default=str)
            if args.out:
                Path(args.out).write_text(payload, encoding="utf-8")
                print("报告已写入 {}".format(args.out))
            print(payload if args.json else format_mm_review(rep))
            return
        if args.cmd == "mm-temporal":
            from video_studio.ops.mm_temporal import format_mmt, temporal_report
            rep = temporal_report(db_path, args.project_id, artifact_id=args.artifact,
                                  config=config,
                                  frames_dir=(Path(args.frames_dir) if args.frames_dir else None),
                                  with_five_a=not args.no_five_a)
            if not rep.get("found", True):
                print("项目不存在: {}".format(args.project_id), file=sys.stderr)
                sys.exit(2)
            payload = json.dumps(rep, ensure_ascii=False, indent=1, default=str)
            if args.out:
                Path(args.out).write_text(payload, encoding="utf-8")
                print("报告已写入 {}".format(args.out))
            print(payload if args.json else format_mmt(rep))
            return
        if args.cmd == "mm-quality":
            from video_studio.ops.mm_quality import calibration_report, format_mmq
            rep = calibration_report(db_path, args.project_id,
                                     truth_set_path=args.truth_set, config=config,
                                     frames_dir=(Path(args.frames_dir) if args.frames_dir
                                                 else None),
                                     run_layers=not args.no_layers)
            if not rep.get("found", True):
                print("项目不存在: {}".format(args.project_id), file=sys.stderr)
                sys.exit(2)
            payload = json.dumps(rep, ensure_ascii=False, indent=1, default=str)
            if args.out:
                Path(args.out).write_text(payload, encoding="utf-8")
                print("报告已写入 {}".format(args.out))
            print(payload if args.json else format_mmq(rep))
            return
        if args.cmd == "mm-judge":
            from video_studio.ops.mm_judge import format_mmj, judge_report
            cal = None
            if args.from_calibration:
                cal = json.loads(Path(args.from_calibration).read_text(encoding="utf-8-sig"))
            rep = judge_report(db_path, args.project_id, config=config,
                               truth_set_path=args.truth_set, judge_truth_path=args.judge_truth,
                               calibration=cal,
                               frames_dir=(Path(args.frames_dir) if args.frames_dir else None))
            if not rep.get("found", True):
                print("项目不存在: {}".format(args.project_id), file=sys.stderr)
                sys.exit(2)
            payload = json.dumps(rep, ensure_ascii=False, indent=1, default=str)
            if args.out:
                Path(args.out).write_text(payload, encoding="utf-8")
                print("报告已写入 {}".format(args.out))
            print(payload if args.json else format_mmj(rep))
            return

        if args.cmd == "integrity":
            from video_studio.ops.integrity import (build_integrity_report, format_integrity,
                                                    write_report)
            rep = build_integrity_report(args.project_id, db_path, ROOT, config,
                                         film_task=args.film_task, film=args.film)
            if args.out:
                write_report(rep, args.out)
                print("报告已写入 {}".format(args.out))
            print(json.dumps(rep, ensure_ascii=False, indent=1, default=str) if args.json
                  else format_integrity(rep))
            return
        if args.cmd == "direction":
            from video_studio.ops.direction import (build_direction_report, format_direction,
                                                    write_report as _wd)
            rep = build_direction_report(args.project_id, db_path, ROOT, config,
                                         film_task=args.film_task, film=args.film,
                                         evidence_path=args.evidence,
                                         measure_freeze=not args.no_freeze)
            if args.out:
                _wd(rep, args.out)
                print("报告已写入 {}".format(args.out))
            print(json.dumps(rep, ensure_ascii=False, indent=1, default=str) if args.json
                  else format_direction(rep))
            return
        if args.cmd == "vlm-eval":
            from video_studio.tools.vlm_eval import main as _vlm_main
            _argv = ["--budget-usd", str(args.budget_usd)]
            if args.truth:
                _argv += ["--truth", args.truth]
            if args.out:
                _argv += ["--out", args.out]
            if args.max_pairs is not None:
                _argv += ["--max-pairs", str(args.max_pairs)]
            if args.json_only:
                _argv += ["--json-only"]
            if getattr(args, "prompt_variant", "main") != "main":
                _argv += ["--prompt-variant", args.prompt_variant]
            rc = _vlm_main(_argv)
            if rc not in (0, 3):
                sys.exit(rc)
            return
        if args.cmd == "dq-review":
            from video_studio.core import human_review as _hr
            from video_studio.ops.review import (build_review_report, format_review,
                                                 write_report as _wr)
            extra = None
            film_level = None
            if args.ledger:
                extra, film_level = None, None
            if args.decide:
                # 先只读构建（拿 finding 列表），再**仅追加**一条决策到台账（append-only）
                rep0 = build_review_report(args.project_id, db_path, ROOT, config,
                                           film_task=args.film_task, film=args.film,
                                           evidence_path=args.evidence,
                                           ledger_path=args.ledger, extra_items=extra,
                                           measure_freeze=False)
                item = next((i for i in rep0["items"] if i["finding_id"] == args.decide), None)
                if item is None:
                    print("FAIL: 未找到 finding_id={}".format(args.decide), file=sys.stderr)
                    return
                for fld, val in (("--reason", args.reason), ("--by", args.by),
                                 ("--provenance", args.provenance)):
                    if not val:
                        print("FAIL: --decide 需要 {}".format(fld), file=sys.stderr)
                        return
                dec = _hr.make_decision(item, args.decision, args.reason, args.by,
                                        args.provenance)
                rec = _hr.append_decision(args.ledger, dec)
                print("决策已追加: seq={} finding={} decision={}".format(
                    rec["seq"], rec["finding_id"], rec["decision"]))
                print("台账: {}（append-only）".format(args.ledger))
                return
            rep = build_review_report(args.project_id, db_path, ROOT, config,
                                      film_task=args.film_task, film=args.film,
                                      evidence_path=args.evidence, ledger_path=args.ledger,
                                      extra_items=extra, film_level_decision=film_level,
                                      measure_freeze=not args.no_freeze)
            if args.out:
                _wr(rep, args.out)
                print("报告已写入 {}".format(args.out))
            print(json.dumps(rep, ensure_ascii=False, indent=1, default=str) if args.json
                  else format_review(rep))
            return
        if args.cmd == "revision-plan":
            from video_studio.core import revision as _rev
            from video_studio.ops.revision import (build_revision_plan, format_plan,
                                                   write_report as _wrev)
            specs = []
            if args.specs:
                specs = json.loads(Path(args.specs).read_text(encoding="utf-8"))
                if isinstance(specs, dict):
                    specs = specs.get("specs") or []
            plan = build_revision_plan(args.project_id, db_path, ROOT, config,
                                       film_task=args.film_task, film=args.film,
                                       evidence_path=args.evidence, ledger_path=args.ledger,
                                       proposal_specs=specs, measure_freeze=not args.no_freeze)
            if args.register:
                for p in plan["proposals"]:
                    _rev.append_proposal(args.register, p)
                plan["register"] = {"path": args.register,
                                    "entries": len(_rev.load_register(args.register)),
                                    "chain_ok": _rev.verify_register_chain(
                                        _rev.load_register(args.register))["ok"]}
            if args.out:
                _wrev(plan, args.out)
                print("报告已写入 {}".format(args.out))
            print(json.dumps(plan, ensure_ascii=False, indent=1, default=str) if args.json
                  else format_plan(plan))
            return
        if args.cmd == "mm-review-confirm":
            from video_studio.ops.mm_review_confirm import run_mm_review_confirm
            result = run_mm_review_confirm(
                db_path=db_path, project_id=args.project_id,
                decisions_path=args.decisions, judge_json_path=args.judge_json,
                truth_set_path=args.truth_set, decided_by=args.decided_by,
            )
            if result.get("ok"):
                print("决策记录已追加: {} 条".format(result.get("appended", 0)))
                print("决策文件: {}".format(result.get("decisions_file", "")))
            else:
                print("FAIL: {}".format(result.get("error", "")), file=sys.stderr)
                sys.exit(1)
            return
        # select-candidate（4-C）：先只读校验，通过后才写既有 decisions/changelog
        from video_studio.ops.selection_review import record_selection
        res = record_selection(db_path, args.project_id, args.scene, args.asset, args.by,
                               args.reason, dry_run=args.dry_run)
        if not res.get("ok"):
            print("[{}] {}".format(res.get("code"), res.get("detail")), file=sys.stderr)
            sys.exit(3)
        print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
        if not args.dry_run:
            print("\n下一步（替换生效，复用既有 append-only / version+1）：\n  " + res["next_step"])
            return

        return

    config = load_config(args.config)
    engine = build_engine(config)
    if args.cmd == "init":
        pid = engine.create_project(args.goal, args.name)
        print(f"项目已创建: {pid}")
    elif args.cmd == "plan":
        from video_studio.pipeline.lifecycle import build_pipeline_task_specs
        from video_studio.core.engine import EngineError
        specs = build_pipeline_task_specs(args.project_id)
        created, skipped = [], []
        # 解析依赖名 -> 同类型最近任务 ID（创建顺序保证存在）
        id_by_type: dict[str, str] = {}
        for spec in specs:
            deps = [id_by_type[d] for d in spec["depends_on"] if d in id_by_type]
            try:
                tid = engine.create_task(
                    args.project_id, spec["task_type"], spec["agent_role"],
                    dependencies=deps, inputs={"phase": spec["phase"]},
                    requires_approval=spec["requires_approval"])
            except EngineError as exc:
                skipped.append(f"{spec['task_type']}({spec['agent_role']})")
                continue
            id_by_type[spec["task_type"]] = tid
            created.append(tid)
        print(f"已创建 {len(created)} 个任务" + (f"，跳过 {len(skipped)} 个未实现角色: {', '.join(skipped)}" if skipped else ""))
    elif args.cmd == "run":
        n = engine.run_cycle(args.project_id, args.limit)
        print(f"本轮执行 {n} 个任务")
    elif args.cmd == "status":
        from video_studio.tabulate_lite import render
        tasks = engine.db.list_tasks(args.project_id)
        print(render(tasks))
    elif args.cmd == "approve":
        from video_studio.hitl.service import HITL
        HITL(engine, config).decide(args.task_id, args.decision, args.comment)
        print(f"已处理审批: {args.task_id} -> {args.decision}")
    elif args.cmd == "recover":
        n = engine.recover()
        print(f"已恢复 {n} 个中断任务")
    elif args.cmd == "redo":
        tid = engine.redo(args.task_id)
        print(f"已创建重做任务: {tid}")
    elif args.cmd == "claims":
        claims = engine.db.list_claims(args.project_id)
        if not claims:
            print("(项目暂无 Claim)")
        else:
            header = ["claim_id", "类型", "风险", "状态", "结论", "证据数", "待人工", "表述"]
            rows = [[c["claim_id"], c["type"], c["risk"], c["status"],
                     c.get("conclusion") or "-", str(c.get("source_count", 0)),
                     "是" if c.get("human_review_required") else "",
                     c["text"][:44]] for c in claims]
            widths = [max(len(str(h)), *(len(str(r[i])) for r in rows)) for i, h in enumerate(header)]
            sep = "+" + "+".join("-" * (w + 2) for w in widths) + "+"

            def fmt(cells):
                return "| " + " | ".join(str(c).ljust(w) for c, w in zip(cells, widths)) + " |"
            print(sep)
            print(fmt(header))
            print(sep)
            for r in rows:
                print(fmt(r))
            print(sep)
    elif args.cmd == "claim":
        from video_studio.hitl.service import HITL
        import json as _json
        ctx = HITL(engine, config).claim_context(args.claim_id)
        print(_json.dumps(ctx, ensure_ascii=False, indent=2, default=str))
    elif args.cmd in ("approve-claim", "reject-claim", "revise-claim"):
        from video_studio.hitl.service import HITL
        hitl = HITL(engine, config)
        decision = {"approve-claim": "approve", "reject-claim": "reject",
                    "revise-claim": "revise"}[args.cmd]
        revised = getattr(args, "text", None)
        result = hitl.decide_claim(args.claim_id, decision, args.comment, revised)
        print(f"Claim 已处理: {result}")
    elif args.cmd == "ingest":
        from pathlib import Path as _Path
        import shutil as _shutil
        src = _Path(args.source_dir)
        if not src.is_dir():
            print(f"目录不存在: {src}")
            return
        media_dir = engine.project_dir(args.project_id) / "media"
        media_dir.mkdir(parents=True, exist_ok=True)
        copied, skipped = [], []
        for f in sorted(src.rglob("*")):
            if not f.is_file():
                continue
            if f.suffix.lower() not in {".mp4", ".mov", ".mkv", ".avi", ".webm", ".mp3", ".wav",
                                         ".m4a", ".flac", ".jpg", ".jpeg", ".png", ".webp",
                                         ".gif", ".pdf", ".docx", ".txt", ".md"}:
                skipped.append(f.name)
                continue
            dst = media_dir / f.name
            if dst.exists():
                skipped.append(f.name)
                continue
            _shutil.copy2(f, dst)
            copied.append(dst.name)
        print(f"已登记 {len(copied)} 个文件，跳过 {len(skipped)} 个（非媒体类型或重名）")
        if copied:
            # 重建素材索引：创建 asset_audit 任务并执行
            tid = engine.create_task(args.project_id, "asset_audit", "asset",
                                     inputs={"phase": "ingest"})
            engine.run_cycle(args.project_id, limit=1)
            t = engine.db.get_task(tid)
            print(f"素材索引已更新（{len(t['artifacts'])} 个产物）")
    elif args.cmd == "loop":
        from video_studio.hitl.service import HITL
        hitl = HITL(engine, config)
        import json as _json
        for round_no in range(1, args.max_rounds + 1):
            pending = engine.db.list_tasks(args.project_id, "NEEDS_REVIEW")
            for t in pending:
                arts = [engine.db.get_artifact(a) for a in t["artifacts"]]
                summaries = " | ".join((a.get("summary") or "")[:80] for a in arts if a)
                print(f"[闸门] {t['task_type']}({t['agent_role']}) 等待审批 :: {summaries}")
                if args.auto_approve:
                    hitl.decide(t["task_id"], "approve", "演示运行自动批准")
                    print(f"  -> 已自动批准 {t['task_id']}")
                else:
                    print(f"  -> 请用: python run.py approve {t['task_id']} approve|reject|modify")
            if pending and not args.auto_approve:
                print("存在待审批任务，停止推进。")
                return
            n = engine.run_cycle(args.project_id)
            tasks = engine.db.list_tasks(args.project_id)
            active = [t for t in tasks if t["status"] in ("PENDING", "NEEDS_REVIEW", "RUNNING")]
            print(f"[第{round_no}轮] 执行 {n} 个任务；未完成 {len(active)} 个")
            if not active:
                print("全部任务完成。")
                break
            if n == 0 and not pending:
                blocked = [t for t in tasks if t["status"] == "BLOCKED"]
                for t in blocked:
                    print(f"[阻塞] {t['task_type']}({t['agent_role']}): {(t['error'] or '')[:120]}")
                pending_claims = engine.db.list_claims(args.project_id, "NEEDS_HUMAN")
                if pending_claims:
                    print(f"[Claim 闸门] 存在 {len(pending_claims)} 条待人工审核的 Claim，"
                          f"生产环节已挂起。请处理：")
                    for c in pending_claims:
                        print(f"  -> python run.py claim {c['claim_id']}   # 查看证据与质疑")
                        print(f"     python run.py approve-claim {c['claim_id']}   # 批准")
                if blocked:
                    print("存在阻塞任务，请人工介入后再次运行 loop。")
                return
        from video_studio.tabulate_lite import render
        print(render(engine.db.list_tasks(args.project_id)))


if __name__ == "__main__":
    main()


