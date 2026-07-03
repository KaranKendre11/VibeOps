import { motion, useReducedMotion } from 'framer-motion';
import { cn } from '../lib/utils';
import { ScrambleReveal } from './scramble';

interface WordmarkProps {
  className?: string;
  /** Larger, animated treatment for the landing hero. */
  hero?: boolean;
}

export function Wordmark({ className, hero = false }: WordmarkProps) {
  const reduce = useReducedMotion();

  if (!hero) {
    // Small corner mark: a tracked, utilitarian sans lockup with an entrance scramble.
    return (
      <span className={cn('font-sans font-semibold tracking-[0.14em] text-fg', className)}>
        <ScrambleReveal text="VIBE" />
        <ScrambleReveal text="OPS" className="text-accent" delay={120} />
      </span>
    );
  }

  const letters = 'VIBEOPS'.split('');
  return (
    <motion.h1
      className={cn(
        'font-sans font-bold leading-none tracking-[0.06em]',
        'text-6xl sm:text-7xl md:text-8xl',
        className,
      )}
      initial={reduce ? false : { opacity: 0, scale: 0.94 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.6, ease: 'easeOut' }}
    >
      <span className={reduce ? '' : 'inline-block animate-breathe'}>
        {letters.map((ch, i) => (
          <motion.span
            key={i}
            className={i >= 4 ? 'text-accent' : 'text-fg'}
            initial={reduce ? false : { opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 + i * 0.05, duration: 0.4, ease: 'easeOut' }}
          >
            {ch}
          </motion.span>
        ))}
      </span>
    </motion.h1>
  );
}
