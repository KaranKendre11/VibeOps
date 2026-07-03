import type { Variants } from 'framer-motion';

// Signature easing — easeOutQuint. Restrained ease-out = "precision instrument".
export const QUINT = [0.23, 1, 0.32, 1] as const;

// Section/panel entrance: fade + slight rise, staggered by a parent container.
export const revealContainer: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.07, delayChildren: 0.03 } },
};

export const revealItem: Variants = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.6, ease: QUINT } },
};

// Masked line reveal: the inner line wipes UP from an overflow-hidden mask.
export const maskItem: Variants = {
  hidden: { y: '115%' },
  show: { y: '0%', transition: { duration: 0.7, ease: QUINT } },
};

// Screen-to-screen: cross-fade + slight scale with the signature ease.
export const screenTransition = {
  initial: { opacity: 0, scale: 0.985 },
  animate: { opacity: 1, scale: 1 },
  exit: { opacity: 0, scale: 1.006 },
  transition: { duration: 0.5, ease: QUINT },
};
