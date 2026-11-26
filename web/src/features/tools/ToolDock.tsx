import React from 'react';
import { useEffect, useRef, useState } from 'react';
import type { ToolId } from '../../data/workspace';
import { ToolFrame } from '../../ui/ToolFrame';
import type { ToolSessionMap } from './tool-session-store';
import { parseToolBridgeMessage, isTrustedToolMessage } from './frame-protocol';
import type { ToolBridgeMessage } from './frame-protocol';

export interface ToolDockProps {
  activeTool: ToolId | null;
  endpoints: Record<ToolId, string>;
  status: Record<ToolId, 'online' | 'offline' | 'unknown'>;
  sessions: ToolSessionMap;
  unloadVersion: number;
  onBridgeMessage?: (message: ToolBridgeMessage) => void;
}

export function ToolDock({
  activeTool,
  endpoints,
  status,
  sessions,
  unloadVersion,
  onBridgeMessage
}: ToolDockProps) {
  const [mountedTools, setMountedTools] = useState<ToolId[]>(() => activeTool ? [activeTool] : []);
  const frames = useRef<Partial<Record<ToolId, HTMLIFrameElement | null>>>({});
  const unloadVersionRef = useRef(unloadVersion);

  useEffect(() => {
    if (!activeTool) return;
    setMountedTools((current) => current.includes(activeTool) ? current : [...current, activeTool]);
  }, [activeTool]);

  useEffect(() => {
    if (unloadVersionRef.current === unloadVersion) return;
    unloadVersionRef.current = unloadVersion;
    setMountedTools(activeTool ? [activeTool] : []);
  }, [activeTool, unloadVersion]);

  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      const message = parseToolBridgeMessage(event.data);
      if (!message || !mountedTools.includes(message.tool)) return;
      const frameWindow = frames.current[message.tool]?.contentWindow ?? null;
      if (!isTrustedToolMessage(event, endpoints[message.tool], frameWindow)) return;
      onBridgeMessage?.(message);
    };
    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [endpoints, mountedTools, onBridgeMessage]);

  return (
    <div
      className={`sc-tool-dock ${activeTool ? 'is-active' : ''}`}
      aria-hidden={activeTool ? undefined : true}
      data-testid="tool-dock"
    >
      {mountedTools.map((tool) => {
        const active = tool === activeTool;
        return (
          <section
            key={tool}
            className={`sc-tool-session ${active ? 'is-active' : ''}`}
            data-tool={tool}
            data-testid={`tool-session-${tool}`}
            aria-hidden={active ? undefined : true}
            inert={!active}
          >
            <ToolFrame
              ref={(frame) => { frames.current[tool] = frame; }}
              tool={tool}
              endpoint={endpoints[tool]}
              status={status[tool]}
              query={sessions[tool].query}
            />
          </section>
        );
      })}
    </div>
  );
}
