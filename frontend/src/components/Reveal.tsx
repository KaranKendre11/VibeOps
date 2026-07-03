import { motion } from 'framer-motion';
import type { ReactNode } from 'react';
import { revealContainer, revealItem } from '../lib/motion';

/** Orchestrates a staggered entrance for its <Reveal> children. */
export function RevealGroup({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <motion.div
      variants={revealContainer}
      initial="hidden"
      animate="show"
      className={className}
    >
      {children}
    </motion.div>
  );
}

/** A single panel/card that fades + rises + resolves from blur, in sequence. */
export function Reveal({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <motion.div variants={revealItem} className={className}>
      {children}
    </motion.div>
  );
}
