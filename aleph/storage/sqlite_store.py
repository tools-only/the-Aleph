from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from aleph.lib.ids import create_id


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dump_json(value) -> str:
    return json.dumps(value if value is not None else None, ensure_ascii=False)


def _parse_json(value: str | None, fallback):
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


class SqliteStore:
    def __init__(
        self,
        root_dir: str | Path | None = None,
        db_path: str | Path | None = None,
        now=None,
    ) -> None:
        self.root_dir = Path(root_dir or Path.cwd())
        self.data_dir = self.root_dir / "data"
        self.logs_dir = self.data_dir / "logs"
        self.db_path = db_path if db_path == ":memory:" else (Path(db_path) if db_path else self.data_dir / "aleph.db")
        self.now = now or _now

        self.logs_dir.mkdir(parents=True, exist_ok=True)
        if self.db_path != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON;")
        self._init_schema()

    def close(self) -> None:
        self.connection.close()

    def _init_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS client_blueprints (
              id TEXT PRIMARY KEY,
              display_name TEXT NOT NULL,
              role TEXT NOT NULL,
              system_prompt TEXT NOT NULL,
              adapter_kind TEXT NOT NULL,
              boundaries_json TEXT NOT NULL,
              declared_capability_json TEXT NOT NULL,
              shared_memory_policy_json TEXT NOT NULL,
              tools_json TEXT NOT NULL,
              handoff_rules_json TEXT NOT NULL,
              runtime_preferences_json TEXT NOT NULL,
              metadata_json TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS client_instances (
              id TEXT PRIMARY KEY,
              blueprint_id TEXT NOT NULL,
              adapter_kind TEXT NOT NULL,
              status TEXT NOT NULL,
              runtime_signals_json TEXT NOT NULL,
              agent_native_state_json TEXT NOT NULL,
              metadata_json TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY(blueprint_id) REFERENCES client_blueprints(id)
            );

            CREATE TABLE IF NOT EXISTS sessions (
              id TEXT PRIMARY KEY,
              title TEXT NOT NULL,
              status TEXT NOT NULL,
              foreground_client_id TEXT NOT NULL,
              foreground_reason TEXT NOT NULL,
              memory_epoch INTEGER NOT NULL,
              tool_epoch INTEGER NOT NULL,
              policy_epoch INTEGER NOT NULL,
              metadata_json TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS session_turns (
              id TEXT PRIMARY KEY,
              session_id TEXT NOT NULL,
              client_id TEXT,
              role TEXT NOT NULL,
              content TEXT NOT NULL,
              visibility TEXT NOT NULL,
              source_event_id TEXT,
              metadata_json TEXT NOT NULL,
              created_at TEXT NOT NULL,
              FOREIGN KEY(session_id) REFERENCES sessions(id)
            );

            CREATE TABLE IF NOT EXISTS session_events (
              id TEXT PRIMARY KEY,
              session_id TEXT NOT NULL,
              channel TEXT NOT NULL,
              event_kind TEXT NOT NULL,
              source TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              created_at TEXT NOT NULL,
              FOREIGN KEY(session_id) REFERENCES sessions(id)
            );

            CREATE TABLE IF NOT EXISTS memory_records (
              id TEXT PRIMARY KEY,
              session_id TEXT NOT NULL,
              layer TEXT NOT NULL,
              owner_client_id TEXT,
              domain TEXT,
              kind TEXT NOT NULL,
              content TEXT NOT NULL,
              write_mode TEXT NOT NULL,
              metadata_json TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY(session_id) REFERENCES sessions(id)
            );

            CREATE TABLE IF NOT EXISTS switch_logs (
              id TEXT PRIMARY KEY,
              session_id TEXT NOT NULL,
              from_client_id TEXT,
              to_client_id TEXT NOT NULL,
              reason TEXT NOT NULL,
              trigger TEXT NOT NULL,
              explanation TEXT NOT NULL,
              handoff_summary TEXT NOT NULL,
              created_at TEXT NOT NULL,
              FOREIGN KEY(session_id) REFERENCES sessions(id)
            );

            CREATE TABLE IF NOT EXISTS projection_cache (
              cache_key TEXT PRIMARY KEY,
              projection_type TEXT NOT NULL,
              session_id TEXT NOT NULL,
              client_id TEXT NOT NULL,
              value_json TEXT NOT NULL,
              metadata_json TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS prewarm_jobs (
              id TEXT PRIMARY KEY,
              session_id TEXT NOT NULL,
              client_id TEXT NOT NULL,
              status TEXT NOT NULL,
              reason TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            """
        )
        self.connection.commit()

    def _append_jsonl(self, filename: str, payload: dict) -> None:
        path = self.logs_dir / filename
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def save_client_blueprint(self, blueprint: dict) -> dict:
        now = self.now()
        current = self.get_client_blueprint(blueprint["id"])
        created_at = current["created_at"] if current else now
        self.connection.execute(
            """
            INSERT INTO client_blueprints (
              id, display_name, role, system_prompt, adapter_kind, boundaries_json,
              declared_capability_json, shared_memory_policy_json, tools_json,
              handoff_rules_json, runtime_preferences_json, metadata_json,
              created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              display_name = excluded.display_name,
              role = excluded.role,
              system_prompt = excluded.system_prompt,
              adapter_kind = excluded.adapter_kind,
              boundaries_json = excluded.boundaries_json,
              declared_capability_json = excluded.declared_capability_json,
              shared_memory_policy_json = excluded.shared_memory_policy_json,
              tools_json = excluded.tools_json,
              handoff_rules_json = excluded.handoff_rules_json,
              runtime_preferences_json = excluded.runtime_preferences_json,
              metadata_json = excluded.metadata_json,
              updated_at = excluded.updated_at
            """,
            (
                blueprint["id"],
                blueprint["display_name"],
                blueprint["role"],
                blueprint["system_prompt"],
                blueprint["adapter_kind"],
                _dump_json(blueprint["boundaries"]),
                _dump_json(blueprint["declared_capability"]),
                _dump_json(blueprint["shared_memory_policy"]),
                _dump_json(blueprint["tools"]),
                _dump_json(blueprint["handoff_rules"]),
                _dump_json(blueprint["runtime_preferences"]),
                _dump_json(blueprint["metadata"]),
                created_at,
                now,
            ),
        )
        self.connection.commit()
        return self.get_client_blueprint(blueprint["id"])

    def _map_client_blueprint(self, row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "display_name": row["display_name"],
            "role": row["role"],
            "system_prompt": row["system_prompt"],
            "adapter_kind": row["adapter_kind"],
            "boundaries": _parse_json(row["boundaries_json"], []),
            "declared_capability": _parse_json(row["declared_capability_json"], {}),
            "shared_memory_policy": _parse_json(row["shared_memory_policy_json"], {}),
            "tools": _parse_json(row["tools_json"], []),
            "handoff_rules": _parse_json(row["handoff_rules_json"], {}),
            "runtime_preferences": _parse_json(row["runtime_preferences_json"], {}),
            "metadata": _parse_json(row["metadata_json"], {}),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def get_client_blueprint(self, client_id: str) -> dict | None:
        row = self.connection.execute(
            "SELECT * FROM client_blueprints WHERE id = ?",
            (client_id,),
        ).fetchone()
        return self._map_client_blueprint(row) if row else None

    def list_client_blueprints(self) -> list[dict]:
        rows = self.connection.execute(
            "SELECT * FROM client_blueprints ORDER BY created_at ASC"
        ).fetchall()
        return [self._map_client_blueprint(row) for row in rows]

    def save_client_instance(self, instance: dict) -> dict:
        now = self.now()
        current = self.get_client_instance(instance["id"])
        created_at = current["created_at"] if current else now
        self.connection.execute(
            """
            INSERT INTO client_instances (
              id, blueprint_id, adapter_kind, status, runtime_signals_json,
              agent_native_state_json, metadata_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              blueprint_id = excluded.blueprint_id,
              adapter_kind = excluded.adapter_kind,
              status = excluded.status,
              runtime_signals_json = excluded.runtime_signals_json,
              agent_native_state_json = excluded.agent_native_state_json,
              metadata_json = excluded.metadata_json,
              updated_at = excluded.updated_at
            """,
            (
                instance["id"],
                instance["blueprint_id"],
                instance["adapter_kind"],
                instance.get("status", "ready"),
                _dump_json(instance.get("runtime_signals", {})),
                _dump_json(instance.get("agent_native_state", {})),
                _dump_json(instance.get("metadata", {})),
                created_at,
                now,
            ),
        )
        self.connection.commit()
        return self.get_client_instance(instance["id"])

    def _map_client_instance(self, row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "blueprint_id": row["blueprint_id"],
            "adapter_kind": row["adapter_kind"],
            "status": row["status"],
            "runtime_signals": _parse_json(row["runtime_signals_json"], {}),
            "agent_native_state": _parse_json(row["agent_native_state_json"], {}),
            "metadata": _parse_json(row["metadata_json"], {}),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def get_client_instance(self, client_id: str) -> dict | None:
        row = self.connection.execute(
            "SELECT * FROM client_instances WHERE id = ?",
            (client_id,),
        ).fetchone()
        return self._map_client_instance(row) if row else None

    def list_client_instances(self) -> list[dict]:
        rows = self.connection.execute(
            "SELECT * FROM client_instances ORDER BY created_at ASC"
        ).fetchall()
        return [self._map_client_instance(row) for row in rows]

    def update_client_runtime_state(
        self,
        client_id: str,
        *,
        runtime_signals_patch: dict | None = None,
        agent_native_state_patch: dict | None = None,
    ) -> dict:
        current = self.get_client_instance(client_id)
        if not current:
            raise ValueError(f"Client instance '{client_id}' not found")
        runtime_signals = {**current["runtime_signals"], **(runtime_signals_patch or {})}
        agent_native_state = {**current["agent_native_state"], **(agent_native_state_patch or {})}
        self.connection.execute(
            """
            UPDATE client_instances
            SET runtime_signals_json = ?, agent_native_state_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                _dump_json(runtime_signals),
                _dump_json(agent_native_state),
                self.now(),
                client_id,
            ),
        )
        self.connection.commit()
        return self.get_client_instance(client_id)

    def create_session(self, payload: dict) -> dict:
        now = self.now()
        session = {
            "id": create_id("session"),
            "title": payload.get("title", "Aleph Session"),
            "status": payload.get("status", "active"),
            "foreground_client_id": payload["foreground_client_id"],
            "foreground_reason": payload.get("foreground_reason", "bootstrap"),
            "memory_epoch": payload.get("memory_epoch", 1),
            "tool_epoch": payload.get("tool_epoch", 1),
            "policy_epoch": payload.get("policy_epoch", 1),
            "metadata": payload.get("metadata", {}),
            "created_at": now,
            "updated_at": now,
        }
        self.connection.execute(
            """
            INSERT INTO sessions (
              id, title, status, foreground_client_id, foreground_reason,
              memory_epoch, tool_epoch, policy_epoch, metadata_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session["id"],
                session["title"],
                session["status"],
                session["foreground_client_id"],
                session["foreground_reason"],
                session["memory_epoch"],
                session["tool_epoch"],
                session["policy_epoch"],
                _dump_json(session["metadata"]),
                session["created_at"],
                session["updated_at"],
            ),
        )
        self.connection.commit()
        return session

    def _map_session(self, row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "title": row["title"],
            "status": row["status"],
            "foreground_client_id": row["foreground_client_id"],
            "foreground_reason": row["foreground_reason"],
            "memory_epoch": row["memory_epoch"],
            "tool_epoch": row["tool_epoch"],
            "policy_epoch": row["policy_epoch"],
            "metadata": _parse_json(row["metadata_json"], {}),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def get_session(self, session_id: str) -> dict | None:
        row = self.connection.execute(
            "SELECT * FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        return self._map_session(row) if row else None

    def get_latest_session(self) -> dict | None:
        row = self.connection.execute(
            "SELECT * FROM sessions ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        return self._map_session(row) if row else None

    def set_foreground_client(self, session_id: str, client_id: str, reason: str) -> dict:
        self.connection.execute(
            """
            UPDATE sessions
            SET foreground_client_id = ?, foreground_reason = ?, updated_at = ?
            WHERE id = ?
            """,
            (client_id, reason, self.now(), session_id),
        )
        self.connection.commit()
        return self.get_session(session_id)

    def bump_session_epochs(
        self,
        session_id: str,
        *,
        memory_delta: int = 0,
        tool_delta: int = 0,
        policy_delta: int = 0,
    ) -> dict:
        current = self.get_session(session_id)
        if not current:
            raise ValueError(f"Session '{session_id}' not found")
        self.connection.execute(
            """
            UPDATE sessions
            SET memory_epoch = ?, tool_epoch = ?, policy_epoch = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                current["memory_epoch"] + memory_delta,
                current["tool_epoch"] + tool_delta,
                current["policy_epoch"] + policy_delta,
                self.now(),
                session_id,
            ),
        )
        self.connection.commit()
        return self.get_session(session_id)

    def append_session_turn(self, payload: dict) -> dict:
        record = {
            "id": create_id("turn"),
            "session_id": payload["session_id"],
            "client_id": payload.get("client_id"),
            "role": payload["role"],
            "content": payload["content"],
            "visibility": payload.get("visibility", "private"),
            "source_event_id": payload.get("source_event_id"),
            "metadata": payload.get("metadata", {}),
            "created_at": payload.get("created_at", self.now()),
        }
        self.connection.execute(
            """
            INSERT INTO session_turns (
              id, session_id, client_id, role, content, visibility,
              source_event_id, metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["id"],
                record["session_id"],
                record["client_id"],
                record["role"],
                record["content"],
                record["visibility"],
                record["source_event_id"],
                _dump_json(record["metadata"]),
                record["created_at"],
            ),
        )
        self.connection.commit()
        return record

    def list_session_turns(
        self,
        session_id: str,
        *,
        client_id: str | None = None,
        limit: int = 12,
    ) -> list[dict]:
        if client_id:
            rows = self.connection.execute(
                """
                SELECT * FROM session_turns
                WHERE session_id = ? AND client_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (session_id, client_id, limit),
            ).fetchall()
        else:
            rows = self.connection.execute(
                """
                SELECT * FROM session_turns
                WHERE session_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "session_id": row["session_id"],
                "client_id": row["client_id"],
                "role": row["role"],
                "content": row["content"],
                "visibility": row["visibility"],
                "source_event_id": row["source_event_id"],
                "metadata": _parse_json(row["metadata_json"], {}),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def append_session_event(self, payload: dict) -> dict:
        record = {
            "id": create_id("event"),
            "session_id": payload["session_id"],
            "channel": payload["channel"],
            "event_kind": payload["event_kind"],
            "source": payload.get("source", "aleph"),
            "payload": payload.get("payload", {}),
            "created_at": payload.get("created_at", self.now()),
        }
        self.connection.execute(
            """
            INSERT INTO session_events (
              id, session_id, channel, event_kind, source, payload_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["id"],
                record["session_id"],
                record["channel"],
                record["event_kind"],
                record["source"],
                _dump_json(record["payload"]),
                record["created_at"],
            ),
        )
        self.connection.commit()
        self._append_jsonl(f"{record['channel']}-events.jsonl", record)
        return record

    def list_session_events(
        self,
        session_id: str,
        *,
        channel: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        if channel:
            rows = self.connection.execute(
                """
                SELECT * FROM session_events
                WHERE session_id = ? AND channel = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (session_id, channel, limit),
            ).fetchall()
        else:
            rows = self.connection.execute(
                """
                SELECT * FROM session_events
                WHERE session_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "session_id": row["session_id"],
                "channel": row["channel"],
                "event_kind": row["event_kind"],
                "source": row["source"],
                "payload": _parse_json(row["payload_json"], {}),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def save_memory(self, payload: dict) -> dict:
        now = self.now()
        record = {
            "id": create_id("mem"),
            "session_id": payload["session_id"],
            "layer": payload["layer"],
            "owner_client_id": payload.get("owner_client_id"),
            "domain": payload.get("domain"),
            "kind": payload.get("kind", "note"),
            "content": payload["content"],
            "write_mode": payload.get("write_mode", "append"),
            "metadata": payload.get("metadata", {}),
            "created_at": now,
            "updated_at": now,
        }
        self.connection.execute(
            """
            INSERT INTO memory_records (
              id, session_id, layer, owner_client_id, domain, kind, content, write_mode,
              metadata_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["id"],
                record["session_id"],
                record["layer"],
                record["owner_client_id"],
                record["domain"],
                record["kind"],
                record["content"],
                record["write_mode"],
                _dump_json(record["metadata"]),
                record["created_at"],
                record["updated_at"],
            ),
        )
        self.connection.commit()

        if record["layer"] in {"private", "shared", "handoff"}:
            self.bump_session_epochs(record["session_id"], memory_delta=1)
        return record

    def list_memories(self, filter_payload: dict) -> list[dict]:
        session_id = filter_payload["session_id"]
        limit = filter_payload.get("limit", 20)
        layer = filter_payload.get("layer")
        params: list[object] = [session_id]
        clauses = ["session_id = ?"]
        if layer:
            clauses.append("layer = ?")
            params.append(layer)
        owner_client_id = filter_payload.get("owner_client_id")
        if owner_client_id is not None:
            clauses.append("owner_client_id = ?")
            params.append(owner_client_id)
        domain = filter_payload.get("domain")
        if domain is not None:
            clauses.append("domain = ?")
            params.append(domain)
        domains = filter_payload.get("domains")
        if domains:
            placeholders = ", ".join("?" for _ in domains)
            clauses.append(f"domain IN ({placeholders})")
            params.extend(domains)
        query = f"""
            SELECT * FROM memory_records
            WHERE {" AND ".join(clauses)}
            ORDER BY created_at DESC
            LIMIT ?
        """
        params.append(limit)
        rows = self.connection.execute(query, tuple(params)).fetchall()
        return [
            {
                "id": row["id"],
                "session_id": row["session_id"],
                "layer": row["layer"],
                "owner_client_id": row["owner_client_id"],
                "domain": row["domain"],
                "kind": row["kind"],
                "content": row["content"],
                "write_mode": row["write_mode"],
                "metadata": _parse_json(row["metadata_json"], {}),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

    def record_switch(self, payload: dict) -> dict:
        record = {
            "id": create_id("switch"),
            "session_id": payload["session_id"],
            "from_client_id": payload.get("from_client_id"),
            "to_client_id": payload["to_client_id"],
            "reason": payload["reason"],
            "trigger": payload.get("trigger", "daemon"),
            "explanation": payload["explanation"],
            "handoff_summary": payload["handoff_summary"],
            "created_at": payload.get("created_at", self.now()),
        }
        self.connection.execute(
            """
            INSERT INTO switch_logs (
              id, session_id, from_client_id, to_client_id, reason,
              trigger, explanation, handoff_summary, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["id"],
                record["session_id"],
                record["from_client_id"],
                record["to_client_id"],
                record["reason"],
                record["trigger"],
                record["explanation"],
                record["handoff_summary"],
                record["created_at"],
            ),
        )
        self.connection.commit()
        self._append_jsonl("switch-log.jsonl", record)
        return record

    def list_switch_logs(self, session_id: str, limit: int = 10) -> list[dict]:
        rows = self.connection.execute(
            """
            SELECT * FROM switch_logs
            WHERE session_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (session_id, limit),
        ).fetchall()
        return [
            {
                "id": row["id"],
                "session_id": row["session_id"],
                "from_client_id": row["from_client_id"],
                "to_client_id": row["to_client_id"],
                "reason": row["reason"],
                "trigger": row["trigger"],
                "explanation": row["explanation"],
                "handoff_summary": row["handoff_summary"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def save_projection_cache(self, payload: dict) -> dict:
        now = self.now()
        self.connection.execute(
            """
            INSERT INTO projection_cache (
              cache_key, projection_type, session_id, client_id, value_json,
              metadata_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
              projection_type = excluded.projection_type,
              session_id = excluded.session_id,
              client_id = excluded.client_id,
              value_json = excluded.value_json,
              metadata_json = excluded.metadata_json,
              updated_at = excluded.updated_at
            """,
            (
                payload["cache_key"],
                payload["projection_type"],
                payload["session_id"],
                payload["client_id"],
                _dump_json(payload["value"]),
                _dump_json(payload.get("metadata", {})),
                now,
                now,
            ),
        )
        self.connection.commit()
        return self.get_projection_cache(payload["cache_key"])

    def get_projection_cache(self, cache_key: str) -> dict | None:
        row = self.connection.execute(
            "SELECT * FROM projection_cache WHERE cache_key = ?",
            (cache_key,),
        ).fetchone()
        if not row:
            return None
        return {
            "cache_key": row["cache_key"],
            "projection_type": row["projection_type"],
            "session_id": row["session_id"],
            "client_id": row["client_id"],
            "value": _parse_json(row["value_json"], {}),
            "metadata": _parse_json(row["metadata_json"], {}),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def create_prewarm_job(self, payload: dict) -> dict:
        now = self.now()
        record = {
            "id": create_id("prewarm"),
            "session_id": payload["session_id"],
            "client_id": payload["client_id"],
            "status": payload.get("status", "ready"),
            "reason": payload["reason"],
            "payload": payload.get("payload", {}),
            "created_at": now,
            "updated_at": now,
        }
        self.connection.execute(
            """
            INSERT INTO prewarm_jobs (
              id, session_id, client_id, status, reason, payload_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["id"],
                record["session_id"],
                record["client_id"],
                record["status"],
                record["reason"],
                _dump_json(record["payload"]),
                record["created_at"],
                record["updated_at"],
            ),
        )
        self.connection.commit()
        return record

    def list_prewarm_jobs(self, session_id: str, limit: int = 10) -> list[dict]:
        rows = self.connection.execute(
            """
            SELECT * FROM prewarm_jobs
            WHERE session_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (session_id, limit),
        ).fetchall()
        return [
            {
                "id": row["id"],
                "session_id": row["session_id"],
                "client_id": row["client_id"],
                "status": row["status"],
                "reason": row["reason"],
                "payload": _parse_json(row["payload_json"], {}),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]
