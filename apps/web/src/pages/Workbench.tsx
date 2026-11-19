import React, { useState } from 'react';
import type { PageRouteId } from '../data/workspace';

export function Workbench({ onNavigate }: { onNavigate: (page: PageRouteId) => void }) {
  const [question, setQuestion] = useState('');
  const [artifact, setArtifact] = useState<Record<string, unknown> | null>(null);
  const [uploading, setUploading] = useState(false);

  const upload = async (file?: File) => {
    if (!file) return;
    setUploading(true);
    try {
      const body = new FormData();
      body.append('file', file);
      const response = await fetch('/api/v1/artifacts', { method: 'POST', body });
      if (!response.ok) throw new Error(`Upload failed with HTTP ${response.status}`);
      setArtifact(await response.json());
    } finally {
      setUploading(false);
    }
  };

  return <div className="sc-page">
    <header className="sc-page-head">
      <div className="sc-page-head-main">
        <div className="sc-crumbs">SecLyst <span className="sc-crumbs-sep">/</span> Workbench</div>
        <h1 className="sc-page-title">Start with the question, not the tool.</h1>
        <p className="sc-page-desc">Add the evidence once. SecLyst will retain its identity, provenance and specialist-tool context throughout the analysis.</p>
      </div>
    </header>
    <section className="ui-card ui-card-pad space-y-5">
      <label className="space-y-2 block">
        <span className="ui-strong block">What are you trying to determine?</span>
        <textarea className="ui-input" rows={3} value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Is this email malicious? Can this behavior be detected in our logs?" />
      </label>
      <label className="ui-well ui-card-pad block cursor-pointer">
        <span className="ui-h3 block">Add evidence</span>
        <span className="ui-body block mt-1">Email, executable, document, EVTX log or other investigation artifact</span>
        <input className="mt-3" type="file" disabled={uploading} onChange={(event) => void upload(event.target.files?.[0])} />
      </label>
      {artifact && <div className="ui-well p-3">
        <span className="ui-strong block">Artifact stored and fingerprinted</span>
        <span className="ui-meta sc-mono block mt-1">{String(artifact.sha256)}</span>
        <span className="ui-meta block">{String(artifact.original_name)} · {String(artifact.size_bytes)} bytes</span>
      </div>}
      <div className="flex flex-wrap gap-3">
        <button className="ui-btn ui-btn--primary" type="button" disabled={!question.trim() || !artifact} onClick={() => onNavigate('dashboard')}>Create analysis run</button>
        <button className="ui-btn ui-btn--ghost" type="button" onClick={() => onNavigate('dashboard')}>Open existing runs</button>
      </div>
      <p className="ui-meta">Workflow execution is enabled in the next phase. This phase establishes real artifact intake and removes fabricated platform metrics.</p>
    </section>
  </div>;
}
