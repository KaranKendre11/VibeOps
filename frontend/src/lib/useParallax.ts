import { useEffect } from 'react';
import { useMotionValue, useReducedMotion, useSpring, type MotionValue } from 'framer-motion';

export interface Parallax {
  x: MotionValue<number>;
  y: MotionValue<number>;
}

/**
 * Subtle pointer-driven parallax for hero/foreground layers.
 *
 * Tracks the cursor's position relative to the viewport centre and returns
 * spring-smoothed `x`/`y` MotionValues (in px) that drift a few pixels *opposite*
 * the pointer, so foreground content feels like it floats above the ambient
 * background. Apply them to a `motion.div` via `style={{ x, y }}`; use a larger
 * `strength` on nearer layers and a smaller one on farther layers for depth.
 *
 * No-op under `prefers-reduced-motion` (values stay pinned at 0).
 *
 * @param strength Maximum offset in px at the viewport edge. Default 12.
 */
export function useParallax(strength = 12): Parallax {
  const reduce = useReducedMotion();
  const xRaw = useMotionValue(0);
  const yRaw = useMotionValue(0);
  // Soft, slightly under-damped spring so movement trails the cursor rather than
  // snapping — reads as depth, not a cursor-follower.
  const spring = { stiffness: 120, damping: 22, mass: 0.5 };
  const x = useSpring(xRaw, spring);
  const y = useSpring(yRaw, spring);

  useEffect(() => {
    if (reduce) {
      xRaw.set(0);
      yRaw.set(0);
      return;
    }
    function onMove(e: PointerEvent) {
      // Normalised to -0.5..0.5 from the viewport centre, then inverted so layers
      // shift away from the pointer. ×2 maps the edges to ±strength px.
      const nx = e.clientX / window.innerWidth - 0.5;
      const ny = e.clientY / window.innerHeight - 0.5;
      xRaw.set(-nx * strength * 2);
      yRaw.set(-ny * strength * 2);
    }
    window.addEventListener('pointermove', onMove, { passive: true });
    return () => window.removeEventListener('pointermove', onMove);
  }, [reduce, strength, xRaw, yRaw]);

  return { x, y };
}
