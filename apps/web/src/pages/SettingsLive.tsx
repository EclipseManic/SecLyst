// ==========================================================================
// Seclyst shell settings
// ==========================================================================
import React from 'react';
import { useEffect, useState } from 'react';
import { TOOLS_REGISTRY } from '../data/workspace';
import type { ToastMessage, ToolDefinition, ToolId } from '../data/workspace';
import { downloadFileBlob } from '../lib/api-client';
import { Kbd, VerdictBadge } from '../ui/index';

const TRANSPORT: Record<ToolId, string> = {
  malware: 'WebSocket and REST',
  ioc: 'Server-sent events and REST',
  events: 'REST',
  phishing: 'REST',
  ruleforge: 'REST'
};

type Category = 'appearance' | 'apis' | 'tools' | 'backends' | 'security' | 'data' | 'shortcuts' | 'about';

export const SettingsPage: React.FC<{
  theme: 'dark' | 'light' | 'system';
  setTheme: (theme: 'dark' | 'light' | 'system') => void;
  fontScale: number;
  setFontScale: (scale: number) => void;
  compactMode: boolean;
  setCompactMode: (compact: boolean) => void;
  reduceMotion: boolean;
  setReduceMotion: (reduce: boolean) => void;
  backendStatus: Record<ToolId, 'online' | 'offline' | 'unknown'>;
  toolEndpoints: Record<ToolId, string>;
  onTestBackend: (tool: ToolId) => void;
  onUnloadToolSessions: () => void;
  onAddToast: (toast: Omit<ToastMessage, 'id'>) => void;
}> = ({
  theme,
  setTheme,
  fontScale,
  setFontScale,
  compactMode,
  setCompactMode,
  reduceMotion,
  setReduceMotion,
  backendStatus,
  toolEndpoints,
  onTestBackend,
  onUnloadToolSessions,
  onAddToast
}) => {
  const [category, setCategory] = useState<Category>('appearance');
  const [centralSettings, setCentralSettings] = useState<any>({ providers: {}, tools: {} });
  const [providerSecrets, setProviderSecrets] = useState<Record<string, string>>({});
  const [selectedTool, setSelectedTool] = useState<ToolId>('malware');
  const [toolConfigText, setToolConfigText] = useState('{}');
  const tools = Object.values(TOOLS_REGISTRY) as ToolDefinition[];
  const reloadSettings = () => fetch('/api/v1/settings').then((response) => response.json()).then(setCentralSettings).catch(() => undefined);
  useEffect(() => { void reloadSettings(); }, []);
  useEffect(() => { setToolConfigText(JSON.stringify(centralSettings.tools?.[selectedTool] || {}, null, 2)); }, [centralSettings, selectedTool]);

  const clearShellData = () => {
    try {
      for (let index = window.localStorage.length - 1; index >= 0; index -= 1) {
        const key = window.localStorage.key(index);
        if (key?.startsWith('seclyst.')) window.localStorage.removeItem(key);
      }
      for (let index = window.sessionStorage.length - 1; index >= 0; index -= 1) {
        const key = window.sessionStorage.key(index);
        if (key?.startsWith('seclyst.')) window.sessionStorage.removeItem(key);
      }
      onAddToast({ type: 'success', title: 'Shell data cleared', description: 'Only Seclyst browser preferences were removed.' });
    } catch {
      onAddToast({ type: 'error', title: 'Unable to clear shell data', description: 'Browser storage is unavailable.' });
    }
  };

  return (
    <div className="sc-page">
      <header className="sc-page-head">
        <div className="sc-page-head-main">
          <div className="sc-crumbs">Workspace <span className="sc-crumbs-sep">/</span> Settings</div>
          <h1 className="sc-page-title">Settings</h1>
          <p className="sc-page-desc">
            Shell appearance, live engine connections, and local security boundaries. Each tool
            keeps its own operational settings inside its original interface.
          </p>
        </div>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
        <nav className="md:col-span-3 ui-card ui-card-pad h-fit space-y-1" aria-label="Settings sections">
          {([
            ['appearance', 'Appearance'],
            ['apis', 'Shared APIs'],
            ['tools', 'Tool configuration'],
            ['backends', 'Backend connections'],
            ['security', 'Security'],
            ['data', 'Shell data'],
            ['shortcuts', 'Keyboard shortcuts'],
            ['about', 'About']
          ] as [Category, string][]).map(([id, label]) => (
            <button key={id} type="button" className="sc-nav-item" aria-current={category === id ? 'page' : undefined} onClick={() => setCategory(id)}>
              <span className="sc-nav-label">{label}</span>
            </button>
          ))}
        </nav>

        <div className="md:col-span-9 ui-card ui-card-pad space-y-5">
          {category === 'appearance' && (
            <div className="space-y-5">
              <h2 className="ui-h2">Appearance</h2>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {(['dark', 'light', 'system'] as const).map((value) => (
                  <button key={value} type="button" className="ui-choice" aria-pressed={theme === value} onClick={() => setTheme(value)}>
                    <span className="ui-h3">{value === 'system' ? 'System' : value === 'dark' ? 'Dark' : 'Light'}</span>
                    <span className="ui-meta mt-1 block">{value === 'system' ? 'Follow the operating system' : `${value} shell surfaces`}</span>
                  </button>
                ))}
              </div>
              <div className="space-y-2">
                <span className="ui-meta block">Shell font size</span>
                <div className="ui-tabs">
                  {[90, 100, 110, 120].map((scale) => (
                    <button key={scale} type="button" className="ui-tab" aria-selected={fontScale === scale} onClick={() => setFontScale(scale)}>{scale}%</button>
                  ))}
                </div>
              </div>
              <div className="space-y-3">
                <label className="flex items-start gap-2.5 cursor-pointer">
                  <input type="checkbox" checked={compactMode} onChange={(event) => setCompactMode(event.target.checked)} />
                  <span><span className="ui-strong block">Compact shell density</span><span className="ui-meta">Tighten navigation and workspace spacing without changing tool interfaces.</span></span>
                </label>
                <label className="flex items-start gap-2.5 cursor-pointer">
                  <input type="checkbox" checked={reduceMotion} onChange={(event) => setReduceMotion(event.target.checked)} />
                  <span><span className="ui-strong block">Reduce motion</span><span className="ui-meta">Disable non-essential shell transitions.</span></span>
                </label>
              </div>
            </div>
          )}

          {category === 'backends' && (
            <div className="space-y-4">
              <div>
                <h2 className="ui-h2">Backend connections</h2>
                <p className="ui-body mt-1">These are measured by the Seclyst supervisor, not simulated in the browser.</p>
              </div>
              <div className="space-y-2.5">
                {tools.map((tool) => {
                  const status = backendStatus[tool.id];
                  return (
                    <div key={tool.id} className="ui-well p-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                      <div className="min-w-0">
                        <div className="font-bold">{tool.name}</div>
                        <div className="ui-meta mt-0.5">{TRANSPORT[tool.id]} at <span className="sc-mono">{toolEndpoints[tool.id] || 'waiting for supervisor'}</span></div>
                      </div>
                      <div className="flex items-center gap-2">
                        <VerdictBadge
                          verdict={status === 'online' ? 'clean' : status === 'offline' ? 'malicious' : 'unknown'}
                          label={status === 'online' ? 'Online' : status === 'offline' ? 'Offline' : 'Starting'}
                        />
                        <button type="button" className="ui-btn ui-btn--ghost ui-btn--sm" onClick={() => onTestBackend(tool.id)}>Test</button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {category === 'apis' && <div className="space-y-4">
            <div><h2 className="ui-h2">Shared provider APIs</h2><p className="ui-body mt-1">One credential per provider is shared by every tool through SecLyst’s broker, cache, and rate limiter.</p></div>
            {Object.entries(centralSettings.providers || {}).map(([provider, state]: any) => <div className="ui-well p-3 flex flex-col sm:flex-row gap-3 sm:items-center" key={provider}><div className="flex-1"><span className="ui-strong block">{provider}</span><span className="ui-meta">{state.configured ? 'Configured in the secure server credential store' : 'Not configured'}</span></div><input className="ui-input sm:max-w-xs" type="password" placeholder="New API key" value={providerSecrets[provider] || ''} onChange={(event) => setProviderSecrets({...providerSecrets,[provider]:event.target.value})}/><button className="ui-btn ui-btn--primary" type="button" disabled={!providerSecrets[provider]} onClick={async()=>{await fetch(`/api/v1/settings/providers/${provider}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({secret:providerSecrets[provider]})});setProviderSecrets({...providerSecrets,[provider]:''});void reloadSettings();}}>Save</button></div>)}
          </div>}

          {category === 'tools' && <div className="space-y-4"><div><h2 className="ui-h2">Tool configuration</h2><p className="ui-body mt-1">Tool-specific behavior remains separate while provider credentials stay shared.</p></div><div className="ui-tabs">{tools.map((tool)=><button className="ui-tab" aria-selected={selectedTool===tool.id} key={tool.id} onClick={()=>setSelectedTool(tool.id)}>{tool.shortName}</button>)}</div><textarea className="ui-input sc-mono" rows={12} value={toolConfigText} onChange={(event)=>setToolConfigText(event.target.value)}/><button className="ui-btn ui-btn--primary" type="button" onClick={async()=>{try{const values=JSON.parse(toolConfigText);await fetch(`/api/v1/settings/tools/${selectedTool}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({values})});onAddToast({type:'success',title:'Tool configuration saved',description:'Restart SecLyst to apply engine-level changes.'});void reloadSettings();}catch{onAddToast({type:'error',title:'Invalid configuration JSON'});}}}>Save {TOOLS_REGISTRY[selectedTool].shortName} configuration</button></div>}

          {category === 'security' && (
            <div className="space-y-4">
              <h2 className="ui-h2">Security boundary</h2>
              <div className="ui-well ui-card-pad space-y-3">
                <p className="ui-body">Seclyst and all five copied engines are restricted to loopback. This build does not expose an unauthenticated network bind.</p>
                <p className="ui-body">Tool frames run on separate origins with a browser sandbox. They cannot read the shell DOM or its storage.</p>
                <p className="ui-body">Provider credentials belong in server-side environment files. Seclyst never stores API keys in localStorage.</p>
              </div>
            </div>
          )}

          {category === 'data' && (
            <div className="space-y-4">
              <h2 className="ui-h2">Shell data</h2>
              <p className="ui-body">The browser keeps only shell preferences, navigation state, and the shared IOC clipboard. Analysis history stays in each copied engine under <span className="sc-mono">runtime/</span>.</p>
              <p className="ui-body">Visited tool interfaces remain mounted while Seclyst is open so their routes, forms, and live connections survive navigation. Unloading an interface does not cancel backend work.</p>
              <div className="flex flex-wrap gap-3">
                <button type="button" className="ui-btn ui-btn--ghost" onClick={clearShellData}>Clear shell data</button>
                <button type="button" className="ui-btn ui-btn--ghost" onClick={onUnloadToolSessions}>Unload tool interfaces</button>
                <button
                  type="button"
                  className="ui-btn ui-btn--ghost"
                  onClick={() => downloadFileBlob('seclyst-settings.json', JSON.stringify({ theme, fontScale, compactMode, reduceMotion }, null, 2))}
                >
                  Export shell settings
                </button>
              </div>
            </div>
          )}

          {category === 'shortcuts' && (
            <div className="space-y-3">
              <h2 className="ui-h2">Keyboard shortcuts</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                {[
                  ['Ctrl + M / Cmd + M', 'Open universal navigation from anywhere']
                ].map(([key, description]) => (
                  <div key={key} className="ui-well p-3 flex items-center justify-between gap-3"><span>{description}</span><Kbd>{key}</Kbd></div>
                ))}
              </div>
            </div>
          )}

          {category === 'about' && (
            <div className="space-y-4">
              <h2 className="ui-h2">About Seclyst</h2>
              <p className="ui-body">Seclyst is a local analyst workbench that supervises five copied security engines while preserving each engine’s original interface.</p>
              <div className="ui-well ui-card-pad space-y-2 ui-meta sc-mono">
                <div>Shell: React 19 and TypeScript</div>
                <div>Supervisor: Python standard library</div>
                <div>Runtime data: local, ignored by version control</div>
                <div>Tool interfaces: live copied backends, isolated frames</div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
