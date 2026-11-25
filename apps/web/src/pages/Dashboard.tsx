import React, { useEffect, useMemo, useRef, useState } from 'react';
import { TOOLS_REGISTRY } from '../data/workspace';
import type { ActivityItem, ToolDefinition, ToolId } from '../data/workspace';
import type { PlatformSummary } from '../lib/api-client';
import { ToolIcon } from '../lib/icons';

const ANALYSIS_TOOLS: ToolId[] = ['ioc', 'malware', 'phishing', 'events'];

const ACTIVE_JOB_STATUSES = ['queued', 'running', 'waiting_provider', 'waiting_rate_limit', 'retrying'];

interface JobRow {
  id: string;
  tool: string;
  operation: string;
  status: string;
  progress: number;
  stage: string;
}

type EngineState = 'online' | 'offline' | 'unknown';
type RegionState = 'loading' | 'ready' | 'unavailable' | 'error';

function stateWord(state: EngineState): string {
  if (state === 'online') return 'Online';
  if (state === 'unknown') return 'Starting';
  return 'Offline';
}

function jobState(status: string): EngineState {
  if (status === 'running') return 'online';
  if (status === 'failed' || status === 'cancelled') return 'offline';
  return 'unknown';
}

function JobEmpty({ title, body }: { title: string; body: string }) {
  return (
    <div className="cc-empty">
      <strong>{title}</strong>
      <span>{body}</span>
    </div>
  );
}

/* The command center is one working surface, not a landing page: a compact
   intake bar, then the engine ledger — the object this workbench is known by —
   then active work and recent activity side by side. Every figure comes from
   the supervisor or the job queue, and every region has its own empty state. */
export function Dashboard({
  backendStatus,
  activity,
  summary,
  onOpenTool,
  onQuickIoc,
  onOpenActivity
}: {
  backendStatus: Record<ToolId, EngineState>;
  activity: ActivityItem[];
  summary: PlatformSummary | null;
  onOpenTool: (tool: ToolId) => void;
  onQuickIoc: (value: string) => void;
  onOpenActivity: () => void;
}) {
  const [objective, setObjective] = useState('');
  const [selectedTool, setSelectedTool] = useState<ToolId>('ioc');
  const [jobs, setJobs] = useState<JobRow[]>([]);
  const [jobsState, setJobsState] = useState<RegionState>('loading');
  const objectiveRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    let cancelled = false;
    fetch('/api/v1/jobs?limit=50', { headers: { Accept: 'application/json' }, cache: 'no-store' })
      .then(async (response) => {
        if (cancelled) return;
        if (response.status === 503) {
          setJobsState('unavailable');
          return;
        }
        if (!response.ok) {
          setJobsState('error');
          return;
        }
        const data: unknown = await response.json();
        if (cancelled) return;
        setJobs(Array.isArray(data) ? (data as JobRow[]) : []);
        setJobsState('ready');
      })
      .catch(() => {
        if (!cancelled) setJobsState('error');
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const tools = useMemo(() => Object.values(TOOLS_REGISTRY) as ToolDefinition[], []);
  const online = tools.filter((tool) => backendStatus[tool.id] === 'online').length;
  const activeJobs = jobs.filter((job) => ACTIVE_JOB_STATUSES.includes(job.status));
  const counts = summary?.collections;

  // An objective is only carried into IOC lookup, where it becomes the query.
  // The other engines open at their own intake, so they need no text first.
  const canStart = selectedTool === 'ioc' ? objective.trim().length > 0 : true;

  const start = () => {
    if (selectedTool === 'ioc' && objective.trim()) {
      onQuickIoc(objective.trim());
      return;
    }
    onOpenTool(selectedTool);
  };

  return (
    <div className="cc">
      <header className="cc-head">
        <div className="cc-head-main">
          <h1 className="ui-h1">Command center</h1>
          <p className="ui-body">
            Start an analysis below, or open an engine from the ledger. Each engine keeps its own screens and
            its own work.
          </p>
        </div>
        <div className="cc-head-stat">
          <span className="ui-label">Engines online</span>
          <strong className="cc-readout sc-mono">
            {online}
            <span>/{tools.length}</span>
          </strong>
        </div>
      </header>

      <section className="cc-intake" aria-label="Start a new analysis">
        <label className="cc-intake-field">
          <span className="ui-label">Objective</span>
          <textarea
            ref={objectiveRef}
            rows={2}
            value={objective}
            onChange={(event) => setObjective(event.target.value)}
            placeholder="What do you need to determine? For example: is this email malicious, and which indicators does it carry?"
          />
        </label>

        <div className="cc-intake-actions">
          <button type="button" className="ui-btn ui-btn--primary" disabled={!canStart} onClick={start}>
            {selectedTool === 'ioc' ? 'Look up' : 'Open engine'}
          </button>
        </div>

        <div className="cc-intake-tools" role="group" aria-label="Leading engine">
          {ANALYSIS_TOOLS.map((id) => (
            <button
              key={id}
              type="button"
              aria-pressed={selectedTool === id}
              onClick={() => setSelectedTool(id)}
            >
              <ToolIcon tool={id} size={16} />
              <span>{TOOLS_REGISTRY[id].shortName}</span>
            </button>
          ))}
        </div>
      </section>

      <section className="cc-ledger" aria-label="Engines">
        <div className="ui-section-head">
          <h2 className="ui-h2">Engines</h2>
          <span className="ui-meta">Live status from the local supervisor</span>
        </div>

        <div className="cc-table">
          <div className="cc-table-head" aria-hidden="true">
            <span>Engine</span>
            <span>Status</span>
            <span>Records</span>
            <span>Latest activity</span>
            <span />
          </div>

          {tools.map((tool) => {
            const state = backendStatus[tool.id];
            const count = counts?.[tool.id]?.count;
            const latest = activity.find((item) => item.tool === tool.id);
            return (
              <button
                key={tool.id}
                type="button"
                className="cc-row"
                data-tool={tool.id}
                aria-label={`Open ${tool.name}`}
                onClick={() => onOpenTool(tool.id)}
              >
                <span className="cc-engine">
                  <span className="cc-engine-mark">
                    <ToolIcon tool={tool.id} size={15} />
                  </span>
                  <span className="cc-engine-copy">
                    <strong>{tool.shortName}</strong>
                    <small>{tool.tagline}</small>
                  </span>
                </span>
                <span className="cc-state" data-state={state}>
                  {stateWord(state)}
                </span>
                <span className="cc-num sc-mono">{typeof count === 'number' ? count : '—'}</span>
                <span className="cc-latest">{latest ? latest.description : 'No stored records yet'}</span>
                <span className="cc-open">Open</span>
              </button>
            );
          })}
        </div>
      </section>

      <section className="cc-split">
        <div className="ui-card cc-queue">
          <div className="ui-card-head">
            <span className="ui-card-title">Active work</span>
            <span className="ui-meta">
              {jobsState === 'ready' ? `${activeJobs.length} running` : 'Durable job queue'}
            </span>
          </div>

          {jobsState === 'loading' && (
            <div className="cc-rows">
              <span className="cc-skeleton" />
              <span className="cc-skeleton" />
            </div>
          )}
          {jobsState === 'unavailable' && (
            <JobEmpty
              title="Durable jobs are off"
              body="Start with SECLYST_DURABLE_JOBS=true to record background work here."
            />
          )}
          {jobsState === 'error' && (
            <JobEmpty title="Queue unavailable" body="The control plane did not answer this request." />
          )}
          {jobsState === 'ready' &&
            (activeJobs.length === 0 ? (
              <JobEmpty
                title="No active jobs"
                body="Progress from malware, phishing, IOC, event and rule jobs appears here."
              />
            ) : (
              <div className="cc-rows">
                {activeJobs.slice(0, 8).map((job) => (
                  <div key={job.id} className="cc-job">
                    <span className="cc-job-tool sc-mono">{job.tool}</span>
                    <span className="cc-job-op">
                      {job.operation}
                      <small>{job.stage}</small>
                    </span>
                    <span className="cc-state" data-state={jobState(job.status)}>
                      {job.status.replace(/_/g, ' ')}
                    </span>
                    <span className="cc-num sc-mono">{job.progress}%</span>
                  </div>
                ))}
              </div>
            ))}
        </div>

        <div className="ui-card cc-activity">
          <div className="ui-card-head">
            <span className="ui-card-title">Recent activity</span>
            <button type="button" className="ui-btn ui-btn--ghost ui-btn--sm" onClick={onOpenActivity}>
              All activity
            </button>
          </div>

          {activity.length === 0 ? (
            <JobEmpty
              title="Nothing recorded yet"
              body="Run an analysis in any engine; its result is summarised here."
            />
          ) : (
            <div className="cc-rows">
              {activity.slice(0, 8).map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className="cc-activity-row"
                  onClick={() => onOpenTool(item.tool)}
                >
                  <span className="cc-activity-mark">
                    <ToolIcon tool={item.tool} size={14} />
                  </span>
                  <span className="cc-activity-copy">
                    <strong>{item.actionType}</strong>
                    <small>{item.description}</small>
                  </span>
                  <time>{item.timestamp}</time>
                </button>
              ))}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}