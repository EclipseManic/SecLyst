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
  ruleforge: 'Rule history'
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
    if (typeof value === 'number') return String(value);
  }
  return '';
}

export function summaryToActivity(summary: PlatformSummary): ActivityItem[] {
  const rows: ActivityItem[] = [];
  (Object.entries(summary.collections) as [ToolId, PlatformCollection][]).forEach(([tool, collection]) => {
    collection.records.forEach((record, index) => {
      const recordId = recordText(record, ['id', 'scan_id', 'investigation_id', 'ioc_id']);
      const subjectRaw = recordText(record, ['filename', 'ioc', 'name', 'title', 'rule_name', 'source']);
      const subject = subjectRaw || 'Stored record';
      const state = recordText(record, ['verdict', 'severity', 'status', 'action', 'origin']);
      const rawTime = recordText(record, ['timestamp', 'updated_at', 'created_at', 'last_lookup', 'saved_at']);
      const parsedTime = rawTime ? new Date(rawTime) : null;
      const timestamp = parsedTime && !Number.isNaN(parsedTime.getTime())
        ? parsedTime.toLocaleString()
        : rawTime || 'Time unavailable';
      // Records without their own id fall back to their content, not their
      // index: clearing the feed keys off this id, and an index would make a
      // brand-new record inherit an old row's dismissed state.
      const stableId = recordId || `${subjectRaw || 'record'}-${rawTime || index}`;
      rows.push({
        id: `${tool}-${stableId}`,
        tool,
        actionType: ACTIVITY_LABELS[tool],
        description: state ? `${subject}: ${state}` : subject,
        timestamp,
        severity: 'info',
        targetSubTab: ACTIVITY_TARGETS[tool],
        // IOC Lookup is the one engine whose deep-link contract the shell
        // already uses, so an indicator is carried through and looked up.
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
