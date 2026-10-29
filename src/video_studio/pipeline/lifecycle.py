"""标准生产生命周期定义：阶段 / 任务 / 依赖 / 闸门 / 并行关系。

与 docs/DESIGN.md §5 对应。并行关系由"依赖为空"体现：
同一阶段内无依赖的任务可并行派发。
"""

from __future__ import annotations

STANDARD_PIPELINE = {
    "p0_boot": {
        "tasks": [
            {"task_type": "plan", "agent_role": "pm", "requires_approval": False},
        ],
    },
    "p1_topic": {
        "tasks": [
            # 闸门#1：选题+核心观点
            {"task_type": "topic", "agent_role": "topic", "requires_approval": True},
        ],
    },
    "p1_research": {
        "tasks": [
            {"task_type": "research", "agent_role": "research", "depends_on": ["topic"]},
            # 来源核查可与研究串行接续（研究完成后才能核查其输出）
            {"task_type": "source_verify", "agent_role": "source_verify", "depends_on": ["research"]},
        ],
    },
    "p1_structure": {
        "tasks": [
            # 闸门#2：内容结构
            {"task_type": "structure", "agent_role": "structure",
             "depends_on": ["source_verify"], "requires_approval": True},
        ],
    },
    "p2_script": {
        "tasks": [
            {"task_type": "script", "agent_role": "script", "depends_on": ["structure"],
             "requires_approval": True},  # 闸门#3：最终脚本
        ],
    },
    "p2b_verification": {
        # V2 事实核查子流程：script → claim_extract → evidence → skeptic → fact_check
        # → conflict_detect → HITL（Claim 级人工审核，经 claims 命令闭环）
        "tasks": [
            {"task_type": "claim_extract", "agent_role": "claim_extractor",
             "depends_on": ["script"]},
            # 依赖 claim_extract：证据登记必须发生在 Claim 提取之后，才能完成关联
            {"task_type": "evidence_index", "agent_role": "evidence",
             "depends_on": ["research", "source_verify", "claim_extract"]},
            {"task_type": "skeptic_check", "agent_role": "critic",
             "depends_on": ["claim_extract"]},
            {"task_type": "fact_check", "agent_role": "fact_check",
             "depends_on": ["claim_extract", "evidence_index"]},
            {"task_type": "conflict_check", "agent_role": "conflict_detector",
             "depends_on": ["fact_check"]},
        ],
    },
    "p3_visual": {
        "tasks": [
            # 三路并行：视觉规划 / 素材盘点检索 / 生成需求
            {"task_type": "visual_plan", "agent_role": "visual", "depends_on": ["script"]},
            {"task_type": "asset_audit", "agent_role": "asset", "depends_on": ["script"]},
            {"task_type": "retrieval", "agent_role": "retrieval", "depends_on": ["visual_plan"]},
            {"task_type": "editing_plan", "agent_role": "editing",
             "depends_on": ["visual_plan", "retrieval"], "requires_approval": True},  # 闸门#4
        ],
    },
    "p4_audio": {
        "tasks": [
            # 双路并行：配音 / 字幕初稿
            {"task_type": "voice", "agent_role": "voice", "depends_on": ["script"]},
            {"task_type": "subtitle", "agent_role": "subtitle", "depends_on": ["script"]},
            {"task_type": "audio_mix", "agent_role": "audio", "depends_on": ["voice"]},
        ],
    },
    "p5_assembly": {
        "tasks": [
            {"task_type": "render", "agent_role": "editing", "depends_on": ["editing_plan", "audio_mix"]},
            {"task_type": "thumbnail", "agent_role": "thumbnail", "depends_on": ["render"]},
        ],
    },
    "p6_qa": {
        "tasks": [
            # 三路并行：质检 / 合规 / 终审挑战
            {"task_type": "qa", "agent_role": "qa", "depends_on": ["render"]},
            {"task_type": "compliance", "agent_role": "compliance", "depends_on": ["render"]},
            {"task_type": "critic_final", "agent_role": "critic", "depends_on": ["render"]},
            # 闸门#5：最终成片（V1 由人工在 CLI 对 render 任务批准）
        ],
    },
    "p7_publish": {
        "tasks": [
            {"task_type": "platform", "agent_role": "platform", "depends_on": ["render"]},
            {"task_type": "metadata", "agent_role": "metadata", "depends_on": ["platform"]},
            # 闸门#6：发布（V1：导出+清单，人工执行实际发布）
        ],
    },
    "p8_review": {
        "tasks": [
            {"task_type": "analytics", "agent_role": "analyst", "depends_on": ["render"]},
        ],
    },
}


def build_pipeline_task_specs(project_id: str) -> list[dict]:
    """把标准管线展开为 (task_type, agent_role, deps, requires_approval) 列表。

    依赖名（如 "topic"）映射到同项目内最近一次同 task_type 的任务 ID，
    由 Engine 在创建时解析。
    """
    specs = []
    for phase, defn in STANDARD_PIPELINE.items():
        for spec in defn["tasks"]:
            specs.append({
                "project_id": project_id,
                "task_type": spec["task_type"],
                "agent_role": spec["agent_role"],
                "depends_on": spec.get("depends_on", []),
                "requires_approval": bool(spec.get("requires_approval")),
                "phase": phase,
            })
    return specs
