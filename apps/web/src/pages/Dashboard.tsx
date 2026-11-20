import React, { useEffect, useState } from 'react';
import { TOOLS_REGISTRY } from '../data/workspace';
import type { ActivityItem, ToolDefinition, ToolId } from '../data/workspace';
import { ToolIcon } from '../lib/icons';

const ANALYSIS_TOOLS: ToolId[] = ['ioc', 'malware', 'phishing', 'events'];

export function Dashboard({ backendStatus, activity, onOpenTool, onQuickIoc }: {
  backendStatus: Record<ToolId, 'online' | 'offline' | 'unknown'>;
  activity: ActivityItem[];
  onOpenTool: (tool: ToolId) => void;
  onQuickIoc: (value: string) => void;
}) {
  const [objective, setObjective] = useState('');
  const [selectedTool, setSelectedTool] = useState<ToolId>('ioc');
  const [files, setFiles] = useState<File[]>([]);
  const [jobs, setJobs] = useState<any[]>([]);
  useEffect(() => { fetch('/api/v1/jobs?limit=50').then((response) => response.ok ? response.json() : []).then(setJobs).catch(() => setJobs([])); }, []);
  const tools = Object.values(TOOLS_REGISTRY) as ToolDefinition[];
  const online = Object.values(backendStatus).filter((status) => status === 'online').length;
  const activeJobs = jobs.filter((job) => ['queued', 'running', 'waiting_provider', 'waiting_rate_limit'].includes(job.status));
  const start = () => selectedTool === 'ioc' && files.length === 0 ? onQuickIoc(objective.trim()) : onOpenTool(selectedTool);

  return <div className="ops-dashboard">
    <header className="ops-head">
      <div><span className="ops-eyebrow">Workspace overview</span><h1>Security operations, without the tool switching tax.</h1><p>Monitor current work, resume recent investigations, and move into the right specialist with context intact.</p></div>
      <div className="ops-health"><span data-state={online === 5 ? 'healthy' : 'degraded'} /><div><strong>{online === 5 ? 'All systems operational' : `${online} of 5 engines available`}</strong><small>Local SecLyst runtime</small></div></div>
    </header>

    <section className="ops-grid" aria-label="Workspace status">
      <article className="ops-card ops-card--posture"><div className="ops-card-head"><div><span className="ops-label">System posture</span><h2>{online}/5 engines ready</h2></div><span className="ops-state">Live</span></div><div className="ops-engine-list">{tools.map((tool)=><button key={tool.id} onClick={()=>onOpenTool(tool.id)}><ToolIcon tool={tool.id} size={17}/><span>{tool.shortName}</span><i data-state={backendStatus[tool.id]}/></button>)}</div></article>
      <article className="ops-card"><div className="ops-card-head"><div><span className="ops-label">Active queue</span><h2>{activeJobs.length} in progress</h2></div></div>{activeJobs.length?<div className="ops-mini-list">{activeJobs.slice(0,4).map((job)=><div key={job.id}><span>{job.tool} · {job.operation}</span><b>{job.progress}%</b><progress max="100" value={job.progress}/></div>)}</div>:<div className="ops-empty"><strong>Queue is clear</strong><span>New background work will appear here.</span></div>}</article>
      <article className="ops-card ops-card--recent"><div className="ops-card-head"><div><span className="ops-label">Recent work</span><h2>{activity.length} stored records</h2></div></div>{activity.length?<div className="ops-recent-list">{activity.slice(0,5).map((item)=><button key={item.id} onClick={()=>onOpenTool(item.tool)}><ToolIcon tool={item.tool} size={15}/><span><strong>{item.actionType}</strong><small>{item.description}</small></span><time>{item.timestamp}</time></button>)}</div>:<div className="ops-empty"><strong>No recent work</strong><span>Completed tool activity will collect here.</span></div>}</article>
    </section>

    <section className="ops-section"><div className="ops-section-head"><div><span className="ops-eyebrow">Specialist workspaces</span><h2>Choose the depth you need.</h2></div><p>Every tool keeps its original workflow while SecLyst preserves navigation, background activity, shared providers, and secure local access.</p></div><div className="ops-tool-grid">{tools.map((tool)=><button key={tool.id} data-tool={tool.id} onClick={()=>onOpenTool(tool.id)}><span className="ops-tool-icon"><ToolIcon tool={tool.id} size={20}/></span><span><strong>{tool.name}</strong><small>{tool.tagline}</small></span><b>Open workspace</b></button>)}</div></section>

    <section className="ops-section"><div className="ops-section-head"><div><span className="ops-eyebrow">Common pathways</span><h2>Move from evidence to an answer.</h2></div></div><div className="ops-pathways"><button onClick={()=>{setSelectedTool('phishing');document.getElementById('ops-intake')?.scrollIntoView({behavior:'smooth'});}}><span>01</span><strong>Suspicious email</strong><small>Authenticate sender, inspect URLs and attachments, extract IOCs.</small></button><button onClick={()=>{setSelectedTool('malware');document.getElementById('ops-intake')?.scrollIntoView({behavior:'smooth'});}}><span>02</span><strong>Unknown file</strong><small>Run static analysis, YARA, threat intelligence, and artifact extraction.</small></button><button onClick={()=>{setSelectedTool('events');document.getElementById('ops-intake')?.scrollIntoView({behavior:'smooth'});}}><span>03</span><strong>Windows evidence</strong><small>Ingest EVTX, search activity, extract indicators, and hunt with Sigma.</small></button></div></section>

    <section className="ops-ruleforge"><div><span className="ops-eyebrow">Detection engineering</span><h2>Turn confirmed behavior into portable logic.</h2><p>Import, translate, validate, tune, and explain rules across RuleForge’s supported SIEM dialects.</p></div><button onClick={()=>onOpenTool('ruleforge')}>Open RuleForge</button></section>

    <section className="ops-intake" id="ops-intake"><div className="ops-intake-head"><span className="ops-eyebrow">Start a new analysis</span><h2>What do you want to understand?</h2><p>State the decision you need to make, add local evidence, and select the specialist that should lead.</p></div><textarea value={objective} onChange={(event)=>setObjective(event.target.value)} rows={4} placeholder="Example: Determine whether this email is malicious, inspect every attachment, and enrich the extracted indicators."/><div className="ops-evidence"><label><strong>Select files</strong><span>Samples, emails, documents, or EVTX logs</span><input type="file" multiple onChange={(event)=>setFiles(Array.from(event.target.files||[]))}/></label><label><strong>Select a folder</strong><span>A related collection of evidence</span><input type="file" multiple {...({webkitdirectory:''} as React.InputHTMLAttributes<HTMLInputElement>)} onChange={(event)=>setFiles(Array.from(event.target.files||[]))}/></label></div>{files.length>0&&<p className="ops-file-count">{files.length} local item{files.length===1?'':'s'} selected</p>}<div className="ops-tool-select">{ANALYSIS_TOOLS.map((id)=>{const tool=TOOLS_REGISTRY[id];return <button key={id} aria-pressed={selectedTool===id} onClick={()=>setSelectedTool(id)}><ToolIcon tool={id} size={17}/><span><strong>{tool.shortName}</strong><small>{tool.tagline}</small></span></button>;})}</div><div className="ops-intake-foot"><button disabled={!objective.trim()} onClick={start}>Open {TOOLS_REGISTRY[selectedTool].shortName}</button><span>Evidence stays local and opens in the original specialist workflow.</span></div></section>
  </div>;
}
