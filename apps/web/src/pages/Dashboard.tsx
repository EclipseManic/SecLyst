import React, { useEffect, useMemo, useRef, useState } from 'react';
import { TOOLS_REGISTRY } from '../data/workspace';
import type { ActivityItem, ToolDefinition, ToolId } from '../data/workspace';
import type { PlatformSummary } from '../lib/api-client';
import { ToolIcon } from '../lib/icons';

const ANALYSIS_TOOLS: ToolId[] = ['ioc', 'malware', 'phishing', 'events'];

const ACTIVE_JOB_STATUSES = ['queued', 'running', 'waiting_provider', 'waiting_rate_limit', 'retrying'];

/* What each engine does, and the moment it is the right one to open. Short
   enough to read in one pass; the guide below is the page's spine. */
const ENGINE_GUIDE: Record<ToolId, { does: string; when: string }> = {
  ioc: {
    does: 'Checks IPs, domains, hashes, URLs and wallets against several threat-intelligence providers at once.',
    when: 'A link, address or file hash looks wrong and you want context before you act on it.',
  },
  malware: {
    does: 'Inspects a file statically, watches it in a sandbox, and matches YARA rules.',
    when: 'You have a file and need to know what it does before opening or running it.',
  },
  phishing: {
    does: 'Checks an email’s sender, routing, links and attachments for signs of a scam.',
    when: 'An email asks you to click, pay, or sign in, and something feels off.',
  },
  events: {
    does: 'Searches Windows event logs and runs Sigma hunts across them.',
    when: 'You have log files and need a timeline, one specific event, or a threat hunt.',
  },
  ruleforge: {
    does: 'Translates a detection rule from one SIEM’s language into another.',
    when: 'You have a working rule and need it in Splunk, Sentinel, Elastic or QRadar.',
  },
};

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

function prefersReducedMotion(): boolean {
  return typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

function SectionHead({ kicker, title, lede }: { kicker: string; title: string; lede: string }) {
  return (
    <div className="home-section-head">
      <span className="home-kicker">{kicker}</span>
      <h2 className="home-h2">{title}</h2>
      <p className="home-lede">{lede}</p>
    </div>
  );
}

function EmptyNote({ title, body }: { title: string; body: string }) {
  return (
    <div className="home-empty">
      <strong>{title}</strong>
      <span>{body}</span>
    </div>
  );
}

/* The home screen answers the first question a workbench has to answer — what
   is this, and what do I do with it — before showing any controls. It leads
   with a plain-language welcome and real live status, explains the five
   engines in a "use this when" guide, then lets the analyst start. Every
   figure comes from the supervisor or the job queue; nothing is invented. */
export function Dashboard({
  backendStatus,
  activity,
  summary,
  onOpenTool,
  onQuickIoc,
  onOpenActivity,
  onOpenActivityItem,
  onClearActivity
}: {
  backendStatus: Record<ToolId, EngineState>;
  activity: ActivityItem[];
  summary: PlatformSummary | null;
  onOpenTool: (tool: ToolId) => void;
  onQuickIoc: (value: string) => void;
  onOpenActivity: () => void;
  onOpenActivityItem: (item: ActivityItem) => void;
  onClearActivity: () => void;
}) {
  const [objective, setObjective] = useState('');
  const [selectedTool, setSelectedTool] = useState<ToolId>('ioc');
  const [jobs, setJobs] = useState<JobRow[]>([]);
  const [jobsState, setJobsState] = useState<RegionState>('loading');
  const [confirmClear, setConfirmClear] = useState(false);
  const objectiveRef = useRef<HTMLTextAreaElement>(null);
  const intakeRef = useRef<HTMLElement>(null);

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

  // Clearing the timeline is a two-press action; an armed confirm that is not
// followed through should disarm on its own.
  useEffect(() => {
    if (!confirmClear) return;
    const timer = window.setTimeout(() => setConfirmClear(false), 4000);
    return () => window.clearTimeout(timer);
  }, [confirmClear]);

  const tools = useMemo(() => Object.values(TOOLS_REGISTRY) as ToolDefinition[], []);
  const online = tools.filter((tool) => backendStatus[tool.id] === 'online').length;
  const activeJobs = jobs.filter((job) => ACTIVE_JOB_STATUSES.includes(job.status));
  const counts = summary?.collections;
  const recordsTotal = summary
    ? tools.reduce((sum, tool) => sum + (counts?.[tool.id]?.count ?? 0), 0)
    : null;

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

  const goTo = (id: string) => {
    document.getElementById(id)?.scrollIntoView({
      behavior: prefersReducedMotion() ? 'auto' : 'smooth',
      block: 'start'
    });
  };

  const startAnalysis = () => {
    intakeRef.current?.scrollIntoView({
      behavior: prefersReducedMotion() ? 'auto' : 'smooth',
      block: 'center'
    });
    objectiveRef.current?.focus({ preventScroll: true });
  };

  return (
    <div className="home">
      {/* ---------------------------------------------------------------- */}
      {/* HERO — what this is, in plain language                           */}
      {/* ---------------------------------------------------------------- */}
      <section className="home-hero" aria-label="Welcome to SecLyst">
        <div className="home-hero-copy">
          <span className="home-eyebrow">
            <span className="home-eyebrow-dot" aria-hidden="true" />
            Local security workbench · five engines
          </span>

          <h1 className="home-title">Know what you’re looking at.</h1>

          <p className="home-hero-lede">
            SecLyst is a private workbench that puts five security tools in one place. Bring a suspicious
            link, an email, a file, a log export or a detection rule — work out what is really going on,
            and keep the evidence on your own machine.
          </p>

          <div className="home-hero-actions">
            <button type="button" className="ui-btn ui-btn--primary" onClick={startAnalysis}>
              Start an analysis
            </button>
            <button type="button" className="ui-btn ui-btn--ghost" onClick={() => goTo('home-guide')}>
              See which tool to use
            </button>
          </div>

          <ul className="home-facts">
            <li>
              <strong>Local</strong>
              <span>Runs on 127.0.0.1</span>
            </li>
            <li>
              <strong>5</strong>
              <span>Focused engines</span>
            </li>
            <li>
              <strong>Private</strong>
              <span>Password protected</span>
            </li>
          </ul>
        </div>

        <aside className="home-live" aria-label="Live system status">
          <div className="home-live-head">
            <span className="home-kicker">Right now</span>
            <span
              className="home-live-badge"
              data-state={online === tools.length ? 'online' : 'unknown'}
            >
              {online === tools.length ? 'All engines ready' : `${tools.length - online} need attention`}
            </span>
          </div>

          <div className="home-live-big">
            <strong className="sc-mono">
              {online}
              <span>/{tools.length}</span>
            </strong>
            <span className="home-live-big-label">engines online</span>
          </div>

          <dl className="home-live-stats">
            <div>
              <dt>Records indexed</dt>
              <dd className="sc-mono">{recordsTotal === null ? '—' : recordsTotal.toLocaleString()}</dd>
            </div>
            <div>
              <dt>Jobs in progress</dt>
              <dd className="sc-mono">{jobsState === 'ready' ? activeJobs.length : '—'}</dd>
            </div>
          </dl>

          <ul className="home-live-engines">
            {tools.map((tool) => (
              <li key={tool.id} data-tool={tool.id}>
                <span className="home-live-dot" data-state={backendStatus[tool.id]} aria-hidden="true" />
                <span className="home-live-name">
                  <ToolIcon tool={tool.id} size={13} />
                  {tool.shortName}
                </span>
                <span className="home-live-state">{stateWord(backendStatus[tool.id])}</span>
              </li>
            ))}
          </ul>
        </aside>
      </section>

      {/* ---------------------------------------------------------------- */}
      {/* WHAT THIS IS                                                     */}
      {/* ---------------------------------------------------------------- */}
      <section className="home-section" aria-label="What SecLyst is">
        <SectionHead
          kicker="What this is"
          title="A small, private toolkit — not another dashboard."
          lede="One analyst, one machine, five tools that each do one job well and keep the result in the same place."
        />

        <div className="home-pillars">
          <div className="home-pillar">
            <span className="home-kicker">01</span>
            <h3>Private by design</h3>
            <p>
              The engines, their databases and your evidence run on this machine. There is no cloud
              account and nothing is uploaded for you.
            </p>
          </div>
          <div className="home-pillar">
            <span className="home-kicker">02</span>
            <h3>Five tools, one workspace</h3>
            <p>
              Indicators, malware, phishing, Windows events and detection rules share one shell, one look
              and one history.
            </p>
          </div>
          <div className="home-pillar">
            <span className="home-kicker">03</span>
            <h3>Evidence you can reopen</h3>
            <p>
              Every run is stored with its score and artifacts, so you can come back to it instead of
              rebuilding the investigation.
            </p>
          </div>
        </div>
      </section>

      {/* ---------------------------------------------------------------- */}
      {/* HOW TO USE IT                                                    */}
      {/* ---------------------------------------------------------------- */}
      <section className="home-section" aria-label="How to use SecLyst">
        <SectionHead
          kicker="How to use it"
          title="Three steps, every time."
          lede="You do not need to learn five tools. Bring the question; the guide tells you where it belongs."
        />

        <ol className="home-steps">
          <li className="home-step">
            <span className="home-step-num sc-mono">Step 1</span>
            <h3>Bring the question</h3>
            <p>A suspicious link, an email, a file, a log export, or a rule that needs translating.</p>
          </li>
          <li className="home-step">
            <span className="home-step-num sc-mono">Step 2</span>
            <h3>Pick the engine</h3>
            <p>The guide below says which tool fits which question — in one line, with no guessing.</p>
          </li>
          <li className="home-step">
            <span className="home-step-num sc-mono">Step 3</span>
            <h3>Read it, keep it</h3>
            <p>Check the score and the evidence, then move on. The run stays here for next time.</p>
          </li>
        </ol>
      </section>

      {/* ---------------------------------------------------------------- */}
      {/* WHICH TOOL, AND WHEN                                             */}
      {/* ---------------------------------------------------------------- */}
      <section className="home-section" id="home-guide" aria-label="Which tool to use and when">
        <SectionHead
          kicker="Which tool, and when"
          title="Match the question to the engine."
          lede="The middle column is what it does. The right column is the moment to open it."
        />

        <div className="home-guide">
          <div className="home-guide-head" aria-hidden="true">
            <span>Tool</span>
            <span>What it does</span>
            <span>Use it when</span>
            <span />
          </div>

          {tools.map((tool) => {
            const guide = ENGINE_GUIDE[tool.id];
            return (
              <div className="home-guide-row" key={tool.id} data-tool={tool.id}>
                <div className="home-guide-tool">
                  <span className="home-guide-mark">
                    <ToolIcon tool={tool.id} size={16} />
                  </span>
                  <span className="home-guide-toolcopy">
                    <strong>{tool.shortName}</strong>
                    <span className="home-guide-state" data-state={backendStatus[tool.id]}>
                      <i aria-hidden="true" />
                      {stateWord(backendStatus[tool.id])}
                    </span>
                  </span>
                </div>

                <div className="home-guide-cell home-guide-does">
                  <span className="home-guide-cap">What it does</span>
                  <p>{guide.does}</p>
                </div>

                <div className="home-guide-cell home-guide-when">
                  <span className="home-guide-cap">Use it when</span>
                  <p>{guide.when}</p>
                </div>

                <div className="home-guide-open">
                  <button
                    type="button"
                    className="ui-btn ui-btn--ghost ui-btn--sm"
                    onClick={() => onOpenTool(tool.id)}
                    aria-label={`Open ${tool.name}`}
                  >
                    Open
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* ---------------------------------------------------------------- */}
      {/* START HERE                                                       */}
      {/* ---------------------------------------------------------------- */}
      <section className="home-section" id="home-start" ref={intakeRef} aria-label="Start an analysis">
        <SectionHead
          kicker="Start here"
          title="Start with what you have."
          lede="Paste an indicator to open IOC Lookup with it, or choose an engine and go straight in."
        />

        <div className="home-start-card">
          <form
            className="home-start-form"
            onSubmit={(event) => {
              event.preventDefault();
              start();
            }}
          >
            <label className="home-field">
              <span className="ui-label">What are you looking at?</span>
              <textarea
                ref={objectiveRef}
                rows={3}
                value={objective}
                onChange={(event) => setObjective(event.target.value)}
                placeholder="Paste a link, IP address, domain, file hash — or describe what happened."
              />
            </label>

            <div className="home-start-tools" role="group" aria-label="Choose an engine">
              {ANALYSIS_TOOLS.map((id) => (
                <button
                  key={id}
                  type="button"
                  aria-pressed={selectedTool === id}
                  onClick={() => setSelectedTool(id)}
                >
                  <ToolIcon tool={id} size={15} />
                  <span>{TOOLS_REGISTRY[id].shortName}</span>
                </button>
              ))}
            </div>

            <div className="home-start-foot">
              <span className="ui-meta">
                {selectedTool === 'ioc'
                  ? 'IOC Lookup opens with this indicator already entered.'
                  : `${TOOLS_REGISTRY[selectedTool].shortName} opens at its own intake.`}
              </span>
              <button type="submit" className="ui-btn ui-btn--primary" disabled={!canStart}>
                {selectedTool === 'ioc' ? 'Look it up' : 'Open engine'}
              </button>
            </div>
          </form>
        </div>
      </section>

      {/* ---------------------------------------------------------------- */}
      {/* LIVE ACTIVITY                                                    */}
      {/* ---------------------------------------------------------------- */}
      <section className="home-section" aria-label="Live activity">
        <SectionHead
          kicker="While you work"
          title="What is running, and what you found."
          lede="Background jobs and the latest results, kept together so the workspace stays a record."
        />

        <div className="home-pulse">
          <div className="ui-card home-card">
            <div className="ui-card-head">
              <span className="ui-card-title">Active work</span>
              <span className="ui-meta">
                {jobsState === 'ready' ? `${activeJobs.length} running` : 'Durable job queue'}
              </span>
            </div>

            {jobsState === 'loading' && (
              <div className="home-rows">
                <span className="home-skeleton" />
                <span className="home-skeleton" />
              </div>
            )}
            {jobsState === 'unavailable' && (
              <EmptyNote
                title="Durable jobs are off"
                body="Start with SECLYST_DURABLE_JOBS=true to record background work here."
              />
            )}
            {jobsState === 'error' && (
              <EmptyNote title="Queue unavailable" body="The control plane did not answer this request." />
            )}
            {jobsState === 'ready' &&
              (activeJobs.length === 0 ? (
                <EmptyNote
                  title="No active jobs"
                  body="Progress from malware, phishing, IOC, event and rule jobs appears here."
                />
              ) : (
                <div className="home-rows">
                  {activeJobs.slice(0, 6).map((job) => (
                    <div key={job.id} className="home-job">
                      <span className="home-job-tool sc-mono">{job.tool}</span>
                      <span className="home-job-op">
                        {job.operation}
                        <small>{job.stage}</small>
                      </span>
                      <span className="home-state" data-state={jobState(job.status)}>
                        {job.status.replace(/_/g, ' ')}
                      </span>
                      <span className="home-job-num sc-mono">{job.progress}%</span>
                    </div>
                  ))}
                </div>
              ))}
          </div>

          <div className="ui-card home-card">
            <div className="ui-card-head">
              <span className="ui-card-title">Recent activity</span>
              <span className="home-card-actions">
                <button
                  type="button"
                  className="ui-btn ui-btn--quiet ui-btn--sm"
                  data-confirm={confirmClear ? 'true' : undefined}
                  disabled={activity.length === 0}
                  onClick={() => {
                    if (!confirmClear) {
                      setConfirmClear(true);
                      return;
                    }
                    setConfirmClear(false);
                    onClearActivity();
                  }}
                  onBlur={() => setConfirmClear(false)}
                  title={confirmClear ? 'Press again to clear every row' : 'Clear the activity shown here'}
                >
                  {confirmClear ? 'Confirm' : 'Clear'}
                </button>
                <button type="button" className="ui-btn ui-btn--ghost ui-btn--sm" onClick={onOpenActivity}>
                  All activity
                </button>
              </span>
            </div>

            {activity.length === 0 ? (
              <EmptyNote
                title="Nothing recorded yet"
                body="Run an analysis in any engine; its result is summarised here."
              />
            ) : (
              <div className="home-rows">
                {activity.slice(0, 6).map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className="home-activity-row"
                    data-tool={item.tool}
                    onClick={() => onOpenActivityItem(item)}
                    aria-label={`Open ${TOOLS_REGISTRY[item.tool].name}: ${item.actionType} — ${item.description}`}
                  >
                    <span className="home-activity-mark" aria-hidden="true">
                      <ToolIcon tool={item.tool} size={14} />
                    </span>
                    <span className="home-activity-copy">
                      <strong>{item.actionType}</strong>
                      <small>{item.description}</small>
                    </span>
                    <time>{item.timestamp}</time>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </section>

      <footer className="home-foot">
        <span>SecLyst runs only on this machine. Everything you do here stays here.</span>
        <span className="sc-mono">127.0.0.1</span>
      </footer>
    </div>
  );
}