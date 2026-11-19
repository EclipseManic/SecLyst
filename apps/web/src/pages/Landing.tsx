// ==========================================================================
// the Overview page — the product's front page
// ==========================================================================
//
// The one screen that explains the platform, so it reads top to bottom in the
// order a person asks:
//
//   1. Page head      — where you are, and what this screen is for
//   2. The band       — what Seclyst is, drawn: the statement beside the one
//                       thread every tool hangs from, ending at the Command
//                       Center. The drawing is the navigation.
//   3. The figures    — four numbers, every one counted from real state
//   4. The five tools — all five at once, each as its own card: the question it
//                       answers, what it does, what it can do, how to open it
//   5. How a case moves — the three stages, drawn as one path
//   6. Lookup + activity — the two things you actually do from this page
//
// MOTION, AND WHY EACH ONE EXISTS
//
// Motion here is a statement about the product, never decoration:
//
//   * the thread's pulse runs down the spine, from the five tools into the
//     Command Center — the product's whole thesis, moving
//   * a case sweeps along the workflow ruler, one stage to the next
//   * the figures count up and their rules draw in, because a number you
//     watched arrive is a number you read
//   * each section arrives as you reach it, so the page has a reading order
//     instead of arriving all at once
//
// Every one of them is off under the shell's reduce-motion switch and under
// the OS preference, and none of them carries information that is only
// available in the animation: the reduced-motion page is the same page.
//
// Every string comes from TOOLS_REGISTRY or from live shell state. Nothing on
// this page is a second, hand-written copy of the product.
// ==========================================================================
import React from 'react';
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { TOOLS_REGISTRY } from '../data/workspace';
import type { ActivityItem, PageRouteId, ToolId } from '../data/workspace';
import { ToolIcon } from '../lib/icons';
import { Kbd, Modal } from '../ui/index';

export const TOUR_SLIDES = [
  {
    step: 1,
    title: 'Five tools, one workspace',
    badge: 'What Seclyst is',
    body: 'Seclyst gathers IOC Lookup, Malware Analyzer, Phishing Detector, Event Analyzer and RuleForge in one local workbench. Each tool keeps its own navigation, visual language, and workflow.'
  },
  {
    step: 2,
    title: 'Start in the Command Center',
    badge: 'Morning briefing',
    body: 'The Command Center is the one screen that spans all five tools: posture per tool, the findings that need triage, indicators several tools have seen, and one activity timeline. It is where a shift starts, not a replacement for the tools.'
  },
  {
    step: 3,
    title: 'The rail is the whole shell',
    badge: 'Navigation',
    body: 'The left rail holds navigation and every global control: search, activity, your account, the shared clipboard, settings, the theme and the collapse toggle. Tool screens get no shell header at all — they are whole applications, so the shell stays out of their way. Number keys and Ctrl+K still work.'
  },
  {
    step: 4,
    title: 'Where the data comes from',
    badge: 'Data',
    body: 'Seclyst starts all five copied backends on isolated loopback ports. Each tool frame talks to its own live engine and keeps the interface it ships with.'
  }
];

export const FirstRunTourModal: React.FC<{
  open: boolean;
  onClose: () => void;
  onNavigate: (page: PageRouteId, mainTab?: string, subTab?: string) => void;
}> = ({ open, onClose, onNavigate }) => {
  const [slideIdx, setSlideIdx] = useState(0);
  if (!open) return null;
  const slide = TOUR_SLIDES[slideIdx];

  return (
    <Modal
      open={open}
      title={`How this works (${slide.step} of ${TOUR_SLIDES.length})`}
      subtitle={slide.badge}
      onClose={onClose}
      maxWidth="max-w-lg"
    >
      <div className="space-y-4">
        <span className="ui-eyebrow">{slide.badge}</span>
        <h4 className="ui-h2">{slide.title}</h4>
        <p className="ui-body">{slide.body}</p>

        <div className="flex items-center gap-1.5 pt-1">
          {TOUR_SLIDES.map((_, i) => (
            <button
              key={i}
              type="button"
              onClick={() => setSlideIdx(i)}
              className="h-1.5 rounded-full cursor-pointer"
              style={{
                width: i === slideIdx ? '24px' : '8px',
                backgroundColor: i === slideIdx ? 'var(--accent-from)' : 'var(--color-border)'
              }}
              aria-label={`Go to slide ${i + 1}`}
            />
          ))}
        </div>

        <div className="flex items-center justify-between pt-4 border-t" style={{ borderColor: 'var(--color-border-subtle)' }}>
          <button type="button" onClick={onClose} className="ui-btn ui-btn--quiet ui-btn--sm">
            Close
          </button>
          <div className="flex items-center gap-2">
            {slideIdx > 0 && (
              <button type="button" onClick={() => setSlideIdx(slideIdx - 1)} className="ui-btn ui-btn--ghost ui-btn--sm">
                Back
              </button>
            )}
            {slideIdx < TOUR_SLIDES.length - 1 ? (
              <button type="button" onClick={() => setSlideIdx(slideIdx + 1)} className="ui-btn ui-btn--primary ui-btn--sm">
                Next
              </button>
            ) : (
              <button
                type="button"
                onClick={() => {
                  onClose();
                  onNavigate('dashboard');
                }}
                className="ui-btn ui-btn--primary ui-btn--sm"
              >
                Open Command Center
              </button>
            )}
          </div>
        </div>
      </div>
    </Modal>
  );
};

/* --------------------------------------------------------------------------
   Data

   Every string on this page comes from somewhere real. The tools are read from
   TOOLS_REGISTRY — the names, descriptions and capabilities the product already
   states — and the activity list is the shell's own feed, passed in. Nothing
   here is a second, hand-written copy of the product, which is how an Overview
   page ends up describing a tool differently from the tool itself.
   -------------------------------------------------------------------------- */

// The five tools, in the order an incident reaches them rather than the order
// the registry happens to define them.
const TOOL_ORDER: ToolId[] = ['ioc', 'malware', 'phishing', 'events', 'ruleforge'];

// The question each tool answers, in the words an analyst would actually use
// out loud. This is what makes the page scannable: a tool is a question you
// have, not a product name you have to remember.
const TOOL_QUESTIONS: Record<ToolId, string> = {
  malware: 'Is this file dangerous, and what does it do?',
  phishing: 'Is this email a fake, and where does it lead?',
  ioc: 'Have we seen this indicator before, and what is it?',
  events: 'Did any of this happen on our own machines?',
  ruleforge: 'How do I catch this the next time it happens?'
};

const WORKFLOW: { step: string; title: string; desc: string; tools: ToolId[] }[] = [
  {
    step: '01',
    title: 'Triage the artefact',
    desc: 'Drop in the file or the email. You get a verdict back, and the indicators it carries are pulled out with it.',
    tools: ['malware', 'phishing']
  },
  {
    step: '02',
    title: 'Enrich the indicator',
    desc: 'Those IPs, domains and hashes go straight into a lookup, so one indicator becomes a picture instead of a guess.',
    tools: ['ioc']
  },
  {
    step: '03',
    title: 'Hunt, then detect',
    desc: 'Search your own logs for the same behaviour, then write the rule that catches it before it happens again.',
    tools: ['events', 'ruleforge']
  }
];

// The three statements the workspace is built on, shown under the figures.
const TENETS: { num: string; title: string; body: string }[] = [
  {
    num: '01',
    title: 'Each tool stays itself',
    body: 'Every tool screen is that tool’s own interface, hosted unchanged. Its navigation, its wording and its results are the ones its own users already know.'
  },
  {
    num: '02',
    title: 'The shell is the thread',
    body: 'One rail to move between them, one activity feed, and one clipboard of indicators to carry from a scan, to a hunt, to a detection rule.'
  },
  {
    num: '03',
    title: 'Nothing is hidden',
    body: 'Health, stored-record counts and activity come from live engine endpoints. Offline engines stay visibly offline rather than falling back to fixtures.'
  }
];

// The dot on a feed row is the item's verdict, falling back to its severity.
// One mapping, so a red dot on the Overview means what a red dot means in the
// rail and in the Command Center.
const FEED_TONE: Record<string, string> = {
  malicious: 'malicious',
  suspicious: 'suspicious',
  clean: 'clean',
  info: 'info',
  unknown: 'info',
  critical: 'malicious',
  high: 'malicious',
  medium: 'suspicious',
  low: 'clean'
};

const feedTone = (item: ActivityItem) => FEED_TONE[item.verdict ?? item.severity] ?? 'info';

/* --------------------------------------------------------------------------
   Motion
   -------------------------------------------------------------------------- */

// The shell's own reduce-motion switch, and the OS preference behind it. Read
// at the moment an effect runs, because the switch is a live control.
const motionOff = () =>
  typeof document !== 'undefined' &&
  (document.querySelector('[data-reduce-motion="true"]') !== null ||
    (typeof window !== 'undefined' &&
      window.matchMedia?.('(prefers-reduced-motion: reduce)').matches === true));

/* Bring each section in as it is reached.

   The page scrolls inside .sc-scroll rather than the window, so that is the
   observer's root: measuring against the viewport would report a section as
   visible while it was still clipped by its own scroll container.

   Nothing here can hide content. A section starts visible and is only armed
   for the transition once the observer is known to be running, and anything
   already on screen is revealed in the same frame. If the observer is missing,
   or motion is off, every section is marked in and no transition happens. */
const useReveal = () => {
  useEffect(() => {
    const nodes = Array.from(document.querySelectorAll<HTMLElement>('[data-reveal]'));
    if (nodes.length === 0) return;

    const showAll = () => nodes.forEach((node) => node.setAttribute('data-in', 'true'));

    if (motionOff() || typeof IntersectionObserver === 'undefined') {
      showAll();
      return;
    }

    const root = document.querySelector<HTMLElement>('.sc-scroll');
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          entry.target.setAttribute('data-in', 'true');
          observer.unobserve(entry.target);
        });
      },
      // No negative bottom margin. Shrinking the root is what stops a section
      // that sits at the very bottom of the page — the shortcuts line, past
      // the page's own bottom padding — from ever counting as reached, and a
      // section that is never reached is a section that never appears.
      { root: root ?? null, rootMargin: '0px', threshold: 0 }
    );

    nodes.forEach((node) => observer.observe(node));

    // The observer's first callback reveals whatever is already on screen. If
    // that callback never arrives — a root that cannot be observed, an engine
    // quirk — the page would be left invisible, so this is the net: nothing
    // revealed at all means the observer is not working, and everything shows.
    const guard = window.setTimeout(() => {
      if (document.querySelector('[data-reveal][data-in="true"]') === null) showAll();
    }, 1200);

    return () => {
      window.clearTimeout(guard);
      observer.disconnect();
    };
  }, []);
};

// The page counts its own figures up once, on mount. It is a transform-free
// number animation, so it costs nothing to paint, and the app's reduce-motion
// switch turns it off along with the CSS.
const useCountUp = (target: number, duration = 820) => {
  const [value, setValue] = useState(0);

  useEffect(() => {
    if (target === 0 || motionOff()) {
      setValue(target);
      return;
    }
    let frame = 0;
    const started = performance.now();
    const tick = (now: number) => {
      const progress = Math.min(1, (now - started) / duration);
      setValue(Math.round(target * (1 - Math.pow(1 - progress, 3))));
      if (progress < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    // A figure left reading half its value is worse than no animation at all,
    // and requestAnimationFrame does not run in a backgrounded tab. This lands
    // the real number whatever the frames did.
    const settle = window.setTimeout(() => setValue(target), duration + 200);
    return () => {
      cancelAnimationFrame(frame);
      window.clearTimeout(settle);
    };
  }, [target, duration]);

  return value;
};

const Metric: React.FC<{ value: number; label: string; hint: string; index: number }> = ({
  value,
  label,
  hint,
  index
}) => {
  const shown = useCountUp(value);
  return (
    <div className="ui-metric" style={{ '--i': index } as React.CSSProperties}>
      <div className="ui-metric-value">{shown}</div>
      <div className="ui-metric-label">{label}</div>
      <div className="ui-metric-hint">{hint}</div>
    </div>
  );
};

/* --------------------------------------------------------------------------
   Component
   -------------------------------------------------------------------------- */

export const LandingPage: React.FC<{
  onNavigate: (page: PageRouteId, mainTab?: string, subTab?: string) => void;
  onOpenTour: () => void;
  onQuickIocLookup: (ioc: string) => void;
  onOpenSettings: () => void;
  /** The shell's own activity feed — the same list the rail and the Command Center show. */
  activityFeed: ActivityItem[];
  /** How many indicators are pinned in the shared clipboard right now. */
  clipboardCount: number;
}> = ({ onNavigate, onOpenTour, onQuickIocLookup, onOpenSettings, activityFeed, clipboardCount }) => {
  const [quickIocInput, setQuickIocInput] = useState('');
  const pageRef = useRef<HTMLDivElement>(null);
  useReveal();

  /* Arm the reveal before the browser's first paint.

     The CSS hides a section only while this attribute is present, which is
     what keeps the page visible by default: if the script never runs, nothing
     is hidden and the whole page is simply there. `data-js` is the marker the
     design gate recognises as "a script is running", and a layout effect lands
     it before paint, so a section is never shown and then hidden. With motion
     off the attribute is never set at all, and the page is the same page
     standing still. */
  useLayoutEffect(() => {
    if (!motionOff()) pageRef.current?.setAttribute('data-js', 'true');
  }, []);

  // Counted, not written down: these figures come from the registry and from
  // session state, so they cannot drift away from the product.
  const tools = TOOL_ORDER.map((id) => TOOLS_REGISTRY[id]);
  const capabilityCount = tools.reduce((total, tool) => total + tool.capabilities.length, 0);
  const viewCount = tools.reduce((total, tool) => total + tool.subTabs.length, 0);
  const feed = activityFeed.slice(0, 5);

  const submitQuickLookup = () => {
    const value = quickIocInput.trim();
    if (value) onQuickIocLookup(value);
  };

  return (
    <div className="sc-page" ref={pageRef}>
      {/* ================================================================= */}
      {/* THE HERO — the statement, and the product it describes, drawn      */}
      {/* ================================================================= */}
      <section className="ov-hero" aria-labelledby="ov-hero-title">
        <div className="ov-field" aria-hidden="true" />

        <div className="ov-hero-main">
          <div className="sc-crumbs">
            Seclyst <span className="sc-crumbs-sep">/</span> Overview
          </div>
          <h1 className="ov-hero-title" id="ov-hero-title">
            Five security tools. One shared thread.
          </h1>
          <p className="ov-hero-lead">
            Keep each original interface while Seclyst connects the work around them.
          </p>
          <div className="ov-hero-actions">
            <button
              type="button"
              className="ui-btn ui-btn--primary"
              onClick={() => onNavigate('dashboard')}
            >
              Open Command Center
            </button>
            <button type="button" className="ui-btn ui-btn--ghost" onClick={onOpenTour}>
              How this works
            </button>
          </div>
          <p className="ov-hero-trust">
            <span>One local workspace</span>
            <span className="ui-sep" aria-hidden="true" />
            <span>{tools.length} tools</span>
            <span className="ui-sep" aria-hidden="true" />
            <span>One activity feed</span>
            <span className="ui-sep" aria-hidden="true" />
            <span>One clipboard</span>
          </p>
        </div>

        {/* The product, drawn. A picture of the Command Center's posture
            ledger, fed from the same registry the rest of the page reads, so
            the shot cannot describe the platform differently from the page. */}
        <div className="ov-hero-visual" aria-hidden="true">
          <div className="ov-shot">
            <div className="ov-shot-bar">
              <span className="ov-shot-dots">
                <span className="ov-shot-dot" />
                <span className="ov-shot-dot" />
                <span className="ov-shot-dot" />
              </span>
              <span className="ov-shot-title">Command Center</span>
              <span className="ov-shot-tag">{capabilityCount} capabilities</span>
            </div>
            <div className="ov-shot-body">
              <div className="ov-shot-head">
                <span>Tool</span>
                <span>Views</span>
              </div>
              {tools.map((tool) => (
                <div className="ov-shot-row" key={tool.id} data-tool={tool.id}>
                  <span className="ov-shot-tool">
                    <span className="ui-tool-mark">
                      <ToolIcon tool={tool.id} size={14} />
                    </span>
                    <span className="ov-shot-name">{tool.shortName}</span>
                  </span>
                  <span className="ov-shot-count">{tool.subTabs.length} views</span>
                </div>
              ))}
              <p className="ov-shot-foot">{tools.length} tools, one timeline, one clipboard</p>
            </div>
          </div>
        </div>
      </section>

      {/* ================================================================= */}
      {/* FIGURES — counted from real state, never written into the markup   */}
      {/* ================================================================= */}
      <section className="ov-figures" data-reveal aria-labelledby="ov-figures-title">
        <div className="ov-block-head">
          <h2 className="ov-block-title" id="ov-figures-title">
            The workspace in numbers
          </h2>
          <p className="ov-block-sub">
            Read from the tool registry and from this session. None of these is typed into the page.
          </p>
        </div>
        <div className="ui-metrics">
          <Metric index={0} value={tools.length} label="Tools in the workspace" hint="each with its own interface" />
          <Metric index={1} value={capabilityCount} label="Documented capabilities" hint="stated by the tools themselves" />
          <Metric index={2} value={viewCount} label="Views inside the tools" hint="their own sections, unchanged" />
          <Metric index={3} value={clipboardCount} label="Indicators in the clipboard" hint="shared by every tool" />
        </div>
      </section>

      {/* ================================================================= */}
      {/* THE PRINCIPLES — three statements the workspace is built on        */}
      {/* ================================================================= */}
      <section className="ov-principles" data-reveal aria-labelledby="ov-principles-title">
        <h2 className="ov-principles-title" id="ov-principles-title">
          How the workspace is built
        </h2>
        <ol className="ov-tenets">
          {TENETS.map((tenet, index) => (
            <li
              className="ov-tenet"
              key={tenet.num}
              style={{ '--i': index } as React.CSSProperties}
            >
              <span className="ov-tenet-num sc-mono">{tenet.num}</span>
              <div className="ov-tenet-title">{tenet.title}</div>
              <p className="ov-tenet-body">{tenet.body}</p>
            </li>
          ))}
        </ol>
      </section>

      {/* ================================================================= */}
      {/* THE FIVE TOOLS — the centrepiece: all five, side by side           */}
      {/* ================================================================= */}
      <section className="ov-block" aria-labelledby="ov-tools-title">
        <div className="ov-block-head">
          <h2 className="ov-block-title" id="ov-tools-title">
            The five tools
          </h2>
          <p className="ov-block-sub">
            What each one answers, what it does, and what it can do. Read before you open it.
          </p>
        </div>

        <div className="ov-tools">
          {tools.map((tool, index) => (
            <article
              className="ov-tool-card"
              key={tool.id}
              data-tool={tool.id}
              data-reveal
              style={{ '--i': index } as React.CSSProperties}
            >
              <div className="ov-tool-card-head">
                <span className="ui-tool-mark">
                  <ToolIcon tool={tool.id} size={18} />
                </span>
                <h3 className="ov-tool-card-name">{tool.name}</h3>
                <Kbd>{tool.hotkey}</Kbd>
              </div>

              <p className="ov-tool-tagline">{tool.tagline}</p>
              <p className="ov-tool-question">{TOOL_QUESTIONS[tool.id]}</p>
              <p className="ov-tool-desc">{tool.description}</p>

              <ul className="ov-tool-caps">
                {tool.capabilities.map((capability) => (
                  <li key={capability} className="ov-tool-cap">
                    {capability}
                  </li>
                ))}
              </ul>

              <div className="ov-tool-card-foot">
                <span className="ov-tool-sections">{tool.subTabs.length} views inside</span>
                <button
                  type="button"
                  className="ui-btn ui-btn--ghost ui-btn--sm"
                  onClick={() => onNavigate(tool.id)}
                >
                  Open {tool.shortName}
                </button>
              </div>
            </article>
          ))}
        </div>
      </section>

      {/* ================================================================= */}
      {/* WORKFLOW — the three stages, drawn as one path                    */}
      {/* ================================================================= */}
      <section className="ov-block" data-reveal aria-labelledby="ov-flow-title">
        <div className="ov-block-head">
          <h2 className="ov-block-title" id="ov-flow-title">
            From alert to detection rule
          </h2>
          <p className="ov-block-sub">Three stages, five tools, nothing re-typed between them.</p>
        </div>

        <div className="ov-flow">
          <span className="ov-flow-sweep" aria-hidden="true" />
          {WORKFLOW.map((stage, index) => (
            <div
              key={stage.step}
              className="ov-flow-stage"
              style={{ '--i': index } as React.CSSProperties}
            >
              <div className="ov-flow-node sc-mono" aria-hidden="true">
                {stage.step}
              </div>
              <h3 className="ov-flow-title">{stage.title}</h3>
              <p className="ov-flow-desc">{stage.desc}</p>
              <div className="ov-flow-tools">
                {stage.tools.map((tid) => (
                  <button
                    key={tid}
                    type="button"
                    className="ov-flow-tool"
                    data-tool={tid}
                    onClick={() => onNavigate(tid)}
                  >
                    <ToolIcon tool={tid} size={12} />
                    {TOOLS_REGISTRY[tid].shortName}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ================================================================= */}
      {/* LOOKUP + ACTIVITY — the two things you actually do from here       */}
      {/* ================================================================= */}
      <div className="ov-actions" data-reveal>
        <section className="ov-lookup" aria-labelledby="ov-lookup-title">
          <div className="ui-card-head">
            <div>
              <h2 className="ui-card-title" id="ov-lookup-title">
                Look up an indicator
              </h2>
              <div className="ui-card-sub">An IP, domain, URL, hash, wallet or email address</div>
            </div>
          </div>
          <div className="ov-lookup-body">
            <p className="ov-lookup-desc">
              This hands the indicator to IOC Lookup and runs it against its intel sources, so it
              arrives at a result rather than at a blank form.
            </p>
            <div className="ov-lookup-form">
              <input
                type="text"
                value={quickIocInput}
                onChange={(e) => setQuickIocInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') submitQuickLookup();
                }}
                placeholder="198.51.100.45, evil-login-portal.com, a4f8d91c…"
                aria-label="Indicator to look up"
                className="ui-input sc-mono"
              />
              <button
                type="button"
                className="ui-btn ui-btn--primary"
                onClick={submitQuickLookup}
                disabled={!quickIocInput.trim()}
              >
                Look it up
              </button>
            </div>
            <p className="ov-lookup-hint">Opens IOC Lookup with the result already running.</p>
          </div>
        </section>

        <section className="ov-activity" aria-labelledby="ov-activity-title">
          <div className="ui-card-head">
            <div>
              <h2 className="ui-card-title" id="ov-activity-title">
                Recent activity
              </h2>
              <div className="ui-card-sub">The same feed the rail and the Command Center show</div>
            </div>
            <button
              type="button"
              className="ui-btn ui-btn--quiet ui-btn--sm"
              onClick={() => onNavigate('dashboard')}
            >
              Open timeline
            </button>
          </div>

          <div className="ov-activity-list">
            {feed.length === 0 ? (
              <div className="ui-empty">
                <span className="ui-body">Nothing has run yet.</span>
              </div>
            ) : (
              feed.map((item) => {
                const definition = TOOLS_REGISTRY[item.tool];
                return (
                  <button
                    key={item.id}
                    type="button"
                    className="ov-activity-item"
                    title={item.actionType}
                    onClick={() =>
                      onNavigate(
                        item.tool,
                        definition.mainTabs[1].id,
                        item.targetSubTab || definition.subTabs[0].id
                      )
                    }
                  >
                    <span className={`ov-activity-dot ov-activity-dot--${feedTone(item)}`} aria-hidden="true" />
                    <span className="ov-activity-text">
                      <span className="ov-activity-title">{item.description}</span>
                      <span className="ov-activity-meta">
                        <span>{definition.shortName}</span>
                        <span className="ui-sep" aria-hidden="true" />
                        <span className="sc-mono">{item.timestamp}</span>
                      </span>
                    </span>
                  </button>
                );
              })
            )}
          </div>
        </section>
      </div>

      {/* ================================================================= */}
      {/* SHORTCUTS — one quiet line, not a card of its own                  */}
      {/* ================================================================= */}
      <section className="ov-shortcuts" data-reveal aria-label="Keyboard shortcuts">
        <h2 className="ov-shortcuts-label">Shortcuts</h2>
        <span className="ov-shortcut">
          <Kbd>0</Kbd> Overview
        </span>
        <span className="ov-shortcut">
          <Kbd>1</Kbd> to <Kbd>5</Kbd> Tools
        </span>
        <span className="ov-shortcut">
          <Kbd>Ctrl</Kbd> <Kbd>K</Kbd> Search
        </span>
        <span className="ov-shortcut">
          <Kbd>?</Kbd> Tour
        </span>
        <button type="button" className="ov-shortcut-link" onClick={onOpenSettings}>
          Connection settings
        </button>
      </section>
    </div>
  );
};
