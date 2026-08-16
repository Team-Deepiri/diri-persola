import type { ReactNode } from 'react';

/** Inline nav icons — stroke SVGs, no emoji. */

type IconProps = { className?: string; size?: number };

function Svg({
  children,
  className,
  size = 18,
}: IconProps & { children: ReactNode }) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      {children}
    </svg>
  );
}

export function IconSliders(props: IconProps) {
  return (
    <Svg {...props}>
      <line x1="4" y1="21" x2="4" y2="14" />
      <line x1="4" y1="10" x2="4" y2="3" />
      <line x1="12" y1="21" x2="12" y2="12" />
      <line x1="12" y1="8" x2="12" y2="3" />
      <line x1="20" y1="21" x2="20" y2="16" />
      <line x1="20" y1="12" x2="20" y2="3" />
      <line x1="1" y1="14" x2="7" y2="14" />
      <line x1="9" y1="8" x2="15" y2="8" />
      <line x1="17" y1="16" x2="23" y2="16" />
    </Svg>
  );
}

export function IconUser(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </Svg>
  );
}

export function IconBot(props: IconProps) {
  return (
    <Svg {...props}>
      <rect x="4" y="8" width="16" height="12" rx="2" />
      <path d="M12 2v4" />
      <circle cx="9" cy="14" r="1.25" fill="currentColor" stroke="none" />
      <circle cx="15" cy="14" r="1.25" fill="currentColor" stroke="none" />
      <path d="M8 20v2M16 20v2" />
    </Svg>
  );
}

export function IconSearch(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.5-3.5" />
    </Svg>
  );
}

export function IconBlend(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="9" cy="10" r="5.5" />
      <circle cx="15" cy="14" r="5.5" />
    </Svg>
  );
}

export function IconUsers(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
      <path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </Svg>
  );
}

export function IconCity(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M3 21h18" />
      <path d="M5 21V8l5-3v16" />
      <path d="M14 21V5l5 3v13" />
      <path d="M9 9h.01M9 13h.01M9 17h.01M17 12h.01M17 16h.01" />
    </Svg>
  );
}

export function IconWorkqueue(props: IconProps) {
  return (
    <Svg {...props}>
      <rect x="3" y="4" width="18" height="5" rx="1.5" />
      <rect x="3" y="13" width="18" height="5" rx="1.5" />
      <path d="M7 6.5h.01M7 15.5h.01M11 6.5h4M11 15.5h4" />
    </Svg>
  );
}

export function IconSettings(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="12" r="3" />
      <path d="M12 1v2.5M12 20.5V23M4.22 4.22l1.77 1.77M17.99 17.99l1.77 1.77M1 12h2.5M20.5 12H23M4.22 19.78l1.77-1.77M17.99 6.01l1.77-1.77" />
    </Svg>
  );
}
