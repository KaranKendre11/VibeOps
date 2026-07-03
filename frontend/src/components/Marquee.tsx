import { Fragment } from 'react';
import { cn } from '../lib/utils';

interface MarqueeProps {
  items: string[];
  className?: string;
}

/** Infinite horizontal marquee. The track is duplicated so the -50% translate loops seamlessly. */
export function Marquee({ items, className }: MarqueeProps) {
  return (
    <div
      className={cn(
        'group relative overflow-hidden border-y border-line py-3',
        '[mask-image:linear-gradient(90deg,transparent,#000_12%,#000_88%,transparent)]',
        className,
      )}
    >
      <div className="flex w-max animate-marquee gap-8 whitespace-nowrap group-hover:[animation-play-state:paused]">
        {[0, 1].map((copy) => (
          <Fragment key={copy}>
            {items.map((item, i) => (
              <span
                key={`${copy}-${i}`}
                className="flex items-center gap-8 font-mono text-xs uppercase tracking-[0.25em] text-fg-dim"
              >
                <span>{item}</span>
                <span className="text-accent">/</span>
              </span>
            ))}
          </Fragment>
        ))}
      </div>
    </div>
  );
}
