// ==========================================================================
// shared workspace types and tool registry
// ==========================================================================
export type ToolId = 'ioc' | 'malware' | 'phishing' | 'events' | 'ruleforge';
export type PageRouteId = 'home' | 'dashboard' | 'detections' | 'settings' | ToolId;
export type VerdictType = 'clean' | 'suspicious' | 'malicious' | 'info' | 'unknown';

export interface IOCClipboardItem {
  id: string;
  value: string;
  type: 'ip' | 'domain' | 'hash' | 'url' | 'email' | 'registry' | 'path';
  sourceTool: ToolId;
  sourceContext: string;
  verdict: VerdictType;
  addedAt: string;
}

export interface ActivityItem {
  id: string;
  tool: ToolId;
  actionType: string;
  description: string;
  timestamp: string;
  verdict?: VerdictType;
  scoreText?: string;
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info';
  targetSubTab?: string;
  targetItemId?: string;
  unread?: boolean;
}

export interface ToastMessage {
  id: string;
  type: 'success' | 'warning' | 'error' | 'info';
  title: string;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
}

export interface ToolDefinition {
  id: ToolId;
  name: string;
  shortName: string;
  hotkey: string;
  tagline: string;
  description: string;
  accentFrom: string;
  accentTo: string;
  defaultPort: number;
  capabilities: string[];
  mainTabs: { id: string; label: string }[];
  subTabs: { id: string; label: string }[];
}

export const TOOLS_REGISTRY: Record<ToolId, ToolDefinition> = {
  ioc: {
    id: 'ioc',
    name: 'IOC Lookup Platform',
    shortName: 'IOC Lookup',
    hotkey: '1',
    tagline: 'Multi-provider indicator enrichment and investigation.',
    description: 'Correlate IPs, domains, hashes, URLs, wallets, phones, and breached credentials with consensus scoring and graph pivots.',
    accentFrom: '#f59e0b',
    accentTo: '#f97316',
    defaultPort: 7102,
    capabilities: [
      'Multi-provider consensus enrichment',
      'Broad indicator type detection',
      'Relationship graph and structured exports',
      'Batch enrichment and investigation notebooks'
    ],
    mainTabs: [{ id: 'overview', label: 'Overview' }, { id: 'lookup', label: 'Lookup' }],
    subTabs: [
      { id: 'lookup', label: 'Lookup' },
      { id: 'investigations', label: 'Investigations' },
      { id: 'batch', label: 'Batch' },
      { id: 'history', label: 'History' }
    ]
  },
  malware: {
    id: 'malware',
    name: 'Malware Analyzer',
    shortName: 'Malware',
    hotkey: '2',
    tagline: 'Static, threat-intelligence, sandbox, and YARA analysis.',
    description: 'Dissect suspicious PE, ELF, Mach-O, Office, PDF, and archive payloads using the bundled rules and optional cloud sandboxes.',
    accentFrom: '#6366f1',
    accentTo: '#a855f7',
    defaultPort: 7101,
    capabilities: [
      'Executable and document structure analysis',
      'Bundled YARA corpus and import flagging',
      'Optional multi-provider threat intelligence',
      'Interactive process and indicator reporting'
    ],
    mainTabs: [{ id: 'overview', label: 'Overview' }, { id: 'investigation', label: 'Investigation' }],
    subTabs: [
      { id: 'dashboard', label: 'Dashboard' },
      { id: 'static', label: 'Static Analysis' },
      { id: 'threatintel', label: 'Threat Intel' },
      { id: 'behavioral', label: 'Behavioral' },
      { id: 'iocs', label: 'IOCs' }
    ]
  },
  phishing: {
    id: 'phishing',
    name: 'Phishing Mail Detector',
    shortName: 'Phishing',
    hotkey: '3',
    tagline: 'Email authentication, routing, content, and attachment forensics.',
    description: 'Inspect spoofing, lookalike domains, MTA hops, credential-harvesting content, and weaponized attachments.',
    accentFrom: '#f43f5e',
    accentTo: '#ec4899',
    defaultPort: 7104,
    capabilities: [
      'Multi-stage forensic analysis pipeline',
      'SPF, DKIM, DMARC, ARC, and identity checks',
      'Hop-by-hop mail routing inspection',
      'URL, attachment, and safe preview analysis'
    ],
    mainTabs: [{ id: 'overview', label: 'Overview' }, { id: 'analysis', label: 'Analysis' }],
    subTabs: [
      { id: 'dashboard', label: 'Dashboard' },
      { id: 'sender-auth', label: 'Sender and Auth' },
      { id: 'artifacts', label: 'Artifacts' },
      { id: 'preview', label: 'Preview Mail' }
    ]
  },
  events: {
    id: 'events',
    name: 'Event Analyzer',
    shortName: 'Events',
    hotkey: '4',
    tagline: 'Windows EVTX ingestion, search, indicator extraction, and Sigma hunting.',
    description: 'Index EVTX log sets with SQLite search, structured filtering, indicator extraction, and Sigma matching.',
    accentFrom: '#0ea5e9',
    accentTo: '#06b6d4',
    defaultPort: 7103,
    capabilities: [
      'Multi-file EVTX ingestion',
      'Full-text search and structured filters',
      'Sigma detection and ATT&CK tagging',
      'Analyst notes and report exports'
    ],
    mainTabs: [{ id: 'overview', label: 'Overview' }, { id: 'investigation', label: 'Investigation' }],
    subTabs: [
      { id: 'events', label: 'Events' },
      { id: 'iocs', label: 'IOCs' },
      { id: 'sigma', label: 'Sigma' },
      { id: 'notes', label: 'Notes' }
    ]
  },
  ruleforge: {
    id: 'ruleforge',
    name: 'RuleForge',
    shortName: 'RuleForge',
    hotkey: '5',
    tagline: 'Cross-SIEM detection engineering with explicit translation refusals.',
    description: 'Author, translate, tune, and test detection logic across supported SIEM dialects using a deterministic evaluation engine.',
    accentFrom: '#14b8a6',
    accentTo: '#10b981',
    defaultPort: 7105,
    capabilities: [
      'Multiple SIEM query and rule dialects',
      'Visual pipeline and condition editing',
      'Three-valued sample evaluation',
      'Rule synthesis, linting, and history'
    ],
    mainTabs: [{ id: 'overview', label: 'Overview' }, { id: 'workshop', label: 'Workshop' }],
    subTabs: [
      { id: 'author', label: 'Author' },
      { id: 'tune', label: 'Tune' },
      { id: 'debug', label: 'Debug' },
      { id: 'understand', label: 'Understand' },
      { id: 'history', label: 'History' },
      { id: 'dialects', label: 'Dialects' }
    ]
  }
};
