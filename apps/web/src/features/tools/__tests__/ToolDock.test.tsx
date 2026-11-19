import { render, waitFor } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ToolDock } from '../ToolDock';
import { createToolSessions } from '../tool-session-store';
import type { ToolId } from '../../../data/workspace';

const endpoints: Record<ToolId, string> = {
  malware: 'http://127.0.0.1:7101/',
  ioc: 'http://127.0.0.1:7102/',
  events: 'http://127.0.0.1:7103/',
  phishing: 'http://127.0.0.1:7104/',
  ruleforge: 'http://127.0.0.1:7105/'
};

const status: Record<ToolId, 'online'> = {
  malware: 'online',
  ioc: 'online',
  events: 'online',
  phishing: 'online',
  ruleforge: 'online'
};

describe('ToolDock', () => {
  it('mounts tools lazily and retains an iframe across navigation', async () => {
    const sessions = createToolSessions();
    const view = render(
      <ToolDock activeTool="malware" endpoints={endpoints} status={status} sessions={sessions} unloadVersion={0} />
    );
    const malwareFrame = view.getByTitle('Malware Analyzer: original tool interface');
    expect(view.queryByTitle('Phishing Mail Detector: original tool interface')).not.toBeInTheDocument();

    view.rerender(
      <ToolDock activeTool="phishing" endpoints={endpoints} status={status} sessions={sessions} unloadVersion={0} />
    );
    await waitFor(() => expect(view.getByTitle('Phishing Mail Detector: original tool interface')).toBeInTheDocument());
    expect(view.getByTitle('Malware Analyzer: original tool interface')).toBe(malwareFrame);
    expect(view.getByTestId('tool-session-malware')).toHaveAttribute('aria-hidden', 'true');
    expect(view.getByTestId('tool-session-malware')).toHaveAttribute('inert');

    view.rerender(
      <ToolDock activeTool="malware" endpoints={endpoints} status={status} sessions={sessions} unloadVersion={0} />
    );
    expect(view.getByTitle('Malware Analyzer: original tool interface')).toBe(malwareFrame);
    expect(view.getByTestId('tool-session-malware')).not.toHaveAttribute('aria-hidden');
  });

  it('releases retained frames only after an explicit unload signal', async () => {
    const sessions = createToolSessions();
    const view = render(
      <ToolDock activeTool="malware" endpoints={endpoints} status={status} sessions={sessions} unloadVersion={0} />
    );
    view.rerender(
      <ToolDock activeTool="ioc" endpoints={endpoints} status={status} sessions={sessions} unloadVersion={0} />
    );
    await waitFor(() => expect(view.getByTitle('IOC Lookup Platform: original tool interface')).toBeInTheDocument());

    view.rerender(
      <ToolDock activeTool={null} endpoints={endpoints} status={status} sessions={sessions} unloadVersion={1} />
    );
    await waitFor(() => expect(view.queryAllByTitle(/original tool interface/)).toHaveLength(0));
  });
});
