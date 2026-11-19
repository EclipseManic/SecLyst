import { describe, expect, it } from 'vitest';
import {
  FRAME_PROTOCOL,
  endpointOrigin,
  isTrustedToolMessage,
  parseToolBridgeMessage
} from '../frame-protocol';

describe('tool frame protocol', () => {
  const message = {
    protocol: FRAME_PROTOCOL,
    tool: 'malware',
    type: 'route.changed',
    payload: { query: '?scan=1' },
    message_id: 'message-1'
  } as const;

  it('accepts only the versioned message envelope', () => {
    expect(parseToolBridgeMessage(message)).toEqual(message);
    expect(parseToolBridgeMessage({ ...message, protocol: 'other' })).toBeNull();
    expect(parseToolBridgeMessage({ ...message, type: 'arbitrary.command' })).toBeNull();
    expect(parseToolBridgeMessage({ ...message, payload: [] })).toBeNull();
  });

  it('derives a strict endpoint origin', () => {
    expect(endpointOrigin('http://127.0.0.1:7101/path')).toBe('http://127.0.0.1:7101');
    expect(endpointOrigin('not a url')).toBeNull();
  });

  it('requires both the configured origin and exact frame window', () => {
    const frameWindow = {} as Window;
    expect(isTrustedToolMessage(
      { origin: 'http://127.0.0.1:7101', source: frameWindow },
      'http://127.0.0.1:7101/',
      frameWindow
    )).toBe(true);
    expect(isTrustedToolMessage(
      { origin: 'http://127.0.0.1:9999', source: frameWindow },
      'http://127.0.0.1:7101/',
      frameWindow
    )).toBe(false);
    expect(isTrustedToolMessage(
      { origin: 'http://127.0.0.1:7101', source: {} as Window },
      'http://127.0.0.1:7101/',
      frameWindow
    )).toBe(false);
  });
});
