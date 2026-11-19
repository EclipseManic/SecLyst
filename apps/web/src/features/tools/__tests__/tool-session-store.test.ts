import { describe, expect, it } from 'vitest';
import {
  activateToolSession,
  createToolSessions,
  updateToolSessionQuery
} from '../tool-session-store';

describe('tool session store', () => {
  it('starts every tool without a retained route', () => {
    const sessions = createToolSessions();
    expect(Object.values(sessions).every((session) => session.query === '' && session.lastActiveAt === 0)).toBe(true);
  });

  it('updates one tool without mutating another tool session', () => {
    const sessions = createToolSessions();
    const withQuery = updateToolSessionQuery(sessions, 'ioc', '?page=lookup&ioc=example.org');
    expect(withQuery).not.toBe(sessions);
    expect(withQuery.ioc.query).toBe('?page=lookup&ioc=example.org');
    expect(withQuery.malware).toBe(sessions.malware);
  });

  it('retains a query while recording later activation', () => {
    const sessions = updateToolSessionQuery(createToolSessions(), 'ioc', '?page=lookup&tool=batch');
    const activated = activateToolSession(sessions, 'ioc', 42);
    expect(activated.ioc).toEqual({ query: '?page=lookup&tool=batch', lastActiveAt: 42 });
  });
});
