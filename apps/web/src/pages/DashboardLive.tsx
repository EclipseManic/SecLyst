// ==========================================================================
// live command centre
// ==========================================================================
import React from 'react';
import { useMemo, useState } from 'react';
import { TOOLS_REGISTRY } from '../data/workspace';
import type { ActivityItem, PageRouteId, ToastMessage, ToolDefinition, ToolId } from '../data/workspace';
import type { PlatformSummary } from '../lib/api-client';
import { downloadFileBlob } from '../lib/api-client';
import { ToolIcon } from '../lib/icons';
import { VerdictBadge } from '../ui/index';

export const CommandCenterDashboard: React.FC<{
  activityFeed: ActivityItem[];
  backendStatus: Record<ToolId, 'online' | 'offline' | 'unknown'>;
  summary: PlatformSummary | null;
  refreshing: boolean;
  onRefresh: () => void;
  onNavigate: (page: PageRouteId, mainTab?: string, subTab?: string) => void;
  onAddToast: (toast: Omit<ToastMessage, 'id'>) => void;
}> = ({ activityFeed, backendStatus, summary, refreshing, onRefresh, onNavigate, onAddToast }) => {
  const [selectedTools, setSelectedTools] = useState<Record<ToolId, boolean>>({
    malware: true,
    ioc: true,
    events: true,
    phishing: true,
    ruleforge: true
  });

  const toolDefinitions = Object.values(TOOLS_REGISTRY) as ToolDefinition[];
  const filteredActivity = useMemo(
    () => activityFeed.filter((item) => selectedTools[item.tool]),
    [activityFeed, selectedTools]
  );
  const onlineCount = Object.values(backendStatus).filter((status) => status === 'online').length;
  const respondingCollections = toolDefinitions.filter(
    (tool) => summary?.collections[tool.id]?.available
  ).length;
  const storedRecords = toolDefinitions.reduce(
    (total, tool) => total + (summary?.collections[tool.id]?.count ?? 0),
    0
  );

  const exportActivity = () => {
    const header = 'ID,Timestamp,Tool,Action,Description\n';
    const rows = filteredActivity
      .map((item) =>
        [item.id, item.timestamp, item.tool, item.actionType, item.description]
          .map((value) => `"${String(value).replace(/"/g, '""')}"`)
          .join(',')
      )
      .join('\n');
    downloadFileBlob('seclyst-activity.csv', header + rows, 'text/csv');
    onAddToast({
      type: 'success',
      title: 'Activity exported',
      description: `${filteredActivity.length} live records were written to CSV.`
    });
  };

  return (
    <div className="sc-page">
      <header className="sc-page-head">
        <div className="sc-page-head-main">
          <div className="sc-crumbs">
            Seclyst <span className="sc-crumbs-sep">/</span> Command Center
          </div>
          <h1 className="sc-page-title">Command Center</h1>
          <p className="sc-page-desc">
            Live engine health and stored work from the five original tools. Counts remain empty
            until a backend reports them; Seclyst does not synthesize operational data.
          </p>
        </div>
        <div className="sc-page-actions">
          <button type="button" className="ui-btn ui-btn--ghost" onClick={onRefresh} disabled={refreshing}>
            {refreshing ? 'Refreshing' : 'Refresh'}
          </button>
        </div>
      </header>

      <section className="ui-metrics" aria-label="Platform summary">
        <div className="ui-metric">
          <div className="ui-metric-value">{onlineCount} of 5</div>
          <div className="ui-metric-label">Engines online</div>
          <div className="ui-metric-hint">measured through live health endpoints</div>
        </div>
        <div className="ui-metric">
          <div className="ui-metric-value">{storedRecords}</div>
          <div className="ui-metric-label">Stored records</div>
          <div className="ui-metric-hint">reported by available engine collections</div>
        </div>
        <div className="ui-metric">
          <div className="ui-metric-value">{respondingCollections} of 5</div>
          <div className="ui-metric-label">Collections responding</div>
          <div className="ui-metric-hint">history and investigation endpoints</div>
        </div>
        <div className="ui-metric">
          <div className="ui-metric-value">{activityFeed.length}</div>
          <div className="ui-metric-label">Recent records loaded</div>
          <div className="ui-metric-hint">
            {summary ? `refreshed ${new Date(summary.generatedAt).toLocaleTimeString()}` : 'waiting for Seclyst'}
          </div>
        </div>
      </section>

      <div className="cc-divider" aria-hidden="true" />

      <section className="cc-posture" aria-label="Engine status and stored records">
        <div className="cc-posture-head">
          <div>
            <div className="ui-card-title">The five workbenches</div>
            <div className="ui-card-sub">Open each tool in its original interface</div>
          </div>
          <span className="ui-badge">Live state</span>
        </div>
        <div className="cc-posture-cols">
          <span>Tool</span>
          <span>Stored</span>
          <span>Backend</span>
          <span>Collection</span>
          <span />
        </div>
        {toolDefinitions.map((tool) => {
          const collection = summary?.collections[tool.id];
          const status = backendStatus[tool.id];
          return (
            <button
              key={tool.id}
              type="button"
              data-tool={tool.id}
              className="cc-posture-row"
              onClick={() => onNavigate(tool.id, tool.mainTabs[1].id, tool.subTabs[0].id)}
            >
              <span className="cc-posture-tool">
                <span className="ui-tool-mark"><ToolIcon tool={tool.id} size={16} /></span>
                <span className="cc-posture-text">
                  <span className="cc-posture-name block">{tool.shortName}</span>
                  <span className="cc-posture-tag block">{tool.tagline}</span>
                </span>
              </span>
              <span className="cc-posture-metric">{collection?.available ? collection.count : 'Unavailable'}</span>
              <VerdictBadge
                verdict={status === 'online' ? 'clean' : status === 'offline' ? 'malicious' : 'unknown'}
                label={status === 'online' ? 'Online' : status === 'offline' ? 'Offline' : 'Starting'}
              />
              <span className="ui-meta">{collection?.available ? 'Responding' : 'No response'}</span>
              <span className="cc-posture-open">Open</span>
            </button>
          );
        })}
      </section>

      <section className="ui-card ui-card--flush" aria-label="Recent stored work">
        <div className="ui-card-head">
          <div>
            <div className="ui-card-title">Recent stored work</div>
            <div className="ui-card-sub">Records returned by the copied engines</div>
          </div>
          <button type="button" className="ui-btn ui-btn--ghost ui-btn--sm" onClick={exportActivity} disabled={!filteredActivity.length}>
            Export CSV
          </button>
        </div>
        <div className="cc-filters" aria-label="Filter recent records by tool">
          {toolDefinitions.map((tool) => (
            <label key={tool.id} className="ui-meta flex items-center gap-1.5">
              <input
                type="checkbox"
                checked={selectedTools[tool.id]}
                onChange={(event) => setSelectedTools({ ...selectedTools, [tool.id]: event.target.checked })}
              />
              {tool.shortName}
            </label>
          ))}
        </div>
        {filteredActivity.length === 0 ? (
          <div className="ui-empty">
            <span className="ui-h3">No stored work yet</span>
            <span className="ui-body">Run an analysis in one of the five workbenches, then refresh.</span>
          </div>
        ) : (
          <div className="cc-timeline-list">
            {filteredActivity.map((item) => (
              <button
                key={item.id}
                type="button"
                className="cc-timeline-row"
                onClick={() => onNavigate(item.tool)}
              >
                <span className="cc-timeline-tool" data-tool={item.tool}>
                  <ToolIcon tool={item.tool} size={14} />
                  {TOOLS_REGISTRY[item.tool].shortName}
                </span>
                <span className="cc-timeline-body">
                  <span className="ui-strong">{item.actionType}</span>
                  <span className="ui-body">{item.description}</span>
                </span>
                <span className="ui-meta sc-mono">{item.timestamp}</span>
              </button>
            ))}
          </div>
        )}
      </section>
    </div>
  );
};
