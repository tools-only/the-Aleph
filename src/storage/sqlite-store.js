import { mkdirSync, appendFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { DatabaseSync } from 'node:sqlite';
import { createId } from '../lib/id.js';

function parseJson(value, fallback) {
  if (!value) return fallback;
  try {
    return JSON.parse(value);
  } catch {
    return fallback;
  }
}

function stringifyJson(value) {
  return JSON.stringify(value ?? null);
}

export class SqliteStore {
  constructor(options = {}) {
    this.rootDir = options.rootDir ?? process.cwd();
    this.dataDir = join(this.rootDir, 'data');
    this.logsDir = join(this.dataDir, 'logs');
    this.dbPath = options.dbPath ?? join(this.dataDir, 'aleph.db');
    this.now = options.now ?? (() => Date.now());

    mkdirSync(dirname(this.dbPath), { recursive: true });
    mkdirSync(this.logsDir, { recursive: true });

    this.db = new DatabaseSync(this.dbPath);
    this.db.exec('PRAGMA journal_mode = WAL;');
    this.db.exec('PRAGMA foreign_keys = ON;');
    this._initSchema();
  }

  _initSchema() {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS persona_profiles (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        voice TEXT NOT NULL,
        specialties_json TEXT NOT NULL,
        boundaries_json TEXT NOT NULL,
        permissions_json TEXT NOT NULL,
        shared_domains_json TEXT NOT NULL,
        metadata_json TEXT NOT NULL,
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL
      );

      CREATE TABLE IF NOT EXISTS persona_sessions (
        id TEXT PRIMARY KEY,
        persona_id TEXT NOT NULL,
        status TEXT NOT NULL,
        handoff_summary TEXT,
        last_reality_lens TEXT,
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL
      );

      CREATE TABLE IF NOT EXISTS memories (
        id TEXT PRIMARY KEY,
        layer TEXT NOT NULL,
        persona_id TEXT,
        domain TEXT,
        kind TEXT NOT NULL,
        content TEXT NOT NULL,
        metadata_json TEXT NOT NULL,
        created_at INTEGER NOT NULL
      );

      CREATE TABLE IF NOT EXISTS reality_threads (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        summary TEXT NOT NULL,
        active_scene TEXT NOT NULL,
        open_loops_json TEXT NOT NULL,
        metadata_json TEXT NOT NULL,
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL
      );

      CREATE TABLE IF NOT EXISTS reality_events (
        id TEXT PRIMARY KEY,
        thread_id TEXT NOT NULL,
        type TEXT NOT NULL,
        source TEXT NOT NULL,
        summary TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        created_at INTEGER NOT NULL
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
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL
      );

      CREATE TABLE IF NOT EXISTS switch_logs (
        id TEXT PRIMARY KEY,
        from_persona_id TEXT,
        to_persona_id TEXT NOT NULL,
        reason TEXT NOT NULL,
        explanation TEXT NOT NULL,
        handoff_summary TEXT NOT NULL,
        trigger TEXT NOT NULL,
        created_at INTEGER NOT NULL
      );

      CREATE TABLE IF NOT EXISTS foreground_control (
        slot TEXT PRIMARY KEY,
        thread_id TEXT NOT NULL,
        persona_id TEXT NOT NULL,
        session_id TEXT NOT NULL,
        reason TEXT NOT NULL,
        updated_at INTEGER NOT NULL
      );
    `);
  }

  close() {
    this.db.close();
  }

  savePersonaProfile(profile) {
    const now = this.now();
    this.db
      .prepare(`
        INSERT INTO persona_profiles (
          id, name, voice, specialties_json, boundaries_json,
          permissions_json, shared_domains_json, metadata_json,
          created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
          name = excluded.name,
          voice = excluded.voice,
          specialties_json = excluded.specialties_json,
          boundaries_json = excluded.boundaries_json,
          permissions_json = excluded.permissions_json,
          shared_domains_json = excluded.shared_domains_json,
          metadata_json = excluded.metadata_json,
          updated_at = excluded.updated_at
      `)
      .run(
        profile.id,
        profile.name,
        profile.voice,
        stringifyJson(profile.specialties ?? []),
        stringifyJson(profile.boundaries ?? []),
        stringifyJson(profile.permissions ?? []),
        stringifyJson(profile.sharedDomains ?? []),
        stringifyJson(profile.metadata ?? {}),
        now,
        now,
      );
  }

  getPersonaProfile(personaId) {
    const row = this.db
      .prepare('SELECT * FROM persona_profiles WHERE id = ?')
      .get(personaId);
    return row ? this._mapPersonaProfile(row) : null;
  }

  listPersonaProfiles() {
    const rows = this.db
      .prepare('SELECT * FROM persona_profiles ORDER BY created_at ASC')
      .all();
    return rows.map((row) => this._mapPersonaProfile(row));
  }

  _mapPersonaProfile(row) {
    return {
      id: row.id,
      name: row.name,
      voice: row.voice,
      specialties: parseJson(row.specialties_json, []),
      boundaries: parseJson(row.boundaries_json, []),
      permissions: parseJson(row.permissions_json, []),
      sharedDomains: parseJson(row.shared_domains_json, []),
      metadata: parseJson(row.metadata_json, {}),
      createdAt: row.created_at,
      updatedAt: row.updated_at,
    };
  }

  createRealityThread(input = {}) {
    const now = this.now();
    const thread = {
      id: createId('thread'),
      title: input.title ?? 'Aleph Reality Thread',
      summary: input.summary ?? 'Reality is active and continuous.',
      activeScene: input.activeScene ?? 'The conversation has just begun.',
      openLoops: input.openLoops ?? [],
      metadata: input.metadata ?? {},
      createdAt: now,
      updatedAt: now,
    };
    this.db
      .prepare(`
        INSERT INTO reality_threads (
          id, title, summary, active_scene, open_loops_json,
          metadata_json, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
      `)
      .run(
        thread.id,
        thread.title,
        thread.summary,
        thread.activeScene,
        stringifyJson(thread.openLoops),
        stringifyJson(thread.metadata),
        thread.createdAt,
        thread.updatedAt,
      );
    return thread;
  }

  getLatestRealityThread() {
    const row = this.db
      .prepare('SELECT * FROM reality_threads ORDER BY created_at DESC LIMIT 1')
      .get();
    return row ? this._mapRealityThread(row) : null;
  }

  _mapRealityThread(row) {
    return {
      id: row.id,
      title: row.title,
      summary: row.summary,
      activeScene: row.active_scene,
      openLoops: parseJson(row.open_loops_json, []),
      metadata: parseJson(row.metadata_json, {}),
      createdAt: row.created_at,
      updatedAt: row.updated_at,
    };
  }

  updateRealityThread(threadId, patch = {}) {
    const current = this.getLatestRealityThread();
    if (!current || current.id !== threadId) {
      throw new Error(`Reality thread '${threadId}' not found`);
    }
    const next = {
      ...current,
      summary: patch.summary ?? current.summary,
      activeScene: patch.activeScene ?? current.activeScene,
      openLoops: patch.openLoops ?? current.openLoops,
      metadata: patch.metadata ?? current.metadata,
      updatedAt: this.now(),
    };
    this.db
      .prepare(`
        UPDATE reality_threads
        SET summary = ?, active_scene = ?, open_loops_json = ?, metadata_json = ?, updated_at = ?
        WHERE id = ?
      `)
      .run(
        next.summary,
        next.activeScene,
        stringifyJson(next.openLoops),
        stringifyJson(next.metadata),
        next.updatedAt,
        threadId,
      );
    return next;
  }

  appendRealityEvent(event) {
    const record = {
      id: event.id ?? createId('evt'),
      threadId: event.threadId,
      type: event.type,
      source: event.source,
      summary: event.summary,
      payload: event.payload ?? {},
      createdAt: event.createdAt ?? this.now(),
    };
    this.db
      .prepare(`
        INSERT INTO reality_events (
          id, thread_id, type, source, summary, payload_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
      `)
      .run(
        record.id,
        record.threadId,
        record.type,
        record.source,
        record.summary,
        stringifyJson(record.payload),
        record.createdAt,
      );

    this._appendJsonl('reality-events.jsonl', record);
    return record;
  }

  listRecentRealityEvents(threadId, limit = 10) {
    const rows = this.db
      .prepare(`
        SELECT * FROM reality_events
        WHERE thread_id = ?
        ORDER BY created_at DESC
        LIMIT ?
      `)
      .all(threadId, limit);
    return rows.map((row) => ({
      id: row.id,
      threadId: row.thread_id,
      type: row.type,
      source: row.source,
      summary: row.summary,
      payload: parseJson(row.payload_json, {}),
      createdAt: row.created_at,
    }));
  }

  createSession(input) {
    const now = this.now();
    const session = {
      id: createId('session'),
      personaId: input.personaId,
      status: input.status ?? 'active',
      handoffSummary: input.handoffSummary ?? '',
      lastRealityLens: input.lastRealityLens ?? '',
      createdAt: now,
      updatedAt: now,
    };
    this.db
      .prepare(`
        INSERT INTO persona_sessions (
          id, persona_id, status, handoff_summary, last_reality_lens, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
      `)
      .run(
        session.id,
        session.personaId,
        session.status,
        session.handoffSummary,
        session.lastRealityLens,
        session.createdAt,
        session.updatedAt,
      );
    return session;
  }

  updateSession(sessionId, patch = {}) {
    const row = this.db
      .prepare('SELECT * FROM persona_sessions WHERE id = ?')
      .get(sessionId);
    if (!row) throw new Error(`Session '${sessionId}' not found`);
    const updatedAt = this.now();
    this.db
      .prepare(`
        UPDATE persona_sessions
        SET status = ?, handoff_summary = ?, last_reality_lens = ?, updated_at = ?
        WHERE id = ?
      `)
      .run(
        patch.status ?? row.status,
        patch.handoffSummary ?? row.handoff_summary,
        patch.lastRealityLens ?? row.last_reality_lens,
        updatedAt,
        sessionId,
      );
  }

  saveMemory(memory) {
    const record = {
      id: createId('mem'),
      layer: memory.layer,
      personaId: memory.personaId ?? null,
      domain: memory.domain ?? null,
      kind: memory.kind ?? 'note',
      content: memory.content,
      metadata: memory.metadata ?? {},
      createdAt: memory.createdAt ?? this.now(),
    };
    this.db
      .prepare(`
        INSERT INTO memories (
          id, layer, persona_id, domain, kind, content, metadata_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
      `)
      .run(
        record.id,
        record.layer,
        record.personaId,
        record.domain,
        record.kind,
        record.content,
        stringifyJson(record.metadata),
        record.createdAt,
      );
    return record;
  }

  listMemories(filter = {}) {
    const limit = filter.limit ?? 20;
    if (filter.layer === 'shared') {
      const domains = filter.domains ?? [];
      if (domains.length === 0) return [];
      const placeholders = domains.map(() => '?').join(', ');
      const rows = this.db
        .prepare(`
          SELECT * FROM memories
          WHERE layer = 'shared' AND domain IN (${placeholders})
          ORDER BY created_at DESC
          LIMIT ?
        `)
        .all(...domains, limit);
      return rows.map((row) => this._mapMemory(row));
    }

    if (filter.layer === 'private') {
      const rows = this.db
        .prepare(`
          SELECT * FROM memories
          WHERE layer = 'private' AND persona_id = ?
          ORDER BY created_at DESC
          LIMIT ?
        `)
        .all(filter.personaId, limit);
      return rows.map((row) => this._mapMemory(row));
    }

    if (filter.layer === 'reality-note') {
      const rows = this.db
        .prepare(`
          SELECT * FROM memories
          WHERE layer = 'reality-note'
          ORDER BY created_at DESC
          LIMIT ?
        `)
        .all(limit);
      return rows.map((row) => this._mapMemory(row));
    }

    const rows = this.db
      .prepare('SELECT * FROM memories ORDER BY created_at DESC LIMIT ?')
      .all(limit);
    return rows.map((row) => this._mapMemory(row));
  }

  _mapMemory(row) {
    return {
      id: row.id,
      layer: row.layer,
      personaId: row.persona_id,
      domain: row.domain,
      kind: row.kind,
      content: row.content,
      metadata: parseJson(row.metadata_json, {}),
      createdAt: row.created_at,
    };
  }

  upsertConsequence(input) {
    const now = this.now();
    const existing = this.db
      .prepare(`
        SELECT * FROM consequences
        WHERE thread_id = ? AND kind = ? AND status = 'active'
        ORDER BY updated_at DESC
        LIMIT 1
      `)
      .get(input.threadId, input.kind);

    if (existing) {
      const next = {
        id: existing.id,
        threadId: existing.thread_id,
        kind: existing.kind,
        sourceEventId: input.sourceEventId ?? existing.source_event_id,
        summary: input.summary ?? existing.summary,
        status: input.status ?? existing.status,
        weight: input.weight ?? existing.weight,
        scope: input.scope ?? existing.scope,
        handoffHint: input.handoffHint ?? existing.handoff_hint,
        metadata: input.metadata ?? parseJson(existing.metadata_json, {}),
        createdAt: existing.created_at,
        updatedAt: now,
      };
      this.db
        .prepare(`
          UPDATE consequences
          SET source_event_id = ?, summary = ?, status = ?, weight = ?, scope = ?,
              handoff_hint = ?, metadata_json = ?, updated_at = ?
          WHERE id = ?
        `)
        .run(
          next.sourceEventId,
          next.summary,
          next.status,
          next.weight,
          next.scope,
          next.handoffHint,
          stringifyJson(next.metadata),
          next.updatedAt,
          next.id,
        );
      return next;
    }

    const record = {
      id: createId('conseq'),
      threadId: input.threadId,
      kind: input.kind,
      sourceEventId: input.sourceEventId,
      summary: input.summary,
      status: input.status ?? 'active',
      weight: input.weight ?? 0.5,
      scope: input.scope ?? 'reality',
      handoffHint: input.handoffHint ?? '',
      metadata: input.metadata ?? {},
      createdAt: now,
      updatedAt: now,
    };
    this.db
      .prepare(`
        INSERT INTO consequences (
          id, thread_id, kind, source_event_id, summary, status, weight, scope,
          handoff_hint, metadata_json, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      `)
      .run(
        record.id,
        record.threadId,
        record.kind,
        record.sourceEventId,
        record.summary,
        record.status,
        record.weight,
        record.scope,
        record.handoffHint,
        stringifyJson(record.metadata),
        record.createdAt,
        record.updatedAt,
      );
    return record;
  }

  resolveConsequence(input) {
    let row;
    if (input.id) {
      row = this.db.prepare('SELECT * FROM consequences WHERE id = ?').get(input.id);
    } else {
      row = this.db
        .prepare(`
          SELECT * FROM consequences
          WHERE thread_id = ? AND kind = ? AND status = 'active'
          ORDER BY updated_at DESC
          LIMIT 1
        `)
        .get(input.threadId, input.kind);
    }
    if (!row) return null;
    const updatedAt = this.now();
    this.db
      .prepare(`
        UPDATE consequences
        SET status = 'resolved', updated_at = ?
        WHERE id = ?
      `)
      .run(updatedAt, row.id);
    return {
      id: row.id,
      kind: row.kind,
      status: 'resolved',
      updatedAt,
    };
  }

  listConsequences(threadId, status = 'active') {
    const rows = this.db
      .prepare(`
        SELECT * FROM consequences
        WHERE thread_id = ? AND status = ?
        ORDER BY weight DESC, updated_at DESC
      `)
      .all(threadId, status);
    return rows.map((row) => ({
      id: row.id,
      threadId: row.thread_id,
      kind: row.kind,
      sourceEventId: row.source_event_id,
      summary: row.summary,
      status: row.status,
      weight: row.weight,
      scope: row.scope,
      handoffHint: row.handoff_hint,
      metadata: parseJson(row.metadata_json, {}),
      createdAt: row.created_at,
      updatedAt: row.updated_at,
    }));
  }

  setForegroundControl(input) {
    const now = this.now();
    this.db
      .prepare(`
        INSERT INTO foreground_control (
          slot, thread_id, persona_id, session_id, reason, updated_at
        ) VALUES ('foreground', ?, ?, ?, ?, ?)
        ON CONFLICT(slot) DO UPDATE SET
          thread_id = excluded.thread_id,
          persona_id = excluded.persona_id,
          session_id = excluded.session_id,
          reason = excluded.reason,
          updated_at = excluded.updated_at
      `)
      .run(input.threadId, input.personaId, input.sessionId, input.reason, now);
  }

  getForegroundControl() {
    const row = this.db
      .prepare('SELECT * FROM foreground_control WHERE slot = \'foreground\'')
      .get();
    if (!row) return null;
    return {
      threadId: row.thread_id,
      personaId: row.persona_id,
      sessionId: row.session_id,
      reason: row.reason,
      updatedAt: row.updated_at,
    };
  }

  recordSwitch(entry) {
    const record = {
      id: createId('switch'),
      fromPersonaId: entry.fromPersonaId ?? null,
      toPersonaId: entry.toPersonaId,
      reason: entry.reason,
      explanation: entry.explanation,
      handoffSummary: entry.handoffSummary,
      trigger: entry.trigger ?? 'daemon',
      createdAt: entry.createdAt ?? this.now(),
    };
    this.db
      .prepare(`
        INSERT INTO switch_logs (
          id, from_persona_id, to_persona_id, reason, explanation, handoff_summary, trigger, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
      `)
      .run(
        record.id,
        record.fromPersonaId,
        record.toPersonaId,
        record.reason,
        record.explanation,
        record.handoffSummary,
        record.trigger,
        record.createdAt,
      );
    this._appendJsonl('switch-log.jsonl', record);
    return record;
  }

  getLatestSwitchLog() {
    return (
      this.db
        .prepare('SELECT * FROM switch_logs ORDER BY created_at DESC LIMIT 1')
        .get() ?? null
    );
  }

  listSwitchLogs(limit = 10) {
    return this.db
      .prepare('SELECT * FROM switch_logs ORDER BY created_at DESC LIMIT ?')
      .all(limit)
      .map((row) => ({
        id: row.id,
        fromPersonaId: row.from_persona_id,
        toPersonaId: row.to_persona_id,
        reason: row.reason,
        explanation: row.explanation,
        handoffSummary: row.handoff_summary,
        trigger: row.trigger,
        createdAt: row.created_at,
      }));
  }

  getRealityProjection(threadId) {
    const thread = this.getLatestRealityThread();
    if (!thread || thread.id !== threadId) {
      throw new Error(`Reality thread '${threadId}' not found`);
    }
    return {
      thread,
      consequences: this.listConsequences(threadId, 'active'),
      recentEvents: this.listRecentRealityEvents(threadId, 8),
      realityNotes: this.listMemories({ layer: 'reality-note', limit: 5 }),
    };
  }

  _appendJsonl(filename, payload) {
    const path = join(this.logsDir, filename);
    appendFileSync(path, `${JSON.stringify(payload)}\n`, 'utf8');
  }
}

