import React, { useEffect, useState } from 'react';
import { TOOLS_REGISTRY } from '../data/workspace';
import type { ActivityItem, ToolDefinition, ToolId } from '../data/workspace';
import { ToolIcon } from '../lib/icons';

const ANALYSIS_TOOLS: ToolId[] = ['ioc', 'malware', 'phishing', 'events'];

export function Dashboard({ backendStatus, activity, onOpenTool, onQuickIoc, onOpenActivity }: {
  backendStatus: Record<ToolId, 'online' | 'offline' | 'unknown'>;
  activity: ActivityItem[];
  onOpenTool: (tool: ToolId) => void;
  onQuickIoc: (value: string) => void;
  onOpenActivity: () => void;
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
    <section className="ops-tool-hero">
      <div className="ops-tool-hero-copy"><span className="ops-hero-pill"><i/>Unified security operations platform</span><h1>Analyze. Correlate. <em>Defend.</em></h1><p>Bring five specialist security tools into one local workspace without losing their original workflows, live progress, or investigative context.</p><div className="ops-hero-actions"><button onClick={()=>document.getElementById('ops-intake')?.scrollIntoView({behavior:'smooth'})}>Start an analysis</button><button onClick={onOpenActivity}>View activity</button></div><div className="ops-hero-signals"><span><i/>Local-first</span><span><i/>Shared provider controls</span><span><i/>Durable background jobs</span></div></div>
      <div className="ops-terminal"><header><span className="ops-window-dots"><i/><i/><i/></span><b>seclyst_workspace.json</b><small data-state={online===5?'healthy':'degraded'}>{online===5?'LIVE':'DEGRADED'}</small></header><div className="ops-terminal-body"><p><span>"workspace"</span>: <b>"SecLyst"</b>,</p><p><span>"engines_online"</span>: <strong>{online}</strong> / 5,</p><p><span>"active_jobs"</span>: <strong>{activeJobs.length}</strong>,</p><p><span>"recent_records"</span>: <strong>{activity.length}</strong>,</p><p><span>"latest_activity"</span>: <b>"{activity[0]?.actionType || 'waiting for analysis'}"</b>,</p><p><span>"data_boundary"</span>: <b>"loopback isolated"</b></p><i className="ops-terminal-cursor"/></div><footer><span>✓ tools supervised</span><span>✓ credentials brokered</span><span>✓ sessions retained</span></footer></div>
    </section>

    <section className="ops-metric-strip" aria-label="Workspace status"><div><strong>5</strong><span>Specialist tools</span></div><div><strong>{online}/5</strong><span>Engines online</span></div><div><strong>{activeJobs.length}</strong><span>Active jobs</span></div><div><strong>{activity.length}</strong><span>Recent records</span></div><div><strong>LOCAL</strong><span>Data boundary</span></div></section>

    <section className="ops-section"><div className="ops-section-head"><div><span className="ops-eyebrow">Specialist workspaces</span><h2>Choose the depth you need.</h2></div><p>Every tool keeps its original workflow while SecLyst preserves navigation, background activity, shared providers, and secure local access.</p></div><div className="ops-tool-grid">{tools.map((tool)=><button key={tool.id} data-tool={tool.id} onClick={()=>onOpenTool(tool.id)}><span className="ops-tool-icon"><ToolIcon tool={tool.id} size={20}/></span><span><strong>{tool.name}</strong><small>{tool.tagline}</small></span><b>Open workspace</b></button>)}</div></section>

    <section className="ops-section"><div className="ops-section-head"><div><span className="ops-eyebrow">Common pathways</span><h2>Move from evidence to an answer.</h2></div></div><div className="ops-pathways"><button onClick={()=>{setSelectedTool('phishing');document.getElementById('ops-intake')?.scrollIntoView({behavior:'smooth'});}}><span>01</span><strong>Suspicious email</strong><small>Authenticate sender, inspect URLs and attachments, extract IOCs.</small></button><button onClick={()=>{setSelectedTool('malware');document.getElementById('ops-intake')?.scrollIntoView({behavior:'smooth'});}}><span>02</span><strong>Unknown file</strong><small>Run static analysis, YARA, threat intelligence, and artifact extraction.</small></button><button onClick={()=>{setSelectedTool('events');document.getElementById('ops-intake')?.scrollIntoView({behavior:'smooth'});}}><span>03</span><strong>Windows evidence</strong><small>Ingest EVTX, search activity, extract indicators, and hunt with Sigma.</small></button></div></section>

    <section className="ops-ruleforge"><div><span className="ops-eyebrow">Detection engineering</span><h2>Turn confirmed behavior into portable logic.</h2><p>Import, translate, validate, tune, and explain rules across RuleForge’s supported SIEM dialects.</p></div><button onClick={()=>onOpenTool('ruleforge')}>Open RuleForge</button></section>

    <section className="ops-intake" id="ops-intake"><div className="ops-intake-head"><span className="ops-eyebrow">Start a new analysis</span><h2>What do you want to understand?</h2><p>State the decision you need to make, add local evidence, and select the specialist that should lead.</p></div><textarea value={objective} onChange={(event)=>setObjective(event.target.value)} rows={4} placeholder="Example: Determine whether this email is malicious, inspect every attachment, and enrich the extracted indicators."/><div className="ops-evidence"><label><strong>Select files</strong><span>Samples, emails, documents, or EVTX logs</span><input type="file" multiple onChange={(event)=>setFiles(Array.from(event.target.files||[]))}/></label><label><strong>Select a folder</strong><span>A related collection of evidence</span><input type="file" multiple {...({webkitdirectory:''} as React.InputHTMLAttributes<HTMLInputElement>)} onChange={(event)=>setFiles(Array.from(event.target.files||[]))}/></label></div>{files.length>0&&<p className="ops-file-count">{files.length} local item{files.length===1?'':'s'} selected</p>}<div className="ops-tool-select">{ANALYSIS_TOOLS.map((id)=>{const tool=TOOLS_REGISTRY[id];return <button key={id} aria-pressed={selectedTool===id} onClick={()=>setSelectedTool(id)}><ToolIcon tool={id} size={17}/><span><strong>{tool.shortName}</strong><small>{tool.tagline}</small></span></button>;})}</div><div className="ops-intake-foot"><button disabled={!objective.trim()} onClick={start}>Open {TOOLS_REGISTRY[selectedTool].shortName}</button><span>Evidence stays local and opens in the original specialist workflow.</span></div></section>
  </div>;
}
