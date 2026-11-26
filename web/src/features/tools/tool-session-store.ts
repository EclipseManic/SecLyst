import type { ToolId } from '../../data/workspace';

export interface ToolSession {
  query: string;
  lastActiveAt: number;
}

export type ToolSessionMap = Record<ToolId, ToolSession>;

export const TOOL_IDS: ToolId[] = ['ioc', 'malware', 'phishing', 'events', 'ruleforge'];

export function createToolSessions(): ToolSessionMap {
  return Object.fromEntries(
    TOOL_IDS.map((tool) => [tool, { query: '', lastActiveAt: 0 }])
  ) as ToolSessionMap;
}

export function activateToolSession(
  sessions: ToolSessionMap,
  tool: ToolId,
  now = Date.now()
): ToolSessionMap {
  return {
    ...sessions,
    [tool]: { ...sessions[tool], lastActiveAt: now }
  };
}

export function updateToolSessionQuery(
  sessions: ToolSessionMap,
  tool: ToolId,
  query: string
): ToolSessionMap {
  if (sessions[tool].query === query) return sessions;
  return {
    ...sessions,
    [tool]: { ...sessions[tool], query }
  };
}
