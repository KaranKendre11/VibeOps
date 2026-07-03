import { cn } from '../lib/utils';

interface BrandIconProps {
  /** Rendered square size in px. */
  size?: number;
  className?: string;
}

/**
 * The VibeOps brand mark — the neon-goggled alpaca app icon (served from
 * `/icon.png`). Rendered as a rounded "squircle" chip so it reads as a logo at
 * any size.
 */
export function BrandIcon({ size = 24, className }: BrandIconProps) {
  return (
    <img
      src="/icon.png"
      alt="VibeOps"
      width={size}
      height={size}
      style={{ width: size, height: size }}
      className={cn('shrink-0 object-contain', className)}
    />
  );
}
