// ==========================================================================
// the shared component vocabulary
// ==========================================================================
import React from 'react';
import type { ToolDefinition, VerdictType } from '../data/workspace';
import { ShellIcon, ToolIcon } from '../lib/icons';

export const Kbd: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <kbd className="sc-kbd">{children}</kbd>
);

export const VerdictBadge: React.FC<{ verdict: VerdictType | string; label?: string; size?: 'sm' | 'md' | 'lg' }> = ({
  verdict,
  label,
  size = 'sm'
}) => {
  const norm = verdict.toLowerCase();
  let color = 'var(--color-unknown)';
  let bg = 'var(--color-unknown-bg)';
  const text = label || verdict;

  if (norm === 'malicious' || norm === 'critical' || norm === 'unsafe' || norm === 'fail') {
    color = 'var(--color-malicious)';
    bg = 'var(--color-malicious-bg)';
  } else if (norm === 'suspicious' || norm === 'medium' || norm === 'high' || norm === 'cautious' || norm === 'mismatch' || norm === 'no_match') {
    color = 'var(--color-suspicious)';
    bg = 'var(--color-suspicious-bg)';
  } else if (norm === 'clean' || norm === 'low' || norm === 'safe' || norm === 'pass' || norm === 'matched' || norm === 'match') {
    color = 'var(--color-clean)';
    bg = 'var(--color-clean-bg)';
  } else if (norm === 'info' || norm === 'informational') {
    color = 'var(--color-info)';
    bg = 'var(--color-info-bg)';
  }

  // The tint and the word carry the verdict between them. The dot that used to
  // sit in front of the label said it a second time, and a decorative status
  // dot before a label is a template tell in its own right.
  return (
    <span className={`ui-verdict ui-verdict--${size}`} style={{ color, backgroundColor: bg }}>
      {text}
    </span>
  );
};

export const ScoreRing: React.FC<{ score: number; max?: number; size?: number; label?: string }> = ({
  score,
  max = 100,
  size = 80,
  label
}) => {
  const ratio = Math.max(0, Math.min(1, score / max));
  const pct = Math.round(ratio * 100);
  const strokeWidth = size >= 100 ? 8 : 6;
  const radius = (size - strokeWidth * 2) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - ratio * circumference;

  let strokeColor = 'var(--color-clean)';
  if (pct >= 70) strokeColor = 'var(--color-malicious)';
  else if (pct >= 20) strokeColor = 'var(--color-suspicious)';

return (
    <div className="relative inline-flex items-center justify-center shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90" aria-hidden="true">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="transparent"
          stroke="var(--color-rule-2)"
          strokeWidth={strokeWidth}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="transparent"
          stroke={strokeColor}
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          style={{ transition: 'stroke-dashoffset var(--dur-long) var(--ease-out)' }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
        <span className="sc-mono font-medium text-sm leading-none" style={{ color: strokeColor }}>
          {score}
          <span className="text-xs opacity-70">/{max}</span>
        </span>
        {label && (
          <span className="ui-label mt-0.5" style={{ color: 'var(--color-muted)' }}>
            {label}
          </span>
        )}
      </div>
    </div>
  );
};

export const Sparkline: React.FC<{ values: number[]; color?: string }> = ({ values, color = 'var(--accent-from)' }) => {
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const range = Math.max(max - min, 1);
  const width = 104;
  const height = 30;
  const coords = values.map((v, idx) => {
    const x = (idx / Math.max(values.length - 1, 1)) * (width - 8) + 4;
    const y = height - 4 - ((v - min) / range) * (height - 8);
    return { x, y };
  });
  const pts = coords.map((c) => `${c.x.toFixed(1)},${c.y.toFixed(1)}`).join(' ');
  const areaPts = `4,${height - 2} ${pts} ${width - 4},${height - 2}`;
  const last = coords[coords.length - 1] || { x: width - 4, y: height / 2 };

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className="overflow-visible" aria-hidden="true">
      <polygon fill={color} fillOpacity="0.16" points={areaPts} />
<polyline fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" points={pts} />
      <circle cx={last.x} cy={last.y} r="2.5" fill={color} />
    </svg>
  );
};

export const CopyKV: React.FC<{
  label: string;
  value: string;
  mono?: boolean;
  onCopy?: (val: string) => void;
  onPivot?: (val: string) => void;
  pivotLabel?: string;
}> = ({ label, value, mono = true, onCopy, onPivot, pivotLabel }) => (
  <div className="ui-kv">
    <span className="ui-label shrink-0">{label}</span>
    <div className="flex items-center gap-2 min-w-0">
      <span className={`${mono ? 'sc-mono' : ''} truncate select-all`} title={value}>
        {value}
      </span>
      {onCopy && (
        <button
          type="button"
          onClick={() => onCopy(value)}
          className="ui-btn ui-btn--ghost ui-btn--sm shrink-0"
          title="Copy value"
        >
          Copy
        </button>
      )}
      {onPivot && (
        <button
          type="button"
          onClick={() => onPivot(value)}
          className="ui-btn ui-btn--primary ui-btn--sm shrink-0"
        >
          {pivotLabel || 'Pivot'}
        </button>
      )}
    </div>
  </div>
);

export const Modal: React.FC<{
  open: boolean;
  title: string;
  subtitle?: string;
  onClose: () => void;
  maxWidth?: string;
  children: React.ReactNode;
}> = ({ open, title, subtitle, onClose, maxWidth = 'max-w-xl', children }) => {
  if (!open) return null;
  return (
    <div
      className="sc-modal-scrim"
      role="dialog"
      aria-modal="true"
      aria-label={title}
      onClick={onClose}
    >
      <div className={`sc-modal ${maxWidth}`} onClick={(e) => e.stopPropagation()}>
        <div className="sc-modal-head">
          <div>
            <h3 className="sc-modal-title">{title}</h3>
            {subtitle && <p className="sc-modal-sub">{subtitle}</p>}
          </div>
          <button type="button" onClick={onClose} className="sc-icon-btn" aria-label="Close dialog">
            <ShellIcon name="close" size={16} />
          </button>
        </div>
        <div className="sc-modal-body">{children}</div>
      </div>
    </div>
  );
};

export const ToolOverviewTemplate: React.FC<{
  tool: ToolDefinition;
  stats: { label: string; value: string }[];
  doesList: string[];
  doesNotList: string[];
  terminalTitle: string;
  terminalOutput: string;
  ctaLabel: string;
  onStart: () => void;
}> = ({ tool, stats, doesList, doesNotList, terminalTitle, terminalOutput, ctaLabel, onStart }) => (
  <div className="space-y-6 max-w-6xl mx-auto">
    <div className="ui-card ui-card-pad" data-tool={tool.id}>
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
        <div className="space-y-2 max-w-2xl">
          <span className="ui-badge">
            <ToolIcon tool={tool.id} size={14} />
            <span>{tool.name}</span>
          </span>
          <h1 className="ui-h1">{tool.tagline}</h1>
          <p className="ui-body">{tool.description}</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <button type="button" onClick={onStart} className="ui-btn ui-btn--primary">
            {ctaLabel}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-6">
        {stats.map((st, i) => (
          <div key={i} className="ui-well p-3">
            <div className="ui-label">{st.label}</div>
            <div className="ui-stat-value mt-1">{st.value}</div>
          </div>
        ))}
      </div>
    </div>

    <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
      <div className="ui-card ui-card-pad space-y-3">
        <h2 className="ui-h3">What {tool.shortName} does</h2>
        <ul className="space-y-2">
          {doesList.map((item, idx) => (
            <li key={idx} className="ui-body flex items-start gap-2">
              <span className="ui-dot mt-2" style={{ backgroundColor: 'var(--color-clean)' }} />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="ui-card ui-card-pad space-y-3">
        <h2 className="ui-h3">What it does not do</h2>
        <ul className="space-y-2">
          {doesNotList.map((item, idx) => (
            <li key={idx} className="ui-body flex items-start gap-2">
              <span className="ui-dot mt-2" style={{ backgroundColor: 'var(--color-suspicious)' }} />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>

    <div className="ui-card ui-card--flush">
      <div className="ui-card-head">
        <span className="ui-label">{terminalTitle}</span>
        <span className="ui-label">Read-only sample telemetry</span>
      </div>
      <pre
        className="p-4 sc-mono text-xs overflow-x-auto leading-relaxed"
        style={{ backgroundColor: 'var(--color-graphite)', color: 'var(--color-graphite-ink)' }}
      >
        {terminalOutput}
      </pre>
    </div>
  </div>
);
