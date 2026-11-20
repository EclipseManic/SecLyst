import React from 'react';
import { TOOLS_REGISTRY } from '../data/workspace';
import type { ActivityItem } from '../data/workspace';
import { ToolIcon } from '../lib/icons';

export function ActivityPage({ items }: { items: ActivityItem[] }) {
  return (
    <div className="sc-page premium-activity">
      <header className="sc-page-head">
        <div className="sc-page-head-main">
          <div className="sc-crumbs">SecLyst / Activity</div>
          <h1 className="sc-page-title">Your analysis timeline.</h1>
          <p className="sc-page-desc">A readable history of work reported by every specialist engine.</p>
        </div>
      </header>
      <section className="ui-card ui-card--flush">
        <div className="ui-card-head"><div><div className="ui-card-title">Recent activity</div><div className="ui-card-sub">Newest records first</div></div><span className="ui-badge">{items.length}</span></div>
        {items.length ? <div className="activity-list">{items.map((item) => (
          <article className="activity-row" key={item.id}>
            <div className="activity-tool" data-tool={item.tool}><ToolIcon tool={item.tool} size={15}/><span>{TOOLS_REGISTRY[item.tool].shortName}</span></div>
            <div className="activity-copy"><strong>{item.actionType}</strong><span>{item.description}</span></div>
            <time className="activity-time">{item.timestamp}</time>
          </article>
        ))}</div> : <div className="ui-empty"><span className="ui-h3">No activity yet</span><span className="ui-body">Start work in Dashboard or a specialist tool.</span></div>}
      </section>
    </div>
  );
}
