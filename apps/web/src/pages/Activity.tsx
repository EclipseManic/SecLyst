import React from 'react';
import { TOOLS_REGISTRY } from '../data/workspace';
import type { ActivityItem } from '../data/workspace';
import { ToolIcon } from '../lib/icons';

export function ActivityPage({ items }: { items: ActivityItem[] }) {
  return <div className="sc-page"><header className="sc-page-head"><div className="sc-page-head-main"><div className="sc-crumbs">SecLyst / Activity</div><h1 className="sc-page-title">Your analysis timeline.</h1><p className="sc-page-desc">Recent work reported by every specialist engine in one durable view.</p></div></header><section className="ui-card ui-card--flush">{items.length ? <div className="cc-timeline-list">{items.map((item)=><div className="cc-timeline-row" key={item.id}><span className="cc-timeline-tool" data-tool={item.tool}><ToolIcon tool={item.tool} size={14}/>{TOOLS_REGISTRY[item.tool].shortName}</span><span className="cc-timeline-body"><span className="ui-strong">{item.actionType}</span><span className="ui-body">{item.description}</span></span><span className="ui-meta">{item.timestamp}</span></div>)}</div>:<div className="ui-empty"><span className="ui-h3">No activity yet</span><span className="ui-body">Start work in Dashboard or a specialist tool.</span></div>}</section></div>;
}
