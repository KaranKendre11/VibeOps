import { forwardRef, useState } from 'react';
import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { useReducedMotion } from 'framer-motion';
import { cn } from '../lib/utils';
import { ScrambleText } from './scramble';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'glass';
type Size = 'sm' | 'md' | 'lg';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  /** Scramble the label on hover. Defaults on for primary; opt in/out anywhere. */
  roll?: boolean;
  children: ReactNode;
}

const base =
  'inline-flex items-center justify-center gap-2 rounded-pill font-medium tracking-wide ' +
  'transition-all duration-300 ease-quint select-none whitespace-nowrap ' +
  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 ' +
  'focus-visible:ring-offset-bg disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:translate-y-0';

const variants: Record<Variant, string> = {
  // White pill with black text (matches the landing "Try it" CTA); the magenta
  // accent shows only as a soft glow on hover, not as the fill.
  primary:
    'bg-white text-black hover:-translate-y-0.5 hover:bg-[#ececf0] hover:shadow-glow-lg ' +
    'disabled:shadow-none active:translate-y-0',
  secondary:
    'bg-transparent text-accent border border-accent/60 hover:-translate-y-0.5 ' +
    'hover:border-accent hover:shadow-glow-sm active:translate-y-0',
  ghost:
    'bg-transparent text-fg-muted border border-line hover:text-fg hover:border-white/40 ' +
    'hover:-translate-y-0.5 active:translate-y-0',
  danger:
    'bg-transparent text-red-300 border border-red-500/50 hover:border-red-400 ' +
    'hover:bg-red-500/10 hover:-translate-y-0.5 active:translate-y-0',
  // Heavy liquid-glass CTA for cinematic hero moments (white text over the field).
  glass:
    'liquid-glass-strong text-fg hover:-translate-y-0.5 hover:text-white active:translate-y-0',
};

const sizes: Record<Size, string> = {
  sm: 'text-xs px-4 py-2',
  md: 'text-sm px-6 py-2.5',
  lg: 'text-base px-8 py-3.5',
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'primary', size = 'md', loading = false, roll, disabled, className, children, ...rest },
  ref,
) {
  const reduce = useReducedMotion();
  const [hover, setHover] = useState(false);
  // Scramble on hover for every variant by default (consistent motif); opt out with roll={false}.
  const useScramble = (roll ?? true) && typeof children === 'string' && !loading && !reduce;
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={cn(base, variants[variant], sizes[size], className)}
      {...rest}
      onMouseEnter={(e) => {
        rest.onMouseEnter?.(e);
        if (useScramble) setHover(true);
      }}
      onMouseLeave={(e) => {
        rest.onMouseLeave?.(e);
        if (useScramble) setHover(false);
      }}
    >
      {loading && (
        <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent" />
      )}
      {useScramble ? <ScrambleText text={children as string} isHovered={hover} /> : children}
    </button>
  );
});
