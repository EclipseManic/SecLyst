import type { ToolId } from '../../data/workspace';

export const FRAME_PROTOCOL = 'seclyst-tool/v1' as const;

export type ToolBridgeMessageType =
  | 'tool.ready'
  | 'route.changed'
  | 'job.started'
  | 'job.updated'
  | 'job.completed'
  | 'result.opened'
  | 'unsaved.changed';

export interface ToolBridgeMessage {
  protocol: typeof FRAME_PROTOCOL;
  tool: ToolId;
  type: ToolBridgeMessageType;
  payload: Record<string, unknown>;
  message_id: string;
}

const MESSAGE_TYPES = new Set<ToolBridgeMessageType>([
  'tool.ready',
  'route.changed',
  'job.started',
  'job.updated',
  'job.completed',
  'result.opened',
  'unsaved.changed'
]);

export function parseToolBridgeMessage(value: unknown): ToolBridgeMessage | null {
  if (!value || typeof value !== 'object') return null;
  const candidate = value as Partial<ToolBridgeMessage>;
  if (candidate.protocol !== FRAME_PROTOCOL) return null;
  if (typeof candidate.tool !== 'string') return null;
  if (typeof candidate.type !== 'string' || !MESSAGE_TYPES.has(candidate.type as ToolBridgeMessageType)) return null;
  if (typeof candidate.message_id !== 'string' || !candidate.message_id) return null;
  if (!candidate.payload || typeof candidate.payload !== 'object' || Array.isArray(candidate.payload)) return null;
  return candidate as ToolBridgeMessage;
}

export function endpointOrigin(endpoint?: string): string | null {
  if (!endpoint) return null;
  try {
    return new URL(endpoint).origin;
  } catch {
    return null;
  }
}

export function isTrustedToolMessage(
  event: Pick<MessageEvent, 'origin' | 'source'>,
  endpoint: string | undefined,
  frameWindow: Window | null
): boolean {
  const expectedOrigin = endpointOrigin(endpoint);
  return Boolean(expectedOrigin && event.origin === expectedOrigin && frameWindow && event.source === frameWindow);
}
