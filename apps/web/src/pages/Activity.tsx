import React, { useEffect, useState } from 'react';
import { TOOLS_REGISTRY } from '../data/workspace';
import type { ActivityItem } from '../data/workspace';
import { ToolIcon } from '../lib/icons';

/* The activity page is a list of work, so every row is a control: pressing it
   opens the engine and the stored-results view it came from. Each engine keeps
   its own hue on the row, so the timeline is scannable by tool rather than a
   column of identical dark bars. Clearing hides the records shown now and
   remembers them, so the next summary poll cannot put them back. */
export function ActivityPage({
  items,
  onOpenItem,
  onClear
}: {
  items: ActivityItem[];
  onOpenItem: (item: ActivityItem) => void;
  onClear: () => void;
}) {
  const [confirmClear, setConfirmClear] = useState(false);

  // A confirm that nobody follows through on should not stay armed forever.
  useEffect(() => {
    if (!confirmClear) return;
    const timer = window.setTimeout(() => setConfirmClear(false), 4000);
    return () => window.clearTimeout(timer);
  }, [confirmClear]);

  const clear = () => {
    if (!confirmClear) {
      setConfirmClear(true);
      return;
    }
    setConfirmClear(false);
    onClear();
  };

  return (
    <div className="sc-page premium-activity">
      <header className="sc-page-head">
        <div className="sc-page-head-main">
          <div className="sc-crumbs">SecLyst / Activity</div>
          <h1 className="sc-page-title">Your analysis timeline.</h1>
          <p className="sc-page-desc">
            Every run reported by a specialist engine. Press a row to open the result it came from.
          </p>
        </div>
        <div className="sc-page-head-actions">
          <button
            type="button"
            className="ui-btn ui-btn--ghost ui-btn--sm"
            data-confirm={confirmClear ? 'true' : undefined}
            disabled={items.length === 0}
            onClick={clear}
            onBlur={() => setConfirmClear(false)}
            title={confirmClear ? 'Press again to clear every row' : 'Clear every row shown here'}
          >
            {confirmClear ? 'Confirm clear' : 'Clear activity'}
          </button>
        </div>
      </header>

      <section className="ui-card ui-card--flush">
        <div className="ui-card-head">
          <div>
            <div className="ui-card-title">Recent activity</div>
            <div className="ui-card-sub">
              {confirmClear ? 'Press confirm to hide everything listed below.' : 'Newest records first'}
            </div>
          </div>
          <span className="ui-badge">{items.length}</span>
        </div>

        {items.length ? (
          <div className="activity-list">
            {items.map((item) => {
              const definition = TOOLS_REGISTRY[item.tool];
              return (
                <button
                  type="button"
                  className="activity-row"
                  data-tool={item.tool}
                  key={item.id}
                  onClick={() => onOpenItem(item)}
                  aria-label={`Open ${definition.name}: ${item.actionType} — ${item.description}`}
                >
                  <span className="activity-tool">
                    <span className="activity-mark" aria-hidden="true">
                      <ToolIcon tool={item.tool} size={15} />
                    </span>
                    <span className="activity-tool-name">{definition.shortName}</span>
                  </span>

                  <span className="activity-copy">
                    <strong>{item.actionType}</strong>
                    <span>{item.description}</span>
                  </span>

                  <span className="activity-end">
                    <time className="activity-time">{item.timestamp}</time>
                    <span className="activity-open" aria-hidden="true">
                      Open
                      <span className="activity-arrow">→</span>
                    </span>
                  </span>
                </button>
              );
            })}
          </div>
        ) : (
          <div className="ui-empty">
            <span className="ui-h3">Nothing here right now</span>
            <span className="ui-body">
              Cleared records stay hidden. New work from any engine appears here as it finishes.
            </span>
          </div>
        )}
      </section>
    </div>
  );
}