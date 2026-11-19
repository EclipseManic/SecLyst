import React, { useEffect, useState } from 'react';

interface Job { id: string; tool: string; operation: string; status: string; progress: number; stage: string; created_at: string; }

export function RunsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  useEffect(() => {
    const load = () => fetch('/api/v1/jobs?limit=100').then((response) => response.ok ? response.json() : []).then(setJobs).catch(() => setJobs([]));
    void load();
    const timer = window.setInterval(load, 3000);
    return () => window.clearInterval(timer);
  }, []);
  return <div className="sc-page">
    <header className="sc-page-head"><div className="sc-page-head-main"><div className="sc-crumbs">SecLyst <span className="sc-crumbs-sep">/</span> Runs</div><h1 className="sc-page-title">Analysis runs</h1><p className="sc-page-desc">Durable work across every specialist engine, including progress, waits, partial results and recovery state.</p></div></header>
    <section className="ui-card ui-card--flush">
      {jobs.length === 0 ? <div className="ui-empty"><span className="ui-h3">No runs yet</span><span className="ui-body">Start from the Workbench or any original tool.</span></div> :
        <div className="cc-timeline-list">{jobs.map((job) => <div className="cc-timeline-row" key={job.id}><span className="cc-timeline-tool" data-tool={job.tool}>{job.tool}</span><span className="cc-timeline-body"><span className="ui-strong">{job.operation}</span><span className="ui-body">{job.stage} · {job.progress}%</span></span><span className="ui-badge">{job.status}</span></div>)}</div>}
    </section>
  </div>;
}
