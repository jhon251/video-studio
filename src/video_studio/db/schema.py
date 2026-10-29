"""SQLite 权威状态层：任务 / 事件 / 产物 / 决策 / 记忆。

所有表均为 append-only 风格：任务与产物只新增版本、不删除历史；
事件表是消息总线的持久形态，只追加。
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS projects (
  project_id   TEXT PRIMARY KEY,
  name         TEXT NOT NULL,
  goal         TEXT NOT NULL,
  status       TEXT NOT NULL DEFAULT 'ACTIVE',
  created_at   REAL NOT NULL,
  updated_at   REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
  task_id         TEXT PRIMARY KEY,
  project_id      TEXT NOT NULL,
  parent_task_id  TEXT,
  lineage         TEXT NOT NULL DEFAULT '[]',
  task_type       TEXT NOT NULL,
  agent_role      TEXT NOT NULL,
  status          TEXT NOT NULL DEFAULT 'PENDING',
  priority        INTEGER NOT NULL DEFAULT 3,
  dependencies    TEXT NOT NULL DEFAULT '[]',
  inputs          TEXT NOT NULL DEFAULT '{}',
  expected_output TEXT NOT NULL DEFAULT '{}',
  artifacts       TEXT NOT NULL DEFAULT '[]',
  evidence        TEXT NOT NULL DEFAULT '[]',
  confidence      REAL NOT NULL DEFAULT 0,
  model_used      TEXT,
  cost_usd        REAL NOT NULL DEFAULT 0,
  tools_used      TEXT NOT NULL DEFAULT '[]',
  retry_count     INTEGER NOT NULL DEFAULT 0,
  max_retries     INTEGER NOT NULL DEFAULT 2,
  error           TEXT,
  requires_approval INTEGER NOT NULL DEFAULT 0,
  approval        TEXT,
  version         INTEGER NOT NULL DEFAULT 1,
  created_at      REAL NOT NULL,
  updated_at      REAL NOT NULL,
  started_at      REAL,
  finished_at     REAL
);
CREATE INDEX IF NOT EXISTS idx_tasks_project_status ON tasks(project_id, status);
CREATE INDEX IF NOT EXISTS idx_tasks_lineage ON tasks(project_id);
CREATE TABLE IF NOT EXISTS events (
  event_id    INTEGER PRIMARY KEY AUTOINCREMENT,
  ts          REAL NOT NULL,
  project_id  TEXT NOT NULL,
  task_id     TEXT,
  type        TEXT NOT NULL,
  actor       TEXT NOT NULL,
  payload     TEXT NOT NULL DEFAULT '{}',
  human_visible INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_events_project ON events(project_id, event_id);
CREATE TABLE IF NOT EXISTS artifacts (
  artifact_id  TEXT PRIMARY KEY,
  project_id   TEXT NOT NULL,
  task_id      TEXT,
  type         TEXT NOT NULL,
  path         TEXT NOT NULL,
  sha256       TEXT NOT NULL,
  size         INTEGER NOT NULL DEFAULT 0,
  provenance   TEXT NOT NULL DEFAULT '{}',
  license      TEXT,
  version      INTEGER NOT NULL DEFAULT 1,
  superseded_by TEXT,
  summary      TEXT,
  created_at   REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS decisions (
  decision_id  TEXT PRIMARY KEY,
  project_id   TEXT NOT NULL,
  node         TEXT NOT NULL,
  made_by      TEXT NOT NULL,
  state        TEXT NOT NULL,
  rationale    TEXT,
  artifact_snapshot TEXT NOT NULL DEFAULT '[]',
  created_at   REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS memories (
  memory_id  INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT,
  kind       TEXT NOT NULL,
  agent_role TEXT,
  key        TEXT NOT NULL,
  content    TEXT NOT NULL,
  version    INTEGER NOT NULL DEFAULT 1,
  created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_memories ON memories(kind, agent_role, project_id);
-- ============ V2：事实核查系统（新增，不改动 V1 表） ============
CREATE TABLE IF NOT EXISTS claims (
  claim_id   TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  task_id    TEXT,
  segment_ref TEXT,
  text       TEXT NOT NULL,
  type       TEXT NOT NULL DEFAULT 'FACT',
  risk       TEXT NOT NULL DEFAULT 'MEDIUM',
  markers    TEXT NOT NULL DEFAULT '[]',
  status     TEXT NOT NULL DEFAULT 'UNVERIFIED',
  conclusion TEXT,
  confidence TEXT,
  source_count INTEGER NOT NULL DEFAULT 0,
  human_review_required INTEGER NOT NULL DEFAULT 0,
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_claims_project_status ON claims(project_id, status);
CREATE INDEX IF NOT EXISTS idx_claims_project_risk ON claims(project_id, risk);
CREATE TABLE IF NOT EXISTS evidence (
  evidence_id TEXT PRIMARY KEY,
  project_id  TEXT NOT NULL,
  source      TEXT NOT NULL,
  source_type TEXT NOT NULL DEFAULT 'unknown',
  publication_date TEXT,
  reliability TEXT NOT NULL DEFAULT 'unknown',
  excerpt     TEXT,
  url         TEXT,
  added_by    TEXT,
  task_id     TEXT,
  support_level TEXT,
  created_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_evidence_project ON evidence(project_id);
CREATE TABLE IF NOT EXISTS claim_evidence (
  claim_id    TEXT NOT NULL,
  evidence_id TEXT NOT NULL,
  PRIMARY KEY (claim_id, evidence_id)
);
CREATE TABLE IF NOT EXISTS conflicts (
  conflict_id TEXT PRIMARY KEY,
  project_id  TEXT NOT NULL,
  claim_id    TEXT NOT NULL,
  source_a    TEXT,
  source_b    TEXT,
  description TEXT,
  authority_comparison TEXT,
  recency_comparison   TEXT,
  recommended TEXT,
  confidence  TEXT,
  human_review_required INTEGER NOT NULL DEFAULT 1,
  status      TEXT NOT NULL DEFAULT 'OPEN',
  created_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_conflicts_project ON conflicts(project_id, status);
CREATE TABLE IF NOT EXISTS changelog (
  change_id   INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id  TEXT NOT NULL,
  target_type TEXT NOT NULL,
  target_id   TEXT NOT NULL,
  changed_by  TEXT NOT NULL,
  reason      TEXT,
  before_summary TEXT,
  after_summary  TEXT,
  human_confirmed INTEGER NOT NULL DEFAULT 0,
  created_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_changelog_target ON changelog(project_id, target_type, target_id);
-- ============ V2.1：LLM 语义判定缓存/审计（附加表，不动现有 V2 表） ============
CREATE TABLE IF NOT EXISTS llm_judge_cache (
  cache_key      TEXT PRIMARY KEY,
  claim_text     TEXT,
  evidence_url   TEXT,
  rule_label     TEXT,
  llm_label      TEXT,
  reason         TEXT,
  model          TEXT,
  tier           TEXT,
  prompt_version TEXT,
  fallback_reason TEXT,
  tokens_in      INTEGER NOT NULL DEFAULT 0,
  tokens_out     INTEGER NOT NULL DEFAULT 0,
  cost_usd       REAL NOT NULL DEFAULT 0,
  latency_ms     INTEGER NOT NULL DEFAULT 0,
  cache_hit      INTEGER NOT NULL DEFAULT 0,
  created_at     REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_llm_judge_created ON llm_judge_cache(created_at);
"""


def now() -> float:
    return time.time()


def _js(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def _ld(value):
    return json.loads(value) if value else value


class Database:
    """项目状态库封装。所有变更走这里，写操作自动记录审计事件。"""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.migrate()

    def migrate(self) -> None:
        self.conn.executescript(SCHEMA_SQL)
        # V2.0.1：evidence.support_level 附加列（旧库兼容迁移）
        # V2.0.2：支持关系必须显式评估——未评估存 NULL（added_by=human 不等于 DIRECT_SUPPORT），
        #         历史 NOT NULL 约束重建为可空；历史行已存值原样保留
        info = {r[1]: r for r in self.conn.execute("PRAGMA table_info(evidence)")}
        if "support_level" not in info:
            self.conn.execute("ALTER TABLE evidence ADD COLUMN support_level TEXT")
        elif info["support_level"][3]:
            self.conn.executescript(
                "CREATE TABLE evidence_v202 ("
                "  evidence_id TEXT PRIMARY KEY,"
                "  project_id  TEXT NOT NULL,"
                "  source      TEXT NOT NULL,"
                "  source_type TEXT NOT NULL DEFAULT 'unknown',"
                "  publication_date TEXT,"
                "  reliability TEXT NOT NULL DEFAULT 'unknown',"
                "  excerpt     TEXT,"
                "  url         TEXT,"
                "  added_by    TEXT,"
                "  task_id     TEXT,"
                "  support_level TEXT,"
                "  created_at  REAL NOT NULL"
                ");"
                "INSERT INTO evidence_v202(evidence_id, project_id, source, source_type,"
                " publication_date, reliability, excerpt, url, added_by, task_id,"
                " support_level, created_at)"
                " SELECT evidence_id, project_id, source, source_type, publication_date,"
                " reliability, excerpt, url, added_by, task_id, support_level, created_at"
                " FROM evidence;"
                "DROP TABLE evidence;"
                "ALTER TABLE evidence_v202 RENAME TO evidence;"
                "CREATE INDEX IF NOT EXISTS idx_evidence_project ON evidence(project_id);"
            )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # ---------- projects ----------
    def create_project(self, project_id: str, name: str, goal: str) -> None:
        self.conn.execute(
            "INSERT INTO projects(project_id, name, goal, status, created_at, updated_at) VALUES(?,?,?,?,?,?)",
            (project_id, name, goal, "ACTIVE", now(), now()),
        )
        self.conn.commit()

    def get_project(self, project_id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM projects WHERE project_id=?", (project_id,)).fetchone()
        return dict(row) if row else None

    def touch_project(self, project_id: str) -> None:
        self.conn.execute("UPDATE projects SET updated_at=? WHERE project_id=?", (now(), project_id))
        self.conn.commit()

    # ---------- tasks ----------
    def insert_task(self, task: dict) -> str:
        cols = (
            "task_id,project_id,parent_task_id,lineage,task_type,agent_role,status,priority,"
            "dependencies,inputs,expected_output,artifacts,evidence,confidence,model_used,cost_usd,"
            "tools_used,retry_count,max_retries,error,requires_approval,approval,version,"
            "created_at,updated_at,started_at,finished_at"
        )
        t = now()
        self.conn.execute(
            f"INSERT INTO tasks({cols}) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                task["task_id"], task["project_id"], task.get("parent_task_id"),
                _js(task.get("lineage", [])), task["task_type"], task["agent_role"],
                task.get("status", "PENDING"), task.get("priority", 3),
                _js(task.get("dependencies", [])), _js(task.get("inputs", {})),
                _js(task.get("expected_output", {})), _js(task.get("artifacts", [])),
                _js(task.get("evidence", [])), task.get("confidence", 0.0),
                task.get("model_used"), task.get("cost_usd", 0.0),
                _js(task.get("tools_used", [])), task.get("retry_count", 0),
                task.get("max_retries", 2), task.get("error"),
                int(bool(task.get("requires_approval"))), task.get("approval"),
                task.get("version", 1), t, t, task.get("started_at"), task.get("finished_at"),
            ),
        )
        self.conn.commit()
        return task["task_id"]

    def get_task(self, task_id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        if not row:
            return None
        task = dict(row)
        for key in ("lineage", "dependencies", "inputs", "expected_output", "artifacts", "evidence", "tools_used"):
            task[key] = _ld(task[key])
        task["approval"] = _ld(task["approval"])
        task["requires_approval"] = bool(task["requires_approval"])
        return task

    def update_task(self, task_id: str, **fields) -> None:
        if not fields:
            return
        allowed = {
            "status", "priority", "inputs", "expected_output", "artifacts", "evidence",
            "confidence", "model_used", "cost_usd", "tools_used", "retry_count", "max_retries",
            "error", "approval", "version", "updated_at", "started_at", "finished_at", "requires_approval",
            # 3.x Phase 1：允许在 redo 时重连下游依赖（old task_id → 新版本 task_id），
            # 否则旧任务停在 BLOCKED/FAILED 会让下游 deps_ok 永远为假、链路永久停摆。
            "dependencies",
        }
        json_fields = {"inputs", "expected_output", "artifacts", "evidence", "tools_used",
                       "approval", "dependencies"}
        sets, values = [], []
        for key, value in fields.items():
            if key not in allowed:
                raise ValueError(f"task field not updatable: {key}")
            sets.append(f"{key}=?")
            values.append(_js(value) if key in json_fields else value)
        values.append(task_id)
        self.conn.execute(f"UPDATE tasks SET {', '.join(sets)} WHERE task_id=?", values)
        self.conn.commit()

    def list_tasks(self, project_id: str, status: str | None = None) -> list[dict]:
        if status:
            rows = self.conn.execute(
                "SELECT * FROM tasks WHERE project_id=? AND status=? ORDER BY priority DESC, created_at",
                (project_id, status),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM tasks WHERE project_id=? ORDER BY created_at", (project_id,)
            ).fetchall()
        return [self.get_task(r["task_id"]) for r in rows]

    def set_task_status(self, task_id: str, status: str, error: str | None = None) -> None:
        fields = {"status": status, "updated_at": now()}
        if error is not None:
            fields["error"] = error
        if status in ("RUNNING",):
            fields["started_at"] = now()
        if status in ("SUCCEEDED", "FAILED", "BLOCKED"):
            fields["finished_at"] = now()
        self.update_task(task_id, **fields)

    # ---------- events ----------
    def append_event(self, project_id: str, type_: str, actor: str, task_id: str | None = None,
                     payload: dict | None = None, human_visible: bool = False) -> int:
        cur = self.conn.execute(
            "INSERT INTO events(ts, project_id, task_id, type, actor, payload, human_visible) VALUES(?,?,?,?,?,?,?)",
            (now(), project_id, task_id, type_, actor, _js(payload or {}), int(human_visible)),
        )
        self.conn.commit()
        return cur.lastrowid

    def events_since(self, project_id: str, last_id: int = 0) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM events WHERE project_id=? AND event_id>? ORDER BY event_id", (project_id, last_id)
        ).fetchall()
        return [dict(r) | {"payload": _ld(r["payload"])} for r in rows]

    # ---------- artifacts ----------
    def insert_artifact(self, artifact: dict) -> str:
        self.conn.execute(
            "INSERT INTO artifacts(artifact_id, project_id, task_id, type, path, sha256, size,"
            " provenance, license, version, superseded_by, summary, created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                artifact["artifact_id"], artifact["project_id"], artifact.get("task_id"),
                artifact["type"], artifact["path"], artifact.get("sha256", ""),
                artifact.get("size", 0), _js(artifact.get("provenance", {})),
                artifact.get("license"), artifact.get("version", 1), artifact.get("superseded_by"),
                artifact.get("summary"), now(),
            ),
        )
        self.conn.commit()
        return artifact["artifact_id"]

    def get_artifact(self, artifact_id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM artifacts WHERE artifact_id=?", (artifact_id,)).fetchone()
        if not row:
            return None
        art = dict(row)
        art["provenance"] = _ld(art["provenance"])
        return art

    # ---------- decisions ----------
    def insert_decision(self, decision: dict) -> str:
        self.conn.execute(
            "INSERT INTO decisions(decision_id, project_id, node, made_by, state, rationale,"
            " artifact_snapshot, created_at) VALUES(?,?,?,?,?,?,?,?)",
            (
                decision["decision_id"], decision["project_id"], decision["node"],
                decision["made_by"], decision["state"], decision.get("rationale"),
                _js(decision.get("artifact_snapshot", [])), now(),
            ),
        )
        self.conn.commit()
        return decision["decision_id"]

    # ---------- memories ----------
    def put_memory(self, project_id: str | None, kind: str, key: str, content: str,
                   agent_role: str | None = None) -> int:
        cur = self.conn.execute(
            "INSERT INTO memories(project_id, kind, agent_role, key, content, created_at) VALUES(?,?,?,?,?,?)",
            (project_id, kind, agent_role, key, content, now()),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_memories(self, kind: str | None = None, project_id: str | None = None,
                     agent_role: str | None = None, limit: int = 20) -> list[dict]:
        sql, args = "SELECT * FROM memories WHERE 1=1", []
        if kind:
            sql += " AND kind=?"
            args.append(kind)
        if project_id is not None:
            sql += " AND (project_id=? OR project_id IS NULL)"
            args.append(project_id)
        if agent_role:
            sql += " AND agent_role=?"
            args.append(agent_role)
        sql += " ORDER BY memory_id DESC LIMIT ?"
        args.append(limit)
        return [dict(r) for r in self.conn.execute(sql, args).fetchall()]

    # ============ V2：事实核查数据层 ============

    # ---------- claims ----------
    def insert_claim(self, claim: dict) -> str:
        self.conn.execute(
            "INSERT INTO claims(claim_id, project_id, task_id, segment_ref, text, type, risk, markers,"
            " status, conclusion, confidence, source_count, human_review_required, created_at, updated_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                claim["claim_id"], claim["project_id"], claim.get("task_id"),
                claim.get("segment_ref"), claim["text"], claim.get("type", "FACT"),
                claim.get("risk", "MEDIUM"), _js(claim.get("markers", [])),
                claim.get("status", "UNVERIFIED"), claim.get("conclusion"),
                claim.get("confidence"), claim.get("source_count", 0),
                int(bool(claim.get("human_review_required"))), now(), now(),
            ),
        )
        self.conn.commit()
        return claim["claim_id"]

    def get_claim(self, claim_id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM claims WHERE claim_id=?", (claim_id,)).fetchone()
        if not row:
            return None
        claim = dict(row)
        claim["markers"] = _ld(claim["markers"])
        claim["human_review_required"] = bool(claim["human_review_required"])
        return claim

    def update_claim(self, claim_id: str, **fields) -> None:
        allowed = {"text", "type", "risk", "status", "conclusion", "confidence",
                   "source_count", "human_review_required", "segment_ref"}
        sets, values = [], []
        for key, value in fields.items():
            if key not in allowed:
                raise ValueError(f"claim field not updatable: {key}")
            sets.append(f"{key}=?")
            values.append(_js(value) if key == "markers" else value)
        sets.append("updated_at=?")
        values.append(now())
        values.append(claim_id)
        self.conn.execute(f"UPDATE claims SET {', '.join(sets)} WHERE claim_id=?", values)
        self.conn.commit()

    def list_claims(self, project_id: str, status: str | None = None,
                    risk: str | None = None) -> list[dict]:
        sql, args = "SELECT * FROM claims WHERE project_id=?", [project_id]
        if status:
            sql += " AND status=?"
            args.append(status)
        if risk:
            sql += " AND risk=?"
            args.append(risk)
        sql += " ORDER BY claim_id"
        claims = [dict(r) for r in self.conn.execute(sql, args).fetchall()]
        for c in claims:
            c["markers"] = _ld(c["markers"])
            c["human_review_required"] = bool(c["human_review_required"])
        return claims

    # ---------- evidence ----------
    def insert_evidence(self, ev: dict) -> str:
        self.conn.execute(
            "INSERT INTO evidence(evidence_id, project_id, source, source_type, publication_date,"
            " reliability, excerpt, url, added_by, task_id, support_level, created_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                ev["evidence_id"], ev["project_id"], ev["source"],
                ev.get("source_type", "unknown"), ev.get("publication_date"),
                ev.get("reliability", "unknown"), ev.get("excerpt"), ev.get("url"),
                ev.get("added_by"), ev.get("task_id"),
                ev.get("support_level"), now(),
            ),
        )
        self.conn.commit()
        return ev["evidence_id"]

    def get_evidence(self, evidence_id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM evidence WHERE evidence_id=?", (evidence_id,)).fetchone()
        return dict(row) if row else None

    def list_evidence(self, project_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM evidence WHERE project_id=? ORDER BY evidence_id", (project_id,)).fetchall()
        return [dict(r) for r in rows]

    def link_claim_evidence(self, claim_id: str, evidence_id: str) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO claim_evidence(claim_id, evidence_id) VALUES(?,?)",
            (claim_id, evidence_id))
        self.conn.commit()

    def evidence_for_claim(self, claim_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT e.* FROM claim_evidence ce JOIN evidence e ON ce.evidence_id=e.evidence_id"
            " WHERE ce.claim_id=? ORDER BY e.evidence_id", (claim_id,)).fetchall()
        return [dict(r) for r in rows]

    def claims_for_evidence(self, evidence_id: str) -> list[str]:
        rows = self.conn.execute(
            "SELECT claim_id FROM claim_evidence WHERE evidence_id=?", (evidence_id,)).fetchall()
        return [r["claim_id"] for r in rows]

    # ---------- conflicts ----------
    def insert_conflict(self, conflict: dict) -> str:
        self.conn.execute(
            "INSERT INTO conflicts(conflict_id, project_id, claim_id, source_a, source_b, description,"
            " authority_comparison, recency_comparison, recommended, confidence,"
            " human_review_required, status, created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                conflict["conflict_id"], conflict["project_id"], conflict["claim_id"],
                conflict.get("source_a"), conflict.get("source_b"), conflict.get("description"),
                conflict.get("authority_comparison"), conflict.get("recency_comparison"),
                conflict.get("recommended"), conflict.get("confidence"),
                int(bool(conflict.get("human_review_required", True))),
                conflict.get("status", "OPEN"), now(),
            ),
        )
        self.conn.commit()
        return conflict["conflict_id"]

    def get_conflict(self, conflict_id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM conflicts WHERE conflict_id=?", (conflict_id,)).fetchone()
        if not row:
            return None
        c = dict(row)
        c["human_review_required"] = bool(c["human_review_required"])
        return c

    def list_conflicts(self, project_id: str, status: str | None = None) -> list[dict]:
        sql, args = "SELECT * FROM conflicts WHERE project_id=?", [project_id]
        if status:
            sql += " AND status=?"
            args.append(status)
        sql += " ORDER BY conflict_id"
        conflicts = [dict(r) for r in self.conn.execute(sql, args).fetchall()]
        for c in conflicts:
            c["human_review_required"] = bool(c["human_review_required"])
        return conflicts

    def update_conflict(self, conflict_id: str, **fields) -> None:
        allowed = {"status", "recommended", "confidence", "human_review_required"}
        sets, values = [], []
        for key, value in fields.items():
            if key not in allowed:
                raise ValueError(f"conflict field not updatable: {key}")
            sets.append(f"{key}=?")
            values.append(value)
        values.append(conflict_id)
        self.conn.execute(f"UPDATE conflicts SET {', '.join(sets)} WHERE conflict_id=?", values)
        self.conn.commit()

    # ---------- V2.1 LLM 语义判定缓存/审计（附加表） ----------
    def get_llm_judge_row(self, cache_key: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM llm_judge_cache WHERE cache_key=?", (cache_key,)).fetchone()
        return dict(row) if row else None

    def put_llm_judge_row(self, rec: dict) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO llm_judge_cache(cache_key, claim_text, evidence_url,"
            " rule_label, llm_label, reason, model, tier, prompt_version, fallback_reason,"
            " tokens_in, tokens_out, cost_usd, latency_ms, cache_hit, created_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                rec.get("cache_key"), rec.get("claim_text"), rec.get("evidence_url"),
                rec.get("rule_label"), rec.get("llm_label"), rec.get("reason"),
                rec.get("model"), rec.get("tier", "F"), rec.get("prompt_version"),
                rec.get("fallback_reason"), int(rec.get("tokens_in", 0) or 0),
                int(rec.get("tokens_out", 0) or 0), float(rec.get("cost_usd", 0.0) or 0),
                int(rec.get("latency_ms", 0) or 0), int(bool(rec.get("cache_hit"))), now(),
            ),
        )
        self.conn.commit()

    def list_llm_judge_rows(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM llm_judge_cache ORDER BY created_at").fetchall()]

    # ---------- changelog ----------
    def insert_changelog(self, project_id: str, target_type: str, target_id: str,
                         changed_by: str, reason: str = "", before_summary: str = "",
                         after_summary: str = "", human_confirmed: bool = False) -> int:
        cur = self.conn.execute(
            "INSERT INTO changelog(project_id, target_type, target_id, changed_by, reason,"
            " before_summary, after_summary, human_confirmed, created_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (project_id, target_type, target_id, changed_by, reason,
             before_summary, after_summary, int(human_confirmed), now()))
        self.conn.commit()
        return cur.lastrowid

    def list_changelog(self, project_id: str | None = None, target_type: str | None = None,
                       target_id: str | None = None, limit: int = 100) -> list[dict]:
        sql, args = "SELECT * FROM changelog WHERE 1=1", []
        if project_id is not None:
            sql += " AND project_id=?"
            args.append(project_id)
        if target_type:
            sql += " AND target_type=?"
            args.append(target_type)
        if target_id:
            sql += " AND target_id=?"
            args.append(target_id)
        sql += " ORDER BY change_id DESC LIMIT ?"
        args.append(limit)
        rows = [dict(r) for r in self.conn.execute(sql, args).fetchall()]
        for r in rows:
            r["human_confirmed"] = bool(r["human_confirmed"])
        return rows
