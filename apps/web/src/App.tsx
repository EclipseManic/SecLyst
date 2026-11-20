// ==========================================================================
// the application shell
// ==========================================================================
import React from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { TOOLS_REGISTRY } from './data/workspace';
import type { ActivityItem, IOCClipboardItem, PageRouteId, ToastMessage, ToolDefinition, ToolId } from './data/workspace';
import { apiClient, copyTextToClipboard, safeLocalGet, safeLocalSet, safeSessionGet, safeSessionSet, summaryToActivity } from './lib/api-client';
import type { PlatformSummary } from './lib/api-client';
import { BrandShieldIcon, ShellIcon, ToolIcon } from './lib/icons';
import { ToolDock } from './features/tools/ToolDock';
import type { ToolBridgeMessage } from './features/tools/frame-protocol';
import { activateToolSession, createToolSessions, updateToolSessionQuery } from './features/tools/tool-session-store';
import { Dashboard } from './pages/Dashboard';
import { ActivityPage } from './pages/Activity';
import { SettingsPage } from './pages/SettingsLive';
// Each tool screen is that tool's own interface, hosted rather than redrawn.
import { ToolFrame } from './ui/ToolFrame';
import { Kbd, Modal } from './ui/index';

// The sidebar is the product's information architecture: what the workspace
// is, the five tools, and the settings that apply to all of them. It is the
// only way to change screen — there used to be five, none of them obvious.
const WORKSPACE_NAV: { page: PageRouteId; label: string; icon: 'home' | 'dashboard'; hotkey: string }[] = [
  { page: 'home', label: 'Dashboard', icon: 'home', hotkey: '' },
  { page: 'activity', label: 'Activity', icon: 'dashboard', hotkey: '' }
];

const KEEPALIVE_TOOL_FRAMES = import.meta.env.VITE_SECLYST_KEEPALIVE_FRAMES !== '0';

function classifyIndicator(value: string): IOCClipboardItem['type'] {
  if (/^https?:\/\//i.test(value)) return 'url';
  if (/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) return 'email';
  if (/^[a-z]:\\|^\//i.test(value)) return 'path';
  if (/^(?:\d{1,3}\.){3}\d{1,3}$/.test(value) || /^[a-f0-9:]+$/i.test(value)) return 'ip';
  if (/^[a-f0-9]{32}$|^[a-f0-9]{40}$|^[a-f0-9]{64}$/i.test(value)) return 'hash';
  if (/^[a-z0-9.-]+\.[a-z]{2,}$/i.test(value)) return 'domain';
  return 'registry';
}

// What the top bar says about where you are. A tool screen brings its own
// header, so a tool's entry here is its name and nothing else.
// There is no PAGE_META table any more. The bar that read it is gone: a hosted
// tool brings its own header, and a shell screen states its own name and
// purpose in its page head. One owner per label.

export default function App() {
  // Navigation & Route State (persisted in sessionStorage so refresh retains context — Bug #4 Fix)
  const [page, setPage] = useState<PageRouteId>(() => safeSessionGet<PageRouteId>('seclyst.page', 'home'));
  const [mainTab, setMainTab] = useState<string>(() => safeSessionGet<string>('seclyst.mainTab', 'overview'));
  const [subTab, setSubTab] = useState<string>(() => safeSessionGet<string>('seclyst.subTab', 'dashboard'));

  // Cross-Tool Pivot State & Shared IOC Clipboard
  const [iocClipboard, setIocClipboard] = useState<IOCClipboardItem[]>(() =>
    safeSessionGet<IOCClipboardItem[]>('seclyst.clipboard', [])
  );
  const [clipboardOpen, setClipboardOpen] = useState(false);
  const [clipboardDraft, setClipboardDraft] = useState('');

  // A visited tool remains mounted for this browser lifetime. The server owns
  // analysis data; this map retains only presentation-level deep links.
  const [toolSessions, setToolSessions] = useState(createToolSessions);
  const [toolUnloadVersion, setToolUnloadVersion] = useState(0);

  const setToolQuery = useCallback((tool: ToolId, query: string) => {
    setToolSessions((sessions) => updateToolSessionQuery(sessions, tool, query));
  }, []);

// Shell overlays: the command palette, notifications, the account menu and
  // the tour. The tool-switcher dropdown that used to sit in the header is
  // gone; the sidebar replaced it.
  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(() => safeLocalGet('seclyst.sidebarCollapsed', false));
  const [sidebarWidth, setSidebarWidth] = useState<number>(() => safeLocalGet('seclyst.sidebarWidth', 248));
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);
  const [commandQuery, setCommandQuery] = useState('');
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);

  // Shell preferences
  const theme = 'dark' as const;
  const [fontScale, setFontScale] = useState<number>(() => safeLocalGet('seclyst.fontScale', 100));
  const [compactMode, setCompactMode] = useState<boolean>(() => safeLocalGet('seclyst.compact', false));
  const [reduceMotion, setReduceMotion] = useState<boolean>(() => safeLocalGet('seclyst.reduceMotion', false));
  const userName = 'Local Analyst';

  // Activity Feed, Toasts & Backend Health
  const [activityFeed, setActivityFeed] = useState<ActivityItem[]>([]);
  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const [platformSummary, setPlatformSummary] = useState<PlatformSummary | null>(null);
  const [platformRefreshing, setPlatformRefreshing] = useState(false);
  const [toolEndpoints, setToolEndpoints] = useState<Record<ToolId, string>>({
    malware: '',
    ioc: '',
    events: '',
    phishing: '',
    ruleforge: ''
  });
// Health starts as `unknown`, not `online`. It used to start green for all
// five, which meant the Command Center opened showing "5/5 Engines Online"
// before anything had been checked — and none of these backends is mounted.
  const [backendStatus, setBackendStatus] = useState<Record<ToolId, 'online' | 'offline' | 'unknown'>>({
    malware: 'unknown',
    ioc: 'unknown',
    events: 'unknown',
    phishing: 'unknown',
    ruleforge: 'unknown'
  });

  const addToast = useCallback((t: Omit<ToastMessage, 'id'>) => {
    const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
    setToasts((prev) => [...prev.slice(-4), { ...t, id }]);
    if (t.type !== 'error') {
      setTimeout(() => {
        setToasts((prev) => prev.filter((item) => item.id !== id));
      }, 4500);
    }
  }, []);

  const refreshPlatform = useCallback(async () => {
    setPlatformRefreshing(true);
    try {
      const [platform, summary] = await Promise.all([apiClient.status(), apiClient.summary()]);
      const nextStatus = {} as Record<ToolId, 'online' | 'offline' | 'unknown'>;
      const nextEndpoints = {} as Record<ToolId, string>;
      (Object.keys(TOOLS_REGISTRY) as ToolId[]).forEach((tool) => {
        const state = platform.tools[tool];
        nextStatus[tool] = state?.status === 'online'
          ? 'online'
          : state?.status === 'starting'
            ? 'unknown'
            : 'offline';
        nextEndpoints[tool] = state?.url || '';
      });
      setBackendStatus(nextStatus);
      setToolEndpoints(nextEndpoints);
      setPlatformSummary(summary);
      setActivityFeed(summaryToActivity(summary));
    } catch {
      setBackendStatus({
        malware: 'offline',
        ioc: 'offline',
        events: 'offline',
        phishing: 'offline',
        ruleforge: 'offline'
      });
    } finally {
      setPlatformRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void refreshPlatform();
    const timer = window.setInterval(() => void refreshPlatform(), 10000);
    return () => window.clearInterval(timer);
  }, [refreshPlatform]);

  // Persist navigation & active tool IDs to sessionStorage (Bug #4 Fix)
  useEffect(() => {
    safeSessionSet('seclyst.page', page);
    safeSessionSet('seclyst.mainTab', mainTab);
    safeSessionSet('seclyst.subTab', subTab);
safeSessionSet('seclyst.clipboard', iocClipboard);
  }, [page, mainTab, subTab, iocClipboard]);

  // Persist preferences to localStorage
  useEffect(() => {
    safeLocalSet('seclyst.fontScale', fontScale);
    safeLocalSet('seclyst.compact', compactMode);
safeLocalSet('seclyst.reduceMotion', reduceMotion);
    safeLocalSet('seclyst.sidebarCollapsed', sidebarCollapsed);
    safeLocalSet('seclyst.sidebarWidth', sidebarWidth);
  }, [fontScale, compactMode, reduceMotion, sidebarCollapsed, sidebarWidth]);

  // Sync hash URL & document attributes
  const navigateTo = useCallback((targetPage: PageRouteId, targetMain?: string, targetSub?: string) => {
    setPage(targetPage);
    if (targetPage in TOOLS_REGISTRY) {
      const tDef = TOOLS_REGISTRY[targetPage as ToolId];
      const m = targetMain || tDef.mainTabs[0].id;
      const s = targetSub || tDef.subTabs[0].id;
      setMainTab(m);
      setSubTab(s);
      try {
        window.location.hash = m === 'overview' ? `#/t/${targetPage}` : `#/t/${targetPage}/${m}`;
      } catch {
        // Ignore in restricted iframe
      }
    } else {
      try {
        window.location.hash = targetPage === 'home' ? '#/' : `#/${targetPage}`;
      } catch {
        // Ignore
      }
}
    setCommandPaletteOpen(false);
    setNotificationsOpen(false);
    setUserMenuOpen(false);
  }, []);

  /* Read the hash back.

     navigateTo() has always WRITTEN the hash, and the routes are documented
     (#/t/malware, #/t/malware/investigation), but nothing ever read it: a deep
     link opened the landing page, and a refresh lost the tool you were in.
     Parsing it here closes that loop.

     Sub-tabs are deliberately not in the URL — navigateTo() does not encode
     them — so landing on a main tab resets to that tab's first sub-tab rather
     than inheriting an unrelated one from the previous screen. */
  const routeRef = useRef({ page, mainTab });
  useEffect(() => {
    routeRef.current = { page, mainTab };
  }, [page, mainTab]);

  useEffect(() => {
    const applyHash = () => {
      const raw = window.location.hash.replace(/^#\/?/, '');
      const [scope, id, tab] = raw.split('/');

      let nextPage: PageRouteId | null = null;
      if (!raw) nextPage = 'home';
      else if (scope === 't' && id && id in TOOLS_REGISTRY) nextPage = id as ToolId;
      else if (scope === 'home' || scope === 'activity' || scope === 'settings') {
        nextPage = scope as PageRouteId;
      } else if (scope === 'dashboard' || scope === 'detections') {
        nextPage = 'home';
      }
      if (!nextPage) return;

      const nextMain =
        nextPage in TOOLS_REGISTRY
          ? tab || TOOLS_REGISTRY[nextPage as ToolId].mainTabs[0].id
          : null;

      // navigateTo() already set this exact state before writing the hash.
      // Acting on it again would stomp the sub-tab it just chose.
      if (
        routeRef.current.page === nextPage &&
        (nextMain === null || routeRef.current.mainTab === nextMain)
      ) {
        return;
      }

      setPage(nextPage);
      if (nextMain) {
        setMainTab(nextMain);
        setSubTab(TOOLS_REGISTRY[nextPage as ToolId].subTabs[0].id);
      }
    };

    applyHash();
    window.addEventListener('hashchange', applyHash);
    return () => window.removeEventListener('hashchange', applyHash);
  }, []);

  // Global keyboard shortcuts (Section 4.3 & 18)
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'm') {
        e.preventDefault();
        setCommandPaletteOpen((prev) => !prev);
        return;
      }
if (e.key === 'Escape') {
        setCommandPaletteOpen(false);
        setNotificationsOpen(false);
        setUserMenuOpen(false);
        return;
      }
      const tag = (e.target as HTMLElement)?.tagName?.toLowerCase();
      if (tag === 'input' || tag === 'textarea' || tag === 'select') return;

    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
}, [navigateTo]);

  /* Dismiss the rail's popovers on a press anywhere else.

     They used to be closed only by pressing their own button a second time or
     by Escape, so once opened they stayed open across whatever you did next —
     the report was that the activity and account menus "get stuck". A press
     inside a popover wrapper is that popover's own business: it is either the
     trigger toggling itself or a row being used. A press anywhere else closes
     both. This listens on pointerdown, which runs before the trigger's own
     click, so pressing the other menu's button still opens it rather than
     being swallowed by the dismissal. */
  useEffect(() => {
    if (!notificationsOpen && !userMenuOpen) return;
    const onPointerDown = (event: PointerEvent) => {
      const target = event.target as HTMLElement | null;
      if (target && target.closest('.sc-rail-pop-wrap')) return;
      setNotificationsOpen(false);
      setUserMenuOpen(false);
    };
    document.addEventListener('pointerdown', onPointerDown);
    return () => document.removeEventListener('pointerdown', onPointerDown);
  }, [notificationsOpen, userMenuOpen]);

// `handlePinIoc` lived here. It pinned an indicator from inside a tool into
// the shell's clipboard, and it is gone with the React tool screens: a tool is
// its own interface now and cannot reach into the shell. Pinning is done in
// the clipboard panel itself.

  const resolvedTheme = 'dark' as const;

  const activeTool: ToolId | null = page in TOOLS_REGISTRY ? page as ToolId : null;
  const currentToolDef = activeTool ? TOOLS_REGISTRY[activeTool] : null;
  const isToolPage = page in TOOLS_REGISTRY;
  const unreadCount = activityFeed.filter((a) => a.unread).length;

  useEffect(() => {
    if (!activeTool) return;
    setToolSessions((sessions) => activateToolSession(sessions, activeTool));
  }, [activeTool]);

  const handleToolBridgeMessage = useCallback((message: ToolBridgeMessage) => {
    if (message.type === 'command.open') {
      setCommandPaletteOpen(true);
      return;
    }
    if (message.type !== 'route.changed') return;
    const query = message.payload.query;
    if (typeof query === 'string' && query.startsWith('?')) {
      setToolQuery(message.tool, query);
    }
  }, [setToolQuery]);

  // Command Palette searchable items
  const commandItems = useMemo(() => {
    const list = [
      { category: 'Navigation', label: 'Dashboard', hotkey: '', action: () => navigateTo('home') },
      { category: 'Tools', label: 'IOC Lookup', hotkey: '', action: () => navigateTo('ioc', 'lookup', 'lookup') },
      { category: 'Tools', label: 'Malware Analyzer', hotkey: '', action: () => navigateTo('malware', 'investigation', 'dashboard') },
      { category: 'Tools', label: 'Phishing Detector', hotkey: '', action: () => navigateTo('phishing', 'analysis', 'dashboard') },
      { category: 'Tools', label: 'Event Analyzer', hotkey: '', action: () => navigateTo('events', 'investigation', 'events') },
      { category: 'Tools', label: 'RuleForge', hotkey: '', action: () => navigateTo('ruleforge', 'workshop', 'author') },
      { category: 'Actions', label: 'Run a malware scan', hotkey: '', action: () => navigateTo('malware', 'investigation', 'dashboard') },
      { category: 'Actions', label: 'Upload an EVTX log', hotkey: '', action: () => navigateTo('events', 'investigation', 'events') },
      { category: 'Actions', label: 'Analyze a phishing email', hotkey: '', action: () => navigateTo('phishing', 'analysis', 'dashboard') },
      { category: 'Navigation', label: 'Activity', hotkey: '', action: () => navigateTo('activity') },
      { category: 'Settings', label: 'Backend connections', hotkey: '', action: () => navigateTo('settings') }
    ];
    if (!commandQuery.trim()) return list;
    return list.filter((i) => `${i.category} ${i.label}`.toLowerCase().includes(commandQuery.toLowerCase()));
  }, [commandQuery, navigateTo]);

const userInitials = userName
    .split(' ')
    .map((part) => part.charAt(0))
    .join('')
    .slice(0, 2)
    .toUpperCase();

  // The palette lists the same things grouped by what they are, in the order
  // an analyst reaches for them.
  const commandGroups = useMemo(() => {
    const order = ['Navigation', 'Tools', 'Actions', 'Settings'];
    const buckets = new Map<string, { label: string; hotkey: string; action: () => void }[]>();
    commandItems.forEach((item) => {
      const bucket = buckets.get(item.category) ?? [];
      bucket.push(item);
      buckets.set(item.category, bucket);
    });
    return order
      .filter((category) => buckets.has(category))
      .map((category) => ({ category, items: buckets.get(category) ?? [] }));
  }, [commandItems]);

  return (
    <div
      className="sc-root sc-app"
      data-theme={resolvedTheme}
      data-tool={currentToolDef ? currentToolDef.id : 'home'}
      data-compact={compactMode ? 'true' : 'false'}
      data-reduce-motion={reduceMotion ? 'true' : 'false'}
      style={{ fontSize: `${fontScale}%` }}
    >
      {/* =================================================================== */}
      {/* RAIL — navigation and every global control, in one column            */}
      {/* =================================================================== */}
      <aside
        className="sc-rail"
        data-collapsed={sidebarCollapsed ? 'true' : 'false'}
        style={sidebarCollapsed ? undefined : { width: sidebarWidth }}
        aria-label="Workspace navigation"
      >
        <div className="sc-rail-head">
          <button
            type="button"
            className="sc-brand"
            onClick={() => navigateTo('home')}
            title="Seclyst: Overview"
          >
            <BrandShieldIcon size={22} />
            <span className="sc-brand-name">Seclyst</span>
          </button>
        </div>

        <nav className="sc-rail-nav" aria-label="Screens">
          <div className="sc-rail-group">Workspace</div>
          {WORKSPACE_NAV.map((item) => (
            <button
              key={item.page}
              type="button"
              className="sc-nav-item"
              aria-current={page === item.page ? 'page' : undefined}
              onClick={() => navigateTo(item.page)}
              title={item.label}
            >
              <span className="sc-nav-icon">
                <ToolIcon tool={item.icon} size={17} />
              </span>
              <span className="sc-nav-label">{item.label}</span>
              <span className="sc-nav-hint">
                {item.hotkey && <Kbd>{item.hotkey}</Kbd>}
              </span>
            </button>
          ))}

          <div className="sc-rail-group">Tools</div>
          {(Object.values(TOOLS_REGISTRY) as ToolDefinition[]).map((tool) => (
            <button
              key={tool.id}
              type="button"
              className="sc-nav-item"
              aria-current={page === tool.id ? 'page' : undefined}
              onClick={() => navigateTo(tool.id, tool.mainTabs[1].id, tool.subTabs[0].id)}
              title={tool.tagline}
            >
              <span className="sc-nav-icon">
                <ToolIcon tool={tool.id} size={17} />
              </span>
              <span className="sc-nav-label">{tool.name}</span>
            </button>
          ))}
        </nav>

        {/* Everything global, at the bottom of the rail: search, activity,
            account, the clipboard, settings, theme and the collapse toggle.
            The content region is left to the screen you are on. */}
        <div className="sc-rail-foot">
          <button
            type="button"
            className="sc-rail-search"
            onClick={() => setCommandPaletteOpen(true)}
            title="Search and commands"
          >
            <ShellIcon name="search" size={16} />
            <span className="sc-rail-search-label">Search</span>
            <span className="sc-rail-kbd">
              <Kbd>Ctrl M</Kbd>
            </span>
          </button>

          {/* account */}
          <div className="sc-rail-pop-wrap">
            <button
              type="button"
              className="sc-nav-item"
              aria-expanded={userMenuOpen}
              onClick={() => {
                setUserMenuOpen(!userMenuOpen);
                setNotificationsOpen(false);
              }}
              title={`${userName}, local session`}
            >
              <span className="sc-avatar">{userInitials}</span>
              <span className="sc-nav-label">{userName}</span>
              <span className="sc-nav-hint"><ShellIcon name="more" size={15} /></span>
            </button>

            {userMenuOpen && (
              <div className="sc-pop" role="dialog" aria-label="Account">
                <div className="sc-pop-head">
                  <div>
                    <div className="sc-pop-title">{userName}</div>
                    <div className="ui-meta">This session, not authenticated</div>
                  </div>
                </div>
                <div className="sc-pop-body">
                  <p className="ui-body" style={{ padding: '6px 10px' }}>
                    Seclyst is running as a loopback-only local workbench. No authentication or role guard is simulated.
                  </p>
                </div>
                <div className="sc-pop-foot">
                  <button
                    type="button"
                    className="ui-btn ui-btn--quiet ui-btn--sm"
                    onClick={() => navigateTo('settings')}
                  >
                    Settings
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* the shared clipboard */}
          <button
            type="button"
            className="sc-nav-item"
            onClick={() => setClipboardOpen(true)}
            title="Shared IOC clipboard"
          >
            <span className="sc-nav-icon" aria-hidden="true">
              <ShellIcon name="clipboard" size={17} />
            </span>
            <span className="sc-nav-label">IOC clipboard</span>
            <span className="sc-nav-hint ui-meta sc-mono">{iocClipboard.length}</span>
          </button>

          <button
            type="button"
            className="sc-nav-item"
            aria-current={page === 'settings' ? 'page' : undefined}
            onClick={() => navigateTo('settings')}
            title="Settings"
          >
            <span className="sc-nav-icon" aria-hidden="true">
              <ShellIcon name="settings" size={17} />
            </span>
            <span className="sc-nav-label">Settings</span>
          </button>

          <div className="sc-rail-tools">
            <button
              type="button"
              className="sc-icon-btn"
              onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
              title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              aria-expanded={!sidebarCollapsed}
            >
              <ShellIcon name="panel" size={17} />
            </button>
          </div>
        </div>
        {!sidebarCollapsed && <div className="sc-rail-resize" role="separator" aria-orientation="vertical" onPointerDown={(event) => {
          const startX = event.clientX; const startWidth = sidebarWidth;
          const move = (moveEvent: PointerEvent) => setSidebarWidth(Math.max(216, Math.min(380, startWidth + moveEvent.clientX - startX)));
          const stop = () => { window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', stop); };
          window.addEventListener('pointermove', move); window.addEventListener('pointerup', stop);
        }} />}
      </aside>

      {/* =================================================================== */}
      {/* CONTENT — a shell screen scrolls its own column; a hosted tool fills */}
      {/* the region, because a tool is a whole application with its own head */}
      {/* =================================================================== */}
      <div className="sc-main">
        <main
          className={`sc-content ${isToolPage ? 'sc-content--frame' : ''}`}
        >
          {page === 'home' && (
            <div className="sc-scroll">
              <Dashboard
                backendStatus={backendStatus}
                activityCount={activityFeed.length}
                onOpenTool={(tool) => navigateTo(tool)}
                onQuickIoc={(ioc) => {
                  setToolQuery('ioc', `?page=lookup&ioc=${encodeURIComponent(ioc)}`);
                  navigateTo('ioc', 'lookup', 'lookup');
                }}
              />
            </div>
          )}
          {page === 'activity' && <div className="sc-scroll"><ActivityPage items={activityFeed} /></div>}

          {KEEPALIVE_TOOL_FRAMES ? (
            <ToolDock
              activeTool={activeTool}
              endpoints={toolEndpoints}
              status={backendStatus}
              sessions={toolSessions}
              unloadVersion={toolUnloadVersion}
              onBridgeMessage={handleToolBridgeMessage}
            />
          ) : activeTool ? (
            <ToolFrame
              tool={activeTool}
              endpoint={toolEndpoints[activeTool]}
              status={backendStatus[activeTool]}
              query={toolSessions[activeTool].query}
            />
          ) : null}

          {page === 'settings' && (
            <div className="sc-scroll">
              <SettingsPage
                theme={theme}
                setTheme={() => undefined}
                fontScale={fontScale}
                setFontScale={setFontScale}
                compactMode={compactMode}
                setCompactMode={setCompactMode}
                reduceMotion={reduceMotion}
                setReduceMotion={setReduceMotion}
                backendStatus={backendStatus}
                toolEndpoints={toolEndpoints}
                onTestBackend={async (tid) => {
                  const res = await apiClient.healthCheck(tid);
                  setBackendStatus((prev) => ({ ...prev, [tid]: res.status }));
                  addToast({
                    type: res.status === 'online' ? 'success' : 'warning',
                   title: `${TOOLS_REGISTRY[tid].name}: ${res.status}`,
                    description: `Live supervisor check, latency ${res.latencyMs}ms${res.version ? `, Seclyst ${res.version}` : ''}`
                  });
                }}
                onUnloadToolSessions={() => {
                  setToolUnloadVersion((version) => version + 1);
                  addToast({
                    type: 'success',
                    title: 'Tool interfaces unloaded',
                    description: 'Inactive tool frames were released. Running backend work is unaffected.'
                  });
                }}
                onAddToast={addToast}
              />
            </div>
          )}

        </main>
      </div>

      {/* =================================================================== */}
      {/* SHARED IOC CLIPBOARD — a drawer, opened from the rail                */}
      {/* =================================================================== */}
      {clipboardOpen && (
        <>
          <div className="sc-scrim" onClick={() => setClipboardOpen(false)} aria-hidden="true" />
          <aside className="sc-drawer" aria-label="Shared IOC clipboard">
            <div className="sc-drawer-head">
              <div>
                <div className="ui-h3">Shared IOC clipboard</div>
                <div className="ui-meta">{iocClipboard.length} of 50 indicators, this session</div>
              </div>
              <button
                type="button"
                className="sc-icon-btn"
                onClick={() => setClipboardOpen(false)}
                aria-label="Close clipboard"
              >
                <ShellIcon name="close" size={16} />
              </button>
            </div>

            <div className="sc-drawer-body">
              <div className="ui-well p-3 flex gap-2">
                <input
                  type="text"
                  className="ui-input sc-mono"
                  value={clipboardDraft}
                  onChange={(event) => setClipboardDraft(event.target.value)}
                  placeholder="IP, domain, hash, URL, email, path"
                  aria-label="Indicator to add"
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') event.currentTarget.nextElementSibling?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
                  }}
                />
                <button
                  type="button"
                  className="ui-btn ui-btn--primary"
                  onClick={() => {
                    const value = clipboardDraft.trim();
                    if (!value) return;
                    if (iocClipboard.some((item) => item.value.toLowerCase() === value.toLowerCase())) {
                      addToast({ type: 'info', title: 'Already in clipboard', description: value });
                      return;
                    }
                    const sourceTool: ToolId = page in TOOLS_REGISTRY ? page as ToolId : 'ioc';
                    const clipboardItem: IOCClipboardItem = {
                      id: `clip-${Date.now()}`,
                      value,
                      type: classifyIndicator(value),
                      sourceTool,
                      sourceContext: 'Added from the Seclyst shell',
                      verdict: 'unknown',
                      addedAt: new Date().toLocaleTimeString()
                    };
                    setIocClipboard((items) => [clipboardItem, ...items].slice(0, 50));
                    setClipboardDraft('');
                  }}
                >
                  Add
                </button>
              </div>
              {iocClipboard.length === 0 ? (
                <div className="ui-empty">
                  <span className="ui-h3">Nothing pinned</span>
                  <span className="ui-body">Indicators you add here stay for the session.</span>
                </div>
              ) : (
                iocClipboard.map((item) => (
                  <div key={item.id} className="ui-card ui-card--raised" style={{ padding: 12 }}>
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="sc-mono text-xs font-bold truncate" title={item.value}>
                          {item.value}
                        </div>
                        <div className="ui-meta mt-1">
                          {TOOLS_REGISTRY[item.sourceTool].shortName}, {item.sourceContext}
                        </div>
                      </div>
                      <div className="flex items-center gap-1 shrink-0">
                        <button
                          type="button"
                          className="ui-btn ui-btn--quiet ui-btn--sm"
                          onClick={() => {
                            copyTextToClipboard(item.value);
                            addToast({ type: 'success', title: 'Copied', description: item.value });
                          }}
                        >
                          Copy
                        </button>
                        <button
                          type="button"
                          className="sc-icon-btn"
                          onClick={() => setIocClipboard(iocClipboard.filter((x) => x.id !== item.id))}
                          aria-label={`Remove ${item.value}`}
                        >
                          <ShellIcon name="close" size={16} />
                        </button>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>

            {iocClipboard.length > 0 && (
              <div className="sc-drawer-foot">
                <button
                  type="button"
                  className="ui-btn ui-btn--ghost"
                  onClick={() => {
                    copyTextToClipboard(iocClipboard.map((c) => c.value).join('\n'));
                    addToast({
                      type: 'success',
                      title: `Copied ${iocClipboard.length} indicators`,
                      description: 'One per line, ready to paste into any tool.'
                    });
                  }}
                >
                  Copy all
                </button>
                  <button
                    type="button"
                    className="ui-btn ui-btn--primary"
                    onClick={() => {
                      copyTextToClipboard(iocClipboard.map((c) => c.value).join('\n'));
                      setClipboardOpen(false);
                      setToolQuery('ioc', '?page=lookup&tool=batch');
                      navigateTo('ioc', 'lookup', 'batch');
                      addToast({ type: 'info', title: 'Opened IOC batch lookup', description: 'The indicators were copied, ready to paste into the original batch interface.' });
                    }}
                  >
                    Open batch lookup
                  </button>
              </div>
            )}
          </aside>
        </>
      )}

      {/* =================================================================== */}
      {/* TOASTS                                                              */}
      {/* =================================================================== */}
      <div className="sc-toasts" aria-live="polite">
        {toasts.map((t) => {
          const borderColors = {
            success: 'var(--color-clean)',
            warning: 'var(--color-suspicious)',
            error: 'var(--color-malicious)',
            info: 'var(--color-info)'
          };
          return (
            <div key={t.id} className="sc-toast">
              <span className="sc-toast-mark" style={{ backgroundColor: borderColors[t.type] }} aria-hidden="true" />
              <div className="min-w-0 flex-1">
                <div className="sc-toast-title">{t.title}</div>
                {t.description && <div className="sc-toast-desc">{t.description}</div>}
              </div>
              <button
                type="button"
                className="sc-toast-x"
                onClick={() => setToasts((prev) => prev.filter((x) => x.id !== t.id))}
                aria-label="Dismiss"
              >
                <ShellIcon name="close" size={16} />
              </button>
            </div>
          );
        })}
      </div>

      {/* =================================================================== */}
      {/* UNIVERSAL NAVIGATOR (Ctrl+M / Cmd+M)                                */}
      {/* =================================================================== */}
      {commandPaletteOpen && (
        <div
          className="sc-modal-scrim"
          role="dialog"
          aria-modal="true"
          aria-label="Search and commands"
          onClick={() => setCommandPaletteOpen(false)}
        >
          <div className="sc-modal" style={{ maxWidth: 560 }} onClick={(e) => e.stopPropagation()}>
            <div className="sc-palette-input">
              <ShellIcon name="search" size={16} />
              <input
                type="text"
                autoFocus
                value={commandQuery}
                onChange={(e) => setCommandQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && commandItems.length > 0) {
                    commandItems[0].action();
                  }
                }}
                placeholder="Search tools, actions and settings"
                aria-label="Search tools, actions and settings"
              />
              <span className="sc-rail-kbd">
                <Kbd>Esc</Kbd>
              </span>
            </div>
            <div className="sc-palette-list">
              {commandGroups.length === 0 ? (
                <div className="ui-empty">
                  <span className="ui-body">Nothing matches “{commandQuery}”.</span>
                </div>
              ) : (
                commandGroups.map((group) => (
                  <div key={group.category}>
                    <div className="sc-palette-group">{group.category}</div>
                    {group.items.map((item, idx) => (
                      <button
                        key={`${group.category}-${idx}`}
                        type="button"
                        className="sc-palette-item"
                        data-active={idx === 0 && group.category === commandGroups[0].category ? 'true' : 'false'}
                        onClick={item.action}
                      >
                        <span>{item.label}</span>
                        {item.hotkey && <Kbd>{item.hotkey}</Kbd>}
                      </button>
                    ))}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
