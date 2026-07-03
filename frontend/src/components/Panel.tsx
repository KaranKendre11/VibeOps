import type { HTMLAttributes, ReactNode } from 'react';
import { cn } from '../lib/utils';

type Tone = 'glass' | 'solid' | 'cyan';

interface PanelProps extends HTMLAttributes<HTMLDivElement> {
  /**
   * glass = frosted chrome (default); solid = near-opaque for dense content that
   * must stay crisp (code, logs, spec rows); cyan = accent-tinted glass.
   */
  tone?: Tone;
  /** Glass elevation tier (ignored for solid). */
  elevation?: 1 | 2 | 3;
  glow?: boolean;
  children: ReactNode;
}

const toneClass = (tone: Tone, elevation: 1 | 2 | 3): string => {
  if (tone === 'solid') return 'surface-solid';
  if (tone === 'cyan') return 'glass-cyan';
  return `glass-${elevation}`;
};

/** A bordered surface card — the base container for most content. */
export function Panel({
  tone = 'glass',
  elevation = 2,
  glow = false,
  className,
  children,
  ...rest
}: PanelProps) {
  return (
    <div
      className={cn('rounded-md', toneClass(tone, elevation), glow && 'shadow-glow-inset', className)}
      {...rest}
    >
      {children}
    </div>
  );
}

export function PanelHeader({
  title,
  subtitle,
  right,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  right?: ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-white/10 px-5 py-4">
      <div>
        <h3 className="font-mono text-xs uppercase tracking-[0.2em] text-accent">{title}</h3>
        {subtitle && <p className="mt-1 text-sm text-fg-dim">{subtitle}</p>}
      </div>
      {right}
    </div>
  );
}
