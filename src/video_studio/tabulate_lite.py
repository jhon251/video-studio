"""极简终端表格渲染（零依赖）。"""


def render(rows: list[dict]) -> str:
    if not rows:
        return "(无任务)"
    cols = ["task_id", "task_type", "agent_role", "status", "version", "retry_count",
            "requires_approval", "artifacts", "error"]
    header = ["任务ID", "类型", "Agent", "状态", "版本", "重试", "待审批", "产物数", "错误"]
    lines = []
    for row in rows:
        lines.append([
            row.get("task_id", ""),
            row.get("task_type", ""),
            row.get("agent_role", ""),
            row.get("status", ""),
            str(row.get("version", 1)),
            str(row.get("retry_count", 0)),
            "是" if row.get("requires_approval") else "",
            str(len(row.get("artifacts", []))),
            (row.get("error") or "")[:24],
        ])
    widths = [max(len(str(header[i])), *(len(str(r[i])) for r in lines)) for i in range(len(header))]
    sep = "+" + "+".join("-" * (w + 2) for w in widths) + "+"

    def fmt(cells):
        return "| " + " | ".join(str(c).ljust(w) for c, w in zip(cells, widths)) + " |"

    out = [sep, fmt(header), sep]
    out.extend(fmt(r) for r in lines)
    out.append(sep)
    return "\n".join(out)
