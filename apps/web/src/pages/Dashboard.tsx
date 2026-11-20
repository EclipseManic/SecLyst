import React, { useEffect, useState } from 'react';
import { TOOLS_REGISTRY } from '../data/workspace';
import type { ToolDefinition, ToolId } from '../data/workspace';
import { ToolIcon } from '../lib/icons';

const ANALYSIS_TOOLS: ToolId[] = ['ioc', 'malware', 'phishing', 'events'];

export function Dashboard({
  backendStatus,
  activityCount,
  onOpenTool,
  onQuickIoc
}: {
  backendStatus: Record<ToolId, 'online' | 'offline' | 'unknown'>;
  activityCount: number;
  onOpenTool: (tool: ToolId) => void;
  onQuickIoc: (value: string) => void;
}) {
  const [objective, setObjective] = useState('');
  const [selectedTool, setSelectedTool] = useState<ToolId>('ioc');
  const [files, setFiles] = useState<File[]>([]);
  const [jobs, setJobs] = useState<any[]>([]);
  useEffect(() => { fetch('/api/v1/jobs?limit=100').then((response) => response.ok ? response.json() : []).then(setJobs).catch(() => setJobs([])); }, []);
  const online = Object.values(backendStatus).filter((status) => status === 'online').length;
  const running = jobs.filter((job) => ['queued', 'running', 'waiting_provider', 'waiting_rate_limit'].includes(job.status)).length;
  const greeting = new Date().getHours() < 12 ? 'Good morning' : new Date().getHours() < 18 ? 'Good afternoon' : 'Good evening';

  const start = () => {
    if (selectedTool === 'ioc' && files.length === 0 && objective.trim()) onQuickIoc(objective.trim());
    else onOpenTool(selectedTool);
  };

  return <div className="premium-dashboard">
    <header className="premium-dashboard-head">
      <div><span className="premium-dashboard-kicker">{greeting}, analyst</span><h1>Investigate with context. Act with confidence.</h1><p>One secure workspace for triage, enrichment, forensics, event hunting, and detection engineering.</p></div>
      <div className="premium-live"><i/><span>{online} of 5 engines online</span></div>
    </header>

    <section className="premium-snapshot"><div><span>Engine availability</span><strong>{online}/5</strong><small>Measured live</small></div><div><span>Active work</span><strong>{running}</strong><small>Durable platform jobs</small></div><div><span>Recent records</span><strong>{activityCount}</strong><small>Across specialist engines</small></div><div><span>Workspace mode</span><strong>Local</strong><small>Loopback isolated</small></div></section>

    <section className="premium-section"><div className="premium-section-head"><div><span className="premium-section-label">Specialist suite</span><h2>Five focused tools. One consistent workspace.</h2></div></div><div className="premium-suite">{(Object.values(TOOLS_REGISTRY) as ToolDefinition[]).map((tool)=><button key={tool.id} type="button" data-tool={tool.id} onClick={()=>onOpenTool(tool.id)}><span className="premium-suite-icon"><ToolIcon tool={tool.id} size={20}/></span><span><strong>{tool.name}</strong><small>{tool.description}</small></span><b>Open</b></button>)}</div></section>

    <section className="premium-guide"><div><span>01</span><h3>State the objective</h3><p>Start with the decision you need to make, not a blank tool screen.</p></div><div><span>02</span><h3>Choose the evidence</h3><p>Keep files and folders local while routing work to the right specialist.</p></div><div><span>03</span><h3>Follow durable activity</h3><p>Switch tools freely and return to work without losing browser-side context.</p></div></section>

    <section className="premium-ruleforge"><div><span className="premium-section-label">Detection engineering</span><h2>Already have a rule or detection idea?</h2><p>Use RuleForge to import, translate, validate, tune, and explain detection logic across supported SIEM dialects.</p></div><button type="button" onClick={()=>onOpenTool('ruleforge')}>Open RuleForge</button></section>

    <section className="premium-console" aria-labelledby="premium-console-title">
      <div className="premium-console-copy"><span className="premium-section-label">Start here</span><h2 id="premium-console-title">What do you want to analyze?</h2><p>Describe the outcome you need, attach the evidence, then choose the right specialist.</p></div>
      <textarea className="premium-objective" value={objective} onChange={(event)=>setObjective(event.target.value)} placeholder="Example: Verify whether this email is malicious, inspect its attachments, and enrich every extracted indicator." rows={4}/>
      <div className="premium-evidence-grid"><label><strong>Add files</strong><span>Samples, emails, documents, or EVTX logs</span><input type="file" multiple onChange={(event)=>setFiles(Array.from(event.target.files||[]))}/></label><label><strong>Add a folder</strong><span>A related collection of local evidence</span><input type="file" multiple {...({webkitdirectory:''} as React.InputHTMLAttributes<HTMLInputElement>)} onChange={(event)=>setFiles(Array.from(event.target.files||[]))}/></label></div>
      {files.length > 0 && <div className="premium-file-count">{files.length} local item{files.length===1?'':'s'} selected</div>}
      <div className="premium-tool-selector">{ANALYSIS_TOOLS.map((id)=>{const tool=TOOLS_REGISTRY[id];return <button key={id} type="button" data-tool={id} aria-pressed={selectedTool===id} onClick={()=>setSelectedTool(id)}><ToolIcon tool={id} size={18}/><span><strong>{tool.shortName}</strong><small>{tool.tagline}</small></span></button>;})}</div>
      <div className="premium-console-footer"><button className="premium-primary" type="button" disabled={!objective.trim()} onClick={start}>Open {TOOLS_REGISTRY[selectedTool].shortName}</button><span>Evidence stays on this machine and opens in the original specialist workflow.</span></div>
    </section>
  </div>;
}
