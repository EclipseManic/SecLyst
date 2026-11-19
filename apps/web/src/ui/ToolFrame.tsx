// ==========================================================================
// the original tool interface, hosted
// ==========================================================================
//
// Each tool screen in Seclyst is that tool's own interface, served by the
// copied live backend on an isolated loopback origin. This component is the
// mount; it does not redraw or reinterpret the tool.
//
// It deliberately draws nothing: no card, no border, no padding, no inset
// shadow. A tool is a whole application with its own header and its own
// scrolling, so it gets the content region edge to edge and the shell stays
// out of it. Anything drawn here would be a frame inside a frame.
//
// Cross-origin framing is intentional. It preserves each tool's scripts and
// CSS while preventing them from reading the shell's DOM or browser storage.

import React from 'react';
import { TOOLS_REGISTRY } from '../data/workspace';
import type { ToolId } from '../data/workspace';

export const ToolFrame: React.FC<{
  tool: ToolId;
  endpoint?: string;
  status: 'online' | 'offline' | 'unknown';
  query?: string;
}> = ({ tool, endpoint, status, query = '' }) => {
  const definition = TOOLS_REGISTRY[tool];
  const src = endpoint ? new URL(query || '.', endpoint).toString() : '';

  if (!endpoint || status !== 'online') {
    return (
      <section className="sc-frame-state" role="status" aria-live="polite">
        <div className="sc-frame-state-copy">
          <span className="ui-badge">{status === 'unknown' ? 'Starting' : 'Offline'}</span>
          <h1 className="ui-h2">{definition.name} is not ready</h1>
          <p className="ui-body">
            Seclyst will load the original {definition.shortName} interface here as soon as its
            copied backend passes a live health check.
          </p>
          <p className="ui-meta sc-mono">Check runtime/logs/{tool}.log if this state persists.</p>
        </div>
      </section>
    );
  }

  return (
    <iframe
      key={src}
      className="sc-frame"
      src={src}
      title={`${definition.name}: original tool interface`}
      sandbox="allow-downloads allow-forms allow-modals allow-popups allow-same-origin allow-scripts"
      allow="clipboard-read; clipboard-write"
      referrerPolicy="no-referrer"
    />
  );
};
