import { describe, expect, it } from 'vitest';
import type { PlatformCollection, PlatformSummary } from '../api-client';
import { summaryToActivity } from '../api-client';

function collection(records: Record<string, unknown>[]): PlatformCollection {
  return { count: records.length, records, available: true };
}

function summary(overrides: Partial<Record<string, PlatformCollection>>): PlatformSummary {
  return {
    generatedAt: 1_700_000_000_000,
    collections: {
      ioc: collection([]),
      malware: collection([]),
      phishing: collection([]),
      events: collection([]),
      ruleforge: collection([]),
      ...overrides
    }
  };
}

describe('summaryToActivity', () => {
  it('reads the IOC indicator from "value", not the missing "ioc" field', () => {
    // This is the exact shape /api/recent returns. The old mapper looked for an
    // "ioc" key, missed, and printed "Stored record: unknown" on every row.
    const rows = summaryToActivity(
      summary({
        ioc: collection([
          {
            id: 'ioc-1',
            value: '8.8.8.8',
            ioc_type: 'ip',
            verdict: 'malicious',
            score: 87,
            created_at: '2026-11-26T10:00:00Z'
          }
        ])
      })
    );

    expect(rows).toHaveLength(1);
    const row = rows[0];
    expect(row.id).toBe('ioc:ioc-1');
    expect(row.description).toContain('8.8.8.8');
    expect(row.description).toContain('ip');
    expect(row.description).toContain('malicious');
    expect(row.description).toContain('score 87');
    expect(row.description).not.toContain('Stored record');
    expect(row.verdict).toBe('malicious');
    expect(typeof row.recordedAt).toBe('number');
  });

  it('never prints a bare "unknown" verdict', () => {
    const rows = summaryToActivity(
      summary({
        ioc: collection([{ id: 'ioc-2', value: 'example.org', verdict: 'unknown' }])
      })
    );
    expect(rows[0].description).not.toContain('unknown');
    expect(rows[0].description).toContain('example.org');
    expect(rows[0].verdict).toBe('info');
  });

  it('keeps a content-based id stable when the engine omits its own id', () => {
    const record = { value: 'evil.example', verdict: 'suspicious', created_at: '2026-11-26T10:00:00Z' };
    const first = summaryToActivity(summary({ ioc: collection([record]) }))[0].id;
    const second = summaryToActivity(summary({ ioc: collection([{ ...record }]) }))[0].id;
    expect(first).toBe(second);
  });

  it('describes each engine with its own evidence', () => {
    const rows = summaryToActivity(
      summary({
        malware: collection([
          { id: 'm1', filename: 'dropper.exe', verdict: 'malicious', level: 'high', score: 90, file_type: 'PE32' }
        ]),
        phishing: collection([{ id: 'p1', filename: 'phish.eml', verdict: 'phishing', severity: 'high' }]),
        events: collection([{ id: 'e1', name: 'workstation-logs', status: 'complete', created_at: '2026-11-26T09:00:00Z' }]),
        ruleforge: collection([{ id: 'r1', title: 'LOLBin exec', rule_id: 'R-1', origin: 'generated', dialect: 'sigma' }])
      })
    );

    const byTool = Object.fromEntries(rows.map((row) => [row.tool, row]));
    expect(byTool.malware.description).toContain('dropper.exe');
    expect(byTool.phishing.description).toContain('phish.eml');
    expect(byTool.events.description).toContain('workstation-logs');
    expect(byTool.ruleforge.description).toContain('LOLBin exec');
    expect(byTool.ruleforge.actionType).toBe('Rule saved');
  });
});
