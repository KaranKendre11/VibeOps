import { motion } from 'framer-motion';
import type { ReactNode } from 'react';
import { maskItem } from '../lib/motion';
import { cn } from '../lib/utils';

interface MaskRevealProps {
  children: ReactNode;
  className?: string;
  /**
   * standalone (default) animates on mount — for dynamically appended lines
   * (streaming chat, log rows). Set false to inherit a parent stagger container.
   */
  standalone?: boolean;
}

/** A line/heading that wipes UP into place from an overflow-hidden mask. */
export function MaskReveal({ children, className, standalone = true }: MaskRevealProps) {
  return (
    <span className={cn('block overflow-hidden', className)}>
      <motion.span
        className="block will-change-transform"
        variants={maskItem}
        {...(standalone ? { initial: 'hidden', animate: 'show' } : {})}
      >
        {children}
      </motion.span>
    </span>
  );
}
