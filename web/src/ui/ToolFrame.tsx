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

export interface ToolFrameProps {
  tool: ToolId;
  endpoint?: string;
  status: 'online' | 'offline' | 'unknown';
  query?: string;
}

function isLoopbackHost(host: string): boolean {
  return host === '127.0.0.1' || host === 'localhost' || host === '[::1]' || host === '::1';
}

/* An engine sets its access cookie with SameSite=Strict. Browsers treat
   localhost and 127.0.0.1 as different sites, so a shell opened on localhost
   that frames an engine on 127.0.0.1 is cross-site and the cookie is withheld —
   every API call inside the frame then answers "SecLyst access required".
   Frame the engine on the same loopback name the shell is using so the cookie
   is same-site and is sent. */
function frameUrl(endpoint: string, query: string): string {
  const url = new URL(endpoint);
  const pageHost = typeof window !== 'undefined' ? window.location.hostname : '';
  if (isLoopbackHost(url.hostname) && isLoopbackHost(pageHost) && url.hostname !== pageHost) {
    url.hostname = pageHost;
  }
  if (query) {
    const toolQuery = new URLSearchParams(query.startsWith('?') ? query.slice(1) : query);
    toolQuery.forEach((value, key) => url.searchParams.set(key, value));
  }
  return url.toString();
}

export const ToolFrame = React.forwardRef<HTMLIFrameElement, ToolFrameProps>(function ToolFrame(
  { tool, endpoint, status, query = '' },
  ref
) {
  const definition = TOOLS_REGISTRY[tool];
  const src = endpoint ? frameUrl(endpoint, query) : '';

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
      ref={ref}
      key={src}
      className="sc-frame"
      data-tool={tool}
      src={src}
      title={`${definition.name}: original tool interface`}
      sandbox="allow-downloads allow-forms allow-modals allow-popups allow-same-origin allow-scripts"
      allow="clipboard-read; clipboard-write"
      referrerPolicy="no-referrer"
    />
  );
});
