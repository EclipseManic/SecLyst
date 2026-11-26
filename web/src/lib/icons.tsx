// ==========================================================================
// the inline icon set
// ==========================================================================
import React from 'react';
import type { ToolId } from '../data/workspace';

export const BrandShieldIcon: React.FC<{ className?: string; size?: number }> = ({ className = '', size = 24 }) => (
  <svg width={size} height={size} viewBox="0 0 32 32" fill="none" className={className} aria-hidden="true">
    <defs>
      <linearGradient id="scShieldGrad" x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="var(--accent-from)" />
        <stop offset="100%" stopColor="var(--accent-to)" />
      </linearGradient>
    </defs>
    <path d="M16 2.5L4.5 7.2V15.8C4.5 23.1 9.4 29.4 16 31.5C22.6 29.4 27.5 23.1 27.5 15.8V7.2L16 2.5Z" stroke="url(#scShieldGrad)" strokeWidth="2.2" fill="rgba(99,102,241,0.10)" />
    {/* 5 converging streams into central nexus */}
    <path d="M8 10L16 16M24 10L16 16M7 18L16 16M25 18L16 16M16 26L16 16" stroke="url(#scShieldGrad)" strokeWidth="1.7" strokeLinecap="round" />
    <circle cx="16" cy="16" r="3.2" fill="url(#scShieldGrad)" />
  </svg>
);

export const ToolIcon: React.FC<{ tool: ToolId | 'home' | 'dashboard'; size?: number; className?: string }> = ({ tool, size = 18, className = '' }) => {
  switch (tool) {
    case 'malware':
      // Microscope / Binary Dissection Icon
      return (
        <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
          <path d="M6 18h8" />
          <path d="M3 21h18" />
          <path d="M14 21v-4a2 2 0 0 0-2-2H9" />
          <path d="M14 7l-3.5 3.5" />
          <rect x="12" y="2" width="6" height="6" rx="1" transform="rotate(45 15 5)" />
          <path d="M14 11a5 5 0 0 1 5 5v2" />
        </svg>
      );
    case 'ioc':
      // Magnifying Glass with Crosshair Icon
      return (
        <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
          <circle cx="10.5" cy="10.5" r="7.5" />
          <path d="M21 21l-5.2-5.2" />
          <path d="M10.5 6.5v8M6.5 10.5h8" />
          <circle cx="10.5" cy="10.5" r="2" />
        </svg>
      );
    case 'events':
      // Log / Timeline Scroll Icon
      return (
        <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
          <rect x="3" y="3" width="18" height="18" rx="2.5" />
          <path d="M7 8h3M13 8h4M7 12h2M12 12h5M7 16h4M14 16h3" />
        </svg>
      );
    case 'phishing':
      // Email Shield / Hook-Catch Icon
      return (
        <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
          <rect x="2" y="4" width="20" height="16" rx="2.5" />
          <path d="M22 7l-10 6L2 7" />
          <path d="M16 15a2.5 2.5 0 0 0 5 0v-3" />
        </svg>
      );
    case 'ruleforge':
      // Anvil / Hammer-on-Code Icon
      return (
        <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
          <path d="M14.5 4.5l5 5-9.5 9.5-5-5 9.5-9.5z" />
          <path d="M4 20h16" />
          <path d="M12 3L9 6" />
          <path d="M18 12l3-3" />
        </svg>
      );
    case 'dashboard':
      return (
        <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
          <rect x="3" y="3" width="7" height="9" rx="1.5" />
          <rect x="14" y="3" width="7" height="5" rx="1.5" />
          <rect x="14" y="12" width="7" height="9" rx="1.5" />
          <rect x="3" y="16" width="7" height="5" rx="1.5" />
        </svg>
      );
    default:
      return <BrandShieldIcon size={size} className={className} />;
  }
};
/* --------------------------------------------------------------------------
   The shell's own icon set.

   Every global control in the rail uses one of these instead of a text glyph.
   The glyphs that were here before — a gear, a sun, a magnifier, a clipboard
   — were characters, so they rendered at whatever weight and baseline the
   system font decided, they read as emoji on some machines, and none of them
   could take the rail's ink colour. One set, one stroke weight, one geometry.
   -------------------------------------------------------------------------- */

export type ShellIconName =
  | 'search'
  | 'activity'
  | 'clipboard'
  | 'settings'
  | 'sun'
  | 'moon'
  | 'panel'
  | 'close'
  | 'more'
  | 'check'
  | 'alert';

export const ShellIcon: React.FC<{ name: ShellIconName; size?: number; className?: string }> = ({
  name,
  size = 17,
  className = ''
}) => {
  const common = {
    width: size,
    height: size,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.7,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    className,
    'aria-hidden': true
  };

  switch (name) {
    case 'search':
      return (
        <svg {...common} aria-hidden="true">
          <circle cx="10.5" cy="10.5" r="6.5" />
          <path d="M20 20l-4.7-4.7" />
        </svg>
      );
    case 'activity':
      return (
        <svg {...common} aria-hidden="true">
          <path d="M3 12h3.5l2.5-6 3.5 12 2.5-6H21" />
        </svg>
      );
    case 'clipboard':
      return (
        <svg {...common} aria-hidden="true">
          <rect x="5" y="4" width="14" height="17" rx="2" />
          <path d="M9 4V2.8h6V4" />
          <path d="M9 10h6M9 14h4" />
        </svg>
      );
    case 'settings':
      return (
        <svg {...common} aria-hidden="true">
          <circle cx="12" cy="12" r="3.2" />
          <path d="M12 2.6v2.6M12 18.8v2.6M4.4 4.4l1.9 1.9M17.7 17.7l1.9 1.9M2.6 12h2.6M18.8 12h2.6M4.4 19.6l1.9-1.9M17.7 6.3l1.9-1.9" />
        </svg>
      );
    case 'sun':
      return (
        <svg {...common} aria-hidden="true">
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.2 5.2l1.4 1.4M17.4 17.4l1.4 1.4M5.2 18.8l1.4-1.4M17.4 6.6l1.4-1.4" />
        </svg>
      );
    case 'moon':
      return (
        <svg {...common} aria-hidden="true">
          <path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5z" />
        </svg>
      );
    case 'panel':
      return (
        <svg {...common} aria-hidden="true">
          <rect x="3" y="4" width="18" height="16" rx="2" />
          <path d="M9 4v16" />
        </svg>
      );
    case 'close':
      return (
        <svg {...common} aria-hidden="true">
          <path d="M6 6l12 12M18 6L6 18" />
        </svg>
      );
    case 'more':
      return (
        <svg {...common} aria-hidden="true">
          <circle cx="5.5" cy="12" r="1.2" fill="currentColor" stroke="none" />
          <circle cx="12" cy="12" r="1.2" fill="currentColor" stroke="none" />
          <circle cx="18.5" cy="12" r="1.2" fill="currentColor" stroke="none" />
        </svg>
      );
    case 'check':
      return (
        <svg {...common} aria-hidden="true">
          <path d="M4.5 12.5l5 5 10-11" />
        </svg>
      );
    case 'alert':
      return (
        <svg {...common} aria-hidden="true">
          <path d="M12 4.5l8.5 15h-17z" />
          <path d="M12 10v4.5M12 17.2v.3" />
        </svg>
      );
    default:
      return null;
  }
};
