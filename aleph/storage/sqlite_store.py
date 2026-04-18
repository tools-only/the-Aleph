from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from aleph.lib.ids import create_id


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_json(value: str | None, fallback):
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _dump_json(value) -> str:
    return json.dumps(value if value is not None else None, ensure_ascii=False)


class SqliteStore:
    def __init__(self, root_dir: str | Path | None = None, db_path: str | Path | None = None, now=None) -> None:
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
            CREATE TABLE IF NOT EXISTS client_profiles (
              id TEXT PRIMARY KEY,
              persona_id TEXT NOT NULL,
              display_name TEXT NOT NULL,
              voice TEXT NOT NULL,
              specialties_json TEXT NOT NULL,
              boundaries_json TEXT NOT NULL,
              permissions_json TEXT NOT NULL,
              shared_domains_json TEXT NOT NULL,
              readable_shared_domains_json TEXT NOT NULL,
              writable_shared_domains_json TEXT NOT NULL,
              allowed_actions_json TEXT NOT NULL,
              request_only_actions_json TEXT NOT NULL,
              allowed_tools_json TEXT NOT NULL,
              isolation_json TEXT NOT NULL,
              metadata_json TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS client_sessions (
              id TEXT PRIMARY KEY,
              client_id TEXT NOT NULL,
              status TEXT NOT NULL,
              handoff_summary TEXT,
              last_runtime_lens TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS client_turns (
              id TEXT PRIMARY KEY,
              client_id TEXT NOT NULL,
              session_id TEXT NOT NULL,
              role TEXT NOT NULL,
              content TEXT NOT NULL,
              visibility TEXT NOT NULL,
              source_event_id TEXT,
              metadata_json TEXT NOT NULL,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS memories (
              id TEXT PRIMARY KEY,
              layer TEXT NOT NULL,
              persona_id TEXT,
              domain TEXT,
              kind TEXT NOT NULL,
              content TEXT NOT NULL,
              metadata_json TEXT NOT NULL,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS reality_threads (
              id TEXT PRIMARY KEY,
              title TEXT NOT NULL,
              summary TEXT NOT NULL,
              active_scene TEXT NOT NULL,
              open_loops_json TEXT NOT NULL,
              metadata_json TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS reality_events (
              id TEXT PRIMARY KEY,
              thread_id TEXT NOT NULL,
              type TEXT NOT NULL,
              source TEXT NOT NULL,
              summary TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS consequences (
              id TEXT PRIMARY KEY,
              thread_id TEXT NOT NULL,
              kind TEXT NOT NULL,
              source_event_id TEXT NOT NULL,
              summary TEXT NOT NULL,
              status TEXT NOT NULL,
              weight REAL NOT NULL,
              scope TEXT NOT NULL,
              handoff_hint TEXT NOT NULL,
              metadata_json TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS switch_logs (
              id TEXT PRIMARY KEY,
              from_client_id TEXT,
              to_client_id TEXT NOT NULL,
              from_persona_id TEXT,
              to_persona_id TEXT NOT NULL,
              reason TEXT NOT NULL,
              explanation TEXT NOT NULL,
              handoff_summary TEXT NOT NULL,
              trigger TEXT NOT NULL,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS foreground_control (
              slot TEXT PRIMARY KEY,
              thread_id TEXT NOT NULL,
              client_id TEXT NOT NULL,
              session_id TEXT NOT NULL,
              reason TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            """
        )
        self.connection.commit()

    def _append_jsonl(self, filename: str, payload: dict) -> None:
        path = self.logs_dir / filename
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def save_client_profile(self, profile: dict) -> None:
        now = self.now()
        self.connection.execute(
            """
            INSERT INTO client_profiles (
              id, persona_id, display_name, voice, specialties_json, boundaries_json,
              permissions_json, shared_domains_json, readable_shared_domains_json,
              writable_shared_domains_json, allowed_actions_json,
              request_only_actions_json, allowed_tools_json, isolation_json,
              metadata_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              persona_id = excluded.persona_id,
              display_name = excluded.display_name,
              voice = excluded.voice,
              specialties_json = excluded.specialties_json,
              boundaries_json = excluded.boundaries_json,
              permissions_json = excluded.permissions_json,
              shared_domains_json = excluded.shared_domains_json,
              readable_shared_domains_json = excluded.readable_shared_domains_json,
              writable_shared_domains_json = excluded.writable_shared_domains_json,
              allowed_actions_json = excluded.allowed_actions_json,
              request_only_actions_json = excluded.request_only_actions_json,
              allowed_tools_json = excluded.allowed_tools_json,
              isolation_json = excluded.isolation_json,
              metadata_json = excluded.metadata_json,
              updated_at = excluded.updated_at
            """,
            (
                profile["id"],
                profile["persona_id"],
                profile["display_name"],
                profile["voice"],
                _dump_json(profile["specialties"]),
                _dump_json(profile["boundaries"]),
                _dump_json(profile["permissions"]),
                _dump_json(profile["shared_domains"]),
                _dump_json(profile["capabilities"]["readable_shared_domains"]),
                _dump_json(profile["capabilities"]["writable_shared_domains"]),
                _dump_json(profile["capabilities"]["allowed_actions"]),
                _dump_json(profile["capabilities"]["request_only_actions"]),
                _dump_json(profile["capabilities"]["allowed_tools"]),
                _dump_json(profile["isolation"]),
                _dump_json(profile["metadata"]),
                now,
                now,
            ),
        )
        self.connection.commit()

    def _map_client_profile(self, row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "persona_id": row["persona_id"],
            "display_name": row["display_name"],
            "name": row["display_name"],
            "voice": row["voice"],
            "specialties": _parse_json(row["specialties_json"], []),
            "boundaries": _parse_json(row["boundaries_json"], []),
            "permissions": _parse_json(row["permissions_json"], []),
            "shared_domains": _parse_json(row["shared_domains_json"], []),
            "capabilities": {
                "readable_shared_domains": _parse_json(row["readable_shared_domains_json"], []),
                "writable_shared_domains": _parse_json(row["writable_shared_domains_json"], []),
                "allowed_actions": _parse_json(row["allowed_actions_json"], []),
                "request_only_actions": _parse_json(row["request_only_actions_json"], []),
                "allowed_tools": _parse_json(row["allowed_tools_json"], []),
            },
            "isolation": _parse_json(row["isolation_json"], {}),
            "metadata": _parse_json(row["metadata_json"], {}),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def get_client_profile(self, client_id: str) -> dict | None:
        row = self.connection.execute(
            "SELECT * FROM client_profiles WHERE id = ?", (client_id,)
        ).fetchone()
        return self._map_client_profile(row) if row else None

    def list_client_profiles(self) -> list[dict]:
        rows = self.connection.execute(
            "SELECT * FROM client_profiles ORDER BY created_at ASC"
        ).fetchall()
        return [self._map_client_profile(row) for row in rows]

    def create_client_session(self, payload: dict) -> dict:
        now = self.now()
        session = {
            "id": create_id("client_session"),
            "client_id": payload["client_id"],
            "status": payload.get("status", "standby"),
            "handoff_summary": payload.get("handoff_summary", ""),
            "last_runtime_lens": payload.get("last_runtime_lens", ""),
            "created_at": now,
            "updated_at": now,
        }
        self.connection.execute(
            """
            INSERT INTO client_sessions (
              id, client_id, status, handoff_summary, last_runtime_lens, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session["id"],
                session["client_id"],
                session["status"],
                session["handoff_summary"],
                session["last_runtime_lens"],
                session["created_at"],
                session["updated_at"],
            ),
        )
        self.connection.commit()
        return session

    def append_client_turn(self, payload: dict) -> dict:
        record = {
            "id": create_id("client_turn"),
            "client_id": payload["client_id"],
            "session_id": payload["session_id"],
            "role": payload["role"],
            "content": payload["content"],
            "visibility": payload.get("visibility", "private"),
            "source_event_id": payload.get("source_event_id"),
            "metadata": payload.get("metadata", {}),
            "created_at": payload.get("created_at", self.now()),
        }
        self.connection.execute(
            """
            INSERT INTO client_turns (
              id, client_id, session_id, role, content, visibility,
              source_event_id, metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["id"],
                record["client_id"],
                record["session_id"],
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

    def list_client_turns(self, client_id: str, limit: int = 12) -> list[dict]:
        rows = self.connection.execute(
            """
            SELECT * FROM client_turns
            WHERE client_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (client_id, limit),
        ).fetchall()
        return [
            {
                "id": row["id"],
                "client_id": row["client_id"],
                "session_id": row["session_id"],
                "role": row["role"],
                "content": row["content"],
                "visibility": row["visibility"],
                "source_event_id": row["source_event_id"],
                "metadata": _parse_json(row["metadata_json"], {}),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def save_memory(self, payload: dict) -> dict:
        record = {
            "id": create_id("mem"),
            "layer": payload["layer"],
            "persona_id": payload.get("persona_id"),
            "domain": payload.get("domain"),
            "kind": payload.get("kind", "note"),
            "content": payload["content"],
            "metadata": payload.get("metadata", {}),
            "created_at": payload.get("created_at", self.now()),
        }
        self.connection.execute(
            """
            INSERT INTO memories (
              id, layer, persona_id, domain, kind, content, metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["id"],
                record["layer"],
                record["persona_id"],
                record["domain"],
                record["kind"],
                record["content"],
                _dump_json(record["metadata"]),
                record["created_at"],
            ),
        )
        self.connection.commit()
        return record

    def list_memories(self, filter_payload: dict | None = None) -> list[dict]:
        filter_payload = filter_payload or {}
        limit = filter_payload.get("limit", 20)
        layer = filter_payload.get("layer")
        if layer == "shared":
            domains = filter_payload.get("domains", [])
            if not domains:
                return []
            placeholders = ", ".join("?" for _ in domains)
            rows = self.connection.execute(
                f"""
                SELECT * FROM memories
                WHERE layer = 'shared' AND domain IN ({placeholders})
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (*domains, limit),
            ).fetchall()
        elif layer == "private":
            rows = self.connection.execute(
                """
                SELECT * FROM memories
                WHERE layer = 'private' AND persona_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (filter_payload["persona_id"], limit),
            ).fetchall()
        elif layer == "reality-note":
            rows = self.connection.execute(
                """
                SELECT * FROM memories
                WHERE layer = 'reality-note'
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        else:
            rows = self.connection.execute(
                "SELECT * FROM memories ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [
            {
                "id": row["id"],
                "layer": row["layer"],
                "persona_id": row["persona_id"],
                "domain": row["domain"],
                "kind": row["kind"],
                "content": row["content"],
                "metadata": _parse_json(row["metadata_json"], {}),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def create_reality_thread(self, payload: dict | None = None) -> dict:
        payload = payload or {}
        now = self.now()
        thread = {
            "id": create_id("thread"),
            "title": payload.get("title", "Aleph Reality Thread"),
            "summary": payload.get("summary", "Reality is active and continuous."),
            "active_scene": payload.get("active_scene", payload.get("activeScene", "The conversation has just begun.")),
            "open_loops": payload.get("open_loops", payload.get("openLoops", [])),
            "metadata": payload.get("metadata", {}),
            "created_at": now,
            "updated_at": now,
        }
        self.connection.execute(
            """
            INSERT INTO reality_threads (
              id, title, summary, active_scene, open_loops_json, metadata_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                thread["id"],
                thread["title"],
                thread["summary"],
                thread["active_scene"],
                _dump_json(thread["open_loops"]),
                _dump_json(thread["metadata"]),
                thread["created_at"],
                thread["updated_at"],
            ),
        )
        self.connection.commit()
        return thread

    def get_latest_reality_thread(self) -> dict | None:
        row = self.connection.execute(
            "SELECT * FROM reality_threads ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "title": row["title"],
            "summary": row["summary"],
            "active_scene": row["active_scene"],
            "open_loops": _parse_json(row["open_loops_json"], []),
            "metadata": _parse_json(row["metadata_json"], {}),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def update_reality_thread(self, thread_id: str, patch: dict) -> dict:
        current = self.get_latest_reality_thread()
        if not current or current["id"] != thread_id:
            raise ValueError(f"Reality thread '{thread_id}' not found")
        next_thread = {
            **current,
            "summary": patch.get("summary", current["summary"]),
            "active_scene": patch.get("active_scene", patch.get("activeScene", current["active_scene"])),
            "open_loops": patch.get("open_loops", patch.get("openLoops", current["open_loops"])),
            "metadata": patch.get("metadata", current["metadata"]),
            "updated_at": self.now(),
        }
        self.connection.execute(
            """
            UPDATE reality_threads
            SET summary = ?, active_scene = ?, open_loops_json = ?, metadata_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                next_thread["summary"],
                next_thread["active_scene"],
                _dump_json(next_thread["open_loops"]),
                _dump_json(next_thread["metadata"]),
                next_thread["updated_at"],
                thread_id,
            ),
        )
        self.connection.commit()
        return next_thread

    def append_reality_event(self, payload: dict) -> dict:
        record = {
            "id": payload.get("id", create_id("evt")),
            "thread_id": payload["thread_id"],
            "type": payload["type"],
            "source": payload["source"],
            "summary": payload["summary"],
            "payload": payload.get("payload", {}),
            "created_at": payload.get("created_at", self.now()),
        }
        self.connection.execute(
            """
            INSERT INTO reality_events (
              id, thread_id, type, source, summary, payload_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["id"],
                record["thread_id"],
                record["type"],
                record["source"],
                record["summary"],
                _dump_json(record["payload"]),
                record["created_at"],
            ),
        )
        self.connection.commit()
        self._append_jsonl("reality-events.jsonl", record)
        return record

    def list_recent_reality_events(self, thread_id: str, limit: int = 10) -> list[dict]:
        rows = self.connection.execute(
            """
            SELECT * FROM reality_events
            WHERE thread_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (thread_id, limit),
        ).fetchall()
        return [
            {
                "id": row["id"],
                "thread_id": row["thread_id"],
                "type": row["type"],
                "source": row["source"],
                "summary": row["summary"],
                "payload": _parse_json(row["payload_json"], {}),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def upsert_consequence(self, payload: dict) -> dict:
        existing = self.connection.execute(
            """
            SELECT * FROM consequences
            WHERE thread_id = ? AND kind = ? AND status = 'active'
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (payload["thread_id"], payload["kind"]),
        ).fetchone()
        now = self.now()

        if existing:
            record = {
                "id": existing["id"],
                "thread_id": existing["thread_id"],
                "kind": existing["kind"],
                "source_event_id": payload.get("source_event_id", existing["source_event_id"]),
                "summary": payload.get("summary", existing["summary"]),
                "status": payload.get("status", existing["status"]),
                "weight": payload.get("weight", existing["weight"]),
                "scope": payload.get("scope", existing["scope"]),
                "handoff_hint": payload.get("handoff_hint", existing["handoff_hint"]),
                "metadata": payload.get("metadata", _parse_json(existing["metadata_json"], {})),
                "created_at": existing["created_at"],
                "updated_at": now,
            }
            self.connection.execute(
                """
                UPDATE consequences
                SET source_event_id = ?, summary = ?, status = ?, weight = ?, scope = ?,
                    handoff_hint = ?, metadata_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    record["source_event_id"],
                    record["summary"],
                    record["status"],
                    record["weight"],
                    record["scope"],
                    record["handoff_hint"],
                    _dump_json(record["metadata"]),
                    record["updated_at"],
                    record["id"],
                ),
            )
            self.connection.commit()
            return record

        record = {
            "id": create_id("conseq"),
            "thread_id": payload["thread_id"],
            "kind": payload["kind"],
            "source_event_id": payload["source_event_id"],
            "summary": payload["summary"],
            "status": payload.get("status", "active"),
            "weight": payload.get("weight", 0.5),
            "scope": payload.get("scope", "reality"),
            "handoff_hint": payload.get("handoff_hint", ""),
            "metadata": payload.get("metadata", {}),
            "created_at": now,
            "updated_at": now,
        }
        self.connection.execute(
            """
            INSERT INTO consequences (
              id, thread_id, kind, source_event_id, summary, status,
              weight, scope, handoff_hint, metadata_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["id"],
                record["thread_id"],
                record["kind"],
                record["source_event_id"],
                record["summary"],
                record["status"],
                record["weight"],
                record["scope"],
                record["handoff_hint"],
                _dump_json(record["metadata"]),
                record["created_at"],
                record["updated_at"],
            ),
        )
        self.connection.commit()
        return record

    def resolve_consequence(self, payload: dict) -> dict | None:
        if payload.get("id"):
            row = self.connection.execute(
                "SELECT * FROM consequences WHERE id = ?", (payload["id"],)
            ).fetchone()
        else:
            row = self.connection.execute(
                """
                SELECT * FROM consequences
                WHERE thread_id = ? AND kind = ? AND status = 'active'
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (payload["thread_id"], payload["kind"]),
            ).fetchone()
        if not row:
            return None
        updated_at = self.now()
        self.connection.execute(
            "UPDATE consequences SET status = 'resolved', updated_at = ? WHERE id = ?",
            (updated_at, row["id"]),
        )
        self.connection.commit()
        return {
            "id": row["id"],
            "kind": row["kind"],
            "status": "resolved",
            "updated_at": updated_at,
        }

    def list_consequences(self, thread_id: str, status: str = "active") -> list[dict]:
        rows = self.connection.execute(
            """
            SELECT * FROM consequences
            WHERE thread_id = ? AND status = ?
            ORDER BY weight DESC, updated_at DESC
            """,
            (thread_id, status),
        ).fetchall()
        return [
            {
                "id": row["id"],
                "thread_id": row["thread_id"],
                "kind": row["kind"],
                "source_event_id": row["source_event_id"],
                "summary": row["summary"],
                "status": row["status"],
                "weight": row["weight"],
                "scope": row["scope"],
                "handoff_hint": row["handoff_hint"],
                "metadata": _parse_json(row["metadata_json"], {}),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

    def set_foreground_control(self, payload: dict) -> None:
        now = self.now()
        self.connection.execute(
            """
            INSERT INTO foreground_control (
              slot, thread_id, client_id, session_id, reason, updated_at
            ) VALUES ('foreground', ?, ?, ?, ?, ?)
            ON CONFLICT(slot) DO UPDATE SET
              thread_id = excluded.thread_id,
              client_id = excluded.client_id,
              session_id = excluded.session_id,
              reason = excluded.reason,
              updated_at = excluded.updated_at
            """,
            (
                payload["thread_id"],
                payload["client_id"],
                payload["session_id"],
                payload["reason"],
                now,
            ),
        )
        self.connection.commit()

    def get_foreground_control(self) -> dict | None:
        row = self.connection.execute(
            "SELECT * FROM foreground_control WHERE slot = 'foreground'"
        ).fetchone()
        if not row:
            return None
        return {
            "thread_id": row["thread_id"],
            "client_id": row["client_id"],
            "session_id": row["session_id"],
            "reason": row["reason"],
            "updated_at": row["updated_at"],
        }

    def record_switch(self, payload: dict) -> dict:
        record = {
            "id": create_id("switch"),
            "from_client_id": payload.get("from_client_id"),
            "to_client_id": payload["to_client_id"],
            "from_persona_id": payload.get("from_persona_id"),
            "to_persona_id": payload["to_persona_id"],
            "reason": payload["reason"],
            "explanation": payload["explanation"],
            "handoff_summary": payload["handoff_summary"],
            "trigger": payload.get("trigger", "daemon"),
            "created_at": payload.get("created_at", self.now()),
        }
        self.connection.execute(
            """
            INSERT INTO switch_logs (
              id, from_client_id, to_client_id, from_persona_id, to_persona_id,
              reason, explanation, handoff_summary, trigger, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["id"],
                record["from_client_id"],
                record["to_client_id"],
                record["from_persona_id"],
                record["to_persona_id"],
                record["reason"],
                record["explanation"],
                record["handoff_summary"],
                record["trigger"],
                record["created_at"],
            ),
        )
        self.connection.commit()
        self._append_jsonl("switch-log.jsonl", record)
        return record

    def list_switch_logs(self, limit: int = 10) -> list[dict]:
        rows = self.connection.execute(
            "SELECT * FROM switch_logs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [
            {
                "id": row["id"],
                "from_client_id": row["from_client_id"],
                "to_client_id": row["to_client_id"],
                "from_persona_id": row["from_persona_id"],
                "to_persona_id": row["to_persona_id"],
                "reason": row["reason"],
                "explanation": row["explanation"],
                "handoff_summary": row["handoff_summary"],
                "trigger": row["trigger"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def get_reality_projection(self, thread_id: str) -> dict:
        thread = self.get_latest_reality_thread()
        if not thread or thread["id"] != thread_id:
            raise ValueError(f"Reality thread '{thread_id}' not found")
        return {
            "thread": thread,
            "consequences": self.list_consequences(thread_id, "active"),
            "recent_events": self.list_recent_reality_events(thread_id, 8),
            "reality_notes": self.list_memories({"layer": "reality-note", "limit": 5}),
        }
