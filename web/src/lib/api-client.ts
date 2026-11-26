// ==========================================================================
// safe storage, clipboard, unified backend client
// ==========================================================================
import type { ActivityItem, ToolId } from '../data/workspace';

export type PlatformToolState = 'online' | 'offline' | 'starting' | 'error';

export interface PlatformToolStatus {
  id: ToolId;
  name: string;
  url: string;
  port: number;
  status: PlatformToolState;
  detail: unknown;
}

export interface PlatformStatus {
  product: 'Seclyst';
  version: string;
  generatedAt: number;
  tools: Record<ToolId, PlatformToolStatus>;
}

export interface PlatformCollection {
  count: number;
  records: Record<string, unknown>[];
  available: boolean;
  detail?: string;
}

export interface PlatformSummary {
  generatedAt: number;
  collections: Record<ToolId, PlatformCollection>;
}

export interface AuthStatus {
  /** Whether the control plane gates its API behind a password at all. */
  required: boolean;
  /** Whether a password has been set yet (false means first-run setup). */
  configured: boolean;
  /** Whether the current browser holds a valid session cookie. */
  authenticated: boolean;
}

const ACTIVITY_LABELS: Record<ToolId, string> = {
  malware: 'Malware scan',
  ioc: 'IOC lookup',
  events: 'Event investigation',
  phishing: 'Email analysis',
  ruleforge: 'Rule saved'
};

/* Where each engine keeps the stored results an activity row points at. The
   row has always carried `targetSubTab`, but nothing ever filled it, so a
   click had no destination. These are the sub-tabs that list saved runs. */
const ACTIVITY_TARGETS: Record<ToolId, string> = {
  malware: 'dashboard',
  ioc: 'history',
  events: 'events',
  phishing: 'dashboard',
  ruleforge: 'history'
};

function recordText(record: Record<string, unknown>, keys: string[]): string {
  for (const key of keys) {
    const value = record[key];
    if (typeof value === 'string' && value.trim()) return value.trim();
    if (typeof value === 'number' && Number.isFinite(value)) return String(value);
  }
  return '';
}

/* Each engine stores a different shape. Reading the wrong field is exactly why
   every IOC row used to say "Stored record": the indicator lives in `value`,
   not in `ioc`. These maps name the real columns each history endpoint returns
   (see /api/scans, /api/recent, /api/investigations, /api/history). */
interface ActivityFields {
  subject: string[];
  time: string[];
  id: string[];
  verdict: string[];
  score: string[];
  kind: string[];
}

const ACTIVITY_FIELDS: Record<ToolId, ActivityFields> = {
  ioc: {
    subject: ['value', 'indicator', 'ioc'],
    time: ['created_at', 'timestamp', 'last_lookup'],
    id: ['id', 'ioc_id'],
    verdict: ['verdict'],
    score: ['score'],
    kind: ['ioc_type']
  },
  malware: {
    subject: ['filename', 'name'],
    time: ['timestamp', 'created_at'],
    id: ['id', 'scan_id'],
    verdict: ['verdict', 'level'],
    score: ['score'],
    kind: ['file_type']
  },
  phishing: {
    subject: ['filename', 'subject', 'name'],
    time: ['timestamp', 'created_at'],
    id: ['id', 'scan_id'],
    verdict: ['verdict', 'severity'],
    score: ['score'],
    kind: []
  },
  events: {
    subject: ['name', 'filename'],
    time: ['created_at', 'timestamp'],
    id: ['id', 'investigation_id'],
    verdict: ['status'],
    score: [],
    kind: []
  },
  ruleforge: {
    subject: ['title', 'rule_id', 'name'],
    time: ['created_at', 'timestamp'],
    id: ['id', 'entry_id'],
    verdict: ['origin'],
    score: [],
    kind: ['dialect']
  }
};

const EMPTY_VERDICTS = new Set(['', 'unknown', 'none', 'null', 'undefined', 'n/a']);

/* Never print a bare "unknown": if an engine did not return a verdict, say that
   in words the analyst can act on. */
function cleanWord(value: string): string {
  const trimmed = value.trim();
  return EMPTY_VERDICTS.has(trimmed.toLowerCase()) ? '' : trimmed;
}

function verdictTone(verdict: string): ActivityItem['verdict'] {
  const value = verdict.toLowerCase();
  if (!value) return 'info';
  if (/malicious|infected|breach|critical|phishing|compromised/.test(value)) return 'malicious';
  if (/suspicious|high|medium|warn/.test(value)) return 'suspicious';
  if (/clean|benign|safe|low|pass/.test(value)) return 'clean';
  return 'info';
}

/* One sentence per row, in the words an analyst would use, naming the actual
   evidence and outcome rather than a generic record type. */
function describeActivity(
  tool: ToolId,
  subject: string,
  verdict: string,
  score: string,
  kind: string
): string {
  const outcome = [verdict, score ? `score ${score}` : ''].filter(Boolean).join(', ');
  switch (tool) {
    case 'ioc':
      return `Looked up ${subject || 'an indicator'}${kind ? ` (${kind})` : ''} — ${
        outcome || 'no verdict returned'
      }`;
    case 'malware':
      return `Scanned ${subject || 'a file'} — ${outcome || 'finished, no verdict returned'}`;
    case 'phishing':
      return `Checked email ${subject || '(unnamed)'} — ${outcome || 'finished, no verdict returned'}`;
    case 'events':
      return `Loaded event log ${subject || '(unnamed)'} — ${verdict || 'analysis running'}`;
    case 'ruleforge':
      return `Saved rule ${subject || '(untitled)'}${kind ? ` (${kind})` : ''} — ${verdict || 'stored'}`;
    default:
      return subject || outcome || 'Stored record';
  }
}

export function summaryToActivity(summary: PlatformSummary): ActivityItem[] {
  const rows: ActivityItem[] = [];
  (Object.entries(summary.collections) as [ToolId, PlatformCollection][]).forEach(([tool, collection]) => {
    const fields = ACTIVITY_FIELDS[tool];
    collection.records.forEach((record, index) => {
      const recordId = recordText(record, fields.id);
      const subjectRaw = recordText(record, fields.subject);
      const rawTime = recordText(record, fields.time);
      const parsedTime = rawTime ? new Date(rawTime) : null;
      const recordedAt =
        parsedTime && !Number.isNaN(parsedTime.getTime()) ? parsedTime.getTime() : undefined;
      const timestamp =
        recordedAt !== undefined ? new Date(recordedAt).toLocaleString() : rawTime || 'Time unavailable';
      const verdictRaw = cleanWord(recordText(record, fields.verdict));
      const scoreRaw = recordText(record, fields.score);
      const kindRaw = recordText(record, fields.kind);
      // Prefer the engine's own id. Without one, key off the record's content
      // rather than its position: an index would make a brand-new row inherit
      // an old row's dismissed state (or vice versa) as the list shifts.
      const signature =
        [subjectRaw, rawTime, kindRaw, verdictRaw].filter(Boolean).join('|') || `row-${index}`;
      const stableId = recordId || signature;
      rows.push({
        id: `${tool}:${stableId}`,
        tool,
        actionType: ACTIVITY_LABELS[tool],
        description: describeActivity(tool, subjectRaw, verdictRaw, scoreRaw, kindRaw),
        timestamp,
        recordedAt,
        verdict: verdictTone(verdictRaw),
        scoreText: scoreRaw || undefined,
        severity: 'info',
        targetSubTab: ACTIVITY_TARGETS[tool],
        // IOC Lookup is the one engine whose deep-link contract the shell
        // already uses, so the indicator is carried through and looked up.
        targetItemId: subjectRaw || recordId || undefined,
        unread: false
      });
    });
  });
  return rows.slice(0, 100);
}

export function safeLocalGet<T>(key: string, fallback: T): T {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

export function safeLocalSet(key: string, value: unknown): void {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Ignore quota or sandboxed iframe storage blocks
  }
}

export function safeSessionGet<T>(key: string, fallback: T): T {
  try {
    const raw = window.sessionStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

export function safeSessionSet(key: string, value: unknown): void {
  try {
    window.sessionStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Ignore quota or sandboxed iframe storage blocks
  }
}

export function copyTextToClipboard(text: string, onDone?: () => void): void {
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(() => {
        if (onDone) onDone();
      }).catch(() => {
        fallbackCopy(text, onDone);
      });
      return;
    }
  } catch {
    // Fallback below
  }
  fallbackCopy(text, onDone);
}

export function fallbackCopy(text: string, onDone?: () => void): void {
  try {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
  } catch {
    // Ignore if blocked
  }
  if (onDone) onDone();
}

export function downloadFileBlob(filename: string, content: string, mimeType = 'application/json'): void {
  try {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch {
    // Fallback handled via toast
  }
}

// The shell only talks to the Seclyst supervisor. Tool interfaces use their
// own live origins inside isolated frames, so browser CORS and provider keys do
// not leak into this client.
export class SeclystApiClient {
  private async get<T>(path: string, signal?: AbortSignal): Promise<T> {
    const response = await fetch(path, {
      headers: { Accept: 'application/json' },
      cache: 'no-store',
      signal
    });
    if (!response.ok) {
      throw new Error(`Seclyst platform request failed with HTTP ${response.status}`);
    }
    return response.json() as Promise<T>;
  }

  /* The control plane wraps HTTP errors as { error: { code, message } }. Surface
     the server's own sentence (an incorrect password, a weak one) rather than a
     status code the person cannot act on. */
  private async post<T>(path: string, body: unknown): Promise<T> {
    const response = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify(body),
      cache: 'no-store'
    });
    const payload = (await response.json().catch(() => null)) as
      | { error?: { message?: string } }
      | null;
    if (!response.ok) {
      throw new Error(payload?.error?.message || `Request failed with HTTP ${response.status}`);
    }
    return payload as T;
  }

  status(signal?: AbortSignal): Promise<PlatformStatus> {
    return this.get<PlatformStatus>('/api/platform/status', signal);
  }

  summary(signal?: AbortSignal): Promise<PlatformSummary> {
    return this.get<PlatformSummary>('/api/platform/summary', signal);
  }

  /* Hand a file or folder to the engine that analyses it. The shell cannot
     push a File into a cross-origin engine iframe, so it posts the evidence to
     the control plane, which forwards it to the engine's own upload endpoint
     with the workspace access token. The engine then runs its normal pipeline
     and the finished record appears in the activity feed. */
  async intake(
    tool: ToolId,
    files: File[]
  ): Promise<{ tool: ToolId; started: number; rejected: { name: string; message?: string }[] }> {
    const form = new FormData();
    form.append('tool', tool);
    files.forEach((file) => form.append('files', file, file.name));
    const response = await fetch('/api/v1/intake', {
      method: 'POST',
      headers: { Accept: 'application/json' },
      body: form,
      cache: 'no-store'
    });
    const payload = (await response.json().catch(() => null)) as
      | { error?: { message?: string }; started?: number; rejected?: { name: string; message?: string }[] }
      | null;
    if (!response.ok) {
      throw new Error(payload?.error?.message || `Upload failed with HTTP ${response.status}`);
    }
    return {
      tool,
      started: payload?.started ?? 0,
      rejected: payload?.rejected ?? []
    };
  }

  authStatus(signal?: AbortSignal): Promise<AuthStatus> {
    return this.get<AuthStatus>('/api/v1/auth/status', signal);
  }

  authLogin(password: string): Promise<AuthStatus> {
    return this.post<AuthStatus>('/api/v1/auth/login', { password });
  }

  authSetup(password: string): Promise<AuthStatus> {
    return this.post<AuthStatus>('/api/v1/auth/setup', { password });
  }

  authLogout(): Promise<AuthStatus> {
    return this.post<AuthStatus>('/api/v1/auth/logout', {});
  }

  authChangePassword(current: string, password: string): Promise<AuthStatus> {
    return this.post<AuthStatus>('/api/v1/auth/password', { current, password });
  }

  async healthCheck(tool: ToolId): Promise<{ status: 'online' | 'offline' | 'unknown'; latencyMs: number; version: string }> {
    const start = performance.now();
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 2500);
      const platform = await this.status(controller.signal);
      clearTimeout(timer);
      const state = platform.tools[tool]?.status;
      return {
        status: state === 'online' ? 'online' : state === 'starting' ? 'unknown' : 'offline',
        latencyMs: Math.round(performance.now() - start),
        version: platform.version
      };
    } catch {
      return { status: 'offline', latencyMs: Math.round(performance.now() - start), version: '' };
    }
  }
}

export const apiClient = new SeclystApiClient();
