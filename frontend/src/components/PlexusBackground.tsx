import { useEffect, useRef } from 'react';
import { useReducedMotion } from 'framer-motion';

/**
 * PlexusBackground — an in-browser recreation of the classic "Plexus" look
 * (Rowbyte's After Effects plugin): a slowly drifting field of glowing points on
 * pure black, joined by thin lines whose opacity fades with distance, with a
 * pseudo-z depth (size + brightness parallax) and a subtle cursor "hub" that
 * connects and brightens nearby nodes.
 *
 * Rendered on a single devicePixelRatio-aware <canvas>, driven by rAF. Nodes and
 * links are drawn additively (`globalCompositeOperation = 'lighter'`) over a
 * transparent buffer so the black backdrop shows through and overlaps glow.
 * Respects prefers-reduced-motion: draws one static frame, no animation loop.
 */

interface Color {
  r: number;
  g: number;
  b: number;
}

// Magenta nebula palette: a light rose majority + the deeper accent pink.
// (Named CYAN/VIOLET for historical reasons; both are now magenta-family tones.)
const CYAN: Color = { r: 255, g: 158, b: 196 }; // light rose #ff9ec4
const VIOLET: Color = { r: 255, g: 77, b: 141 }; // accent magenta #ff4d8d
const VIOLET_RATIO = 0.42; // fraction of nodes rendered in the deeper accent pink

const LINK_DIST = 140; // px: max distance at which two nodes are joined
const POINTER_DIST = 190; // px: reach of the cursor "hub"
const BASE_LINE_ALPHA = 0.32; // scales all link opacities (additive blend)
const MAX_DPR = 2; // cap the backing store for perf on hi-dpi screens

interface Point {
  x: number;
  y: number;
  vx: number; // px/sec
  vy: number; // px/sec
  z: number; // 0 (far) .. 1 (near) — pseudo depth
  color: Color;
}

interface PlexusBackgroundProps {
  className?: string;
}

/** ~140 points at 1080p; clamped to the design range for any viewport. */
function targetCount(w: number, h: number): number {
  return Math.max(120, Math.min(160, Math.round((w * h) / 15000)));
}

function makePoint(w: number, h: number): Point {
  const z = Math.random();
  const speed = 8 + Math.random() * 14; // px/sec base
  const dir = Math.random() * Math.PI * 2;
  const parallax = 0.45 + z * 0.75; // nearer points drift a touch faster
  return {
    x: Math.random() * w,
    y: Math.random() * h,
    vx: Math.cos(dir) * speed * parallax,
    vy: Math.sin(dir) * speed * parallax,
    z,
    color: Math.random() < VIOLET_RATIO ? VIOLET : CYAN,
  };
}

/** Pre-render a soft radial glow sprite once so nodes are a single cheap drawImage. */
function makeGlowSprite(color: Color): HTMLCanvasElement {
  const size = 64;
  const c = document.createElement('canvas');
  c.width = size;
  c.height = size;
  const g = c.getContext('2d');
  if (!g) return c;
  const { r, g: gg, b } = color;
  const grad = g.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  grad.addColorStop(0, `rgba(${r},${gg},${b},1)`);
  grad.addColorStop(0.18, `rgba(${r},${gg},${b},0.85)`);
  grad.addColorStop(0.5, `rgba(${r},${gg},${b},0.16)`);
  grad.addColorStop(1, `rgba(${r},${gg},${b},0)`);
  g.fillStyle = grad;
  g.fillRect(0, 0, size, size);
  return c;
}

export function PlexusBackground({ className }: PlexusBackgroundProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const reduce = useReducedMotion();

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const cyanSprite = makeGlowSprite(CYAN);
    const violetSprite = makeGlowSprite(VIOLET);

    let width = 0;
    let height = 0;
    const points: Point[] = [];
    const pointer = { x: 0, y: 0, active: false };
    let rafId: number | null = null;
    let lastTime = 0;

    const resize = () => {
      const prevW = width;
      const prevH = height;
      width = canvas.clientWidth || window.innerWidth;
      height = canvas.clientHeight || window.innerHeight;
      const dpr = Math.min(MAX_DPR, window.devicePixelRatio || 1);
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0); // draw in CSS pixels

      const want = targetCount(width, height);
      if (points.length === 0) {
        for (let i = 0; i < want; i++) points.push(makePoint(width, height));
      } else {
        // Stretch the existing field into the new bounds, then rebalance density.
        const sx = prevW ? width / prevW : 1;
        const sy = prevH ? height / prevH : 1;
        for (const p of points) {
          p.x *= sx;
          p.y *= sy;
        }
        while (points.length < want) points.push(makePoint(width, height));
        while (points.length > want) points.pop();
      }

      if (reduce) render(); // keep the static frame correct across resizes
    };

    const render = () => {
      ctx.clearRect(0, 0, width, height);
      ctx.globalCompositeOperation = 'lighter';

      // --- links between nearby points ---
      const linkSq = LINK_DIST * LINK_DIST;
      for (let i = 0; i < points.length; i++) {
        const a = points[i];
        for (let j = i + 1; j < points.length; j++) {
          const b = points[j];
          const dx = a.x - b.x;
          const dy = a.y - b.y;
          const d2 = dx * dx + dy * dy;
          if (d2 > linkSq) continue;
          const d = Math.sqrt(d2);
          const depth = (a.z + b.z) * 0.5;
          const alpha = (1 - d / LINK_DIST) * BASE_LINE_ALPHA * (0.35 + depth * 0.65);
          if (alpha <= 0.004) continue;
          const r = Math.round((a.color.r + b.color.r) * 0.5);
          const g = Math.round((a.color.g + b.color.g) * 0.5);
          const bl = Math.round((a.color.b + b.color.b) * 0.5);
          ctx.strokeStyle = `rgba(${r},${g},${bl},${alpha})`;
          ctx.lineWidth = 0.6 + depth * 0.7;
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.stroke();
        }
      }

      // --- cursor hub: connect + brighten nodes near the pointer ---
      if (pointer.active) {
        const pSq = POINTER_DIST * POINTER_DIST;
        ctx.lineWidth = 0.8;
        for (const p of points) {
          const dx = p.x - pointer.x;
          const dy = p.y - pointer.y;
          const d2 = dx * dx + dy * dy;
          if (d2 > pSq) continue;
          const alpha = (1 - Math.sqrt(d2) / POINTER_DIST) * 0.5;
          ctx.strokeStyle = `rgba(${p.color.r},${p.color.g},${p.color.b},${alpha})`;
          ctx.beginPath();
          ctx.moveTo(pointer.x, pointer.y);
          ctx.lineTo(p.x, p.y);
          ctx.stroke();
        }
      }

      // --- glowing nodes ---
      const pSq = POINTER_DIST * POINTER_DIST;
      for (const p of points) {
        let near = 0;
        if (pointer.active) {
          const dx = p.x - pointer.x;
          const dy = p.y - pointer.y;
          const d2 = dx * dx + dy * dy;
          if (d2 < pSq) near = 1 - Math.sqrt(d2) / POINTER_DIST;
        }
        const glowR = 2.2 + p.z * 4 + near * 3;
        const alpha = Math.min(1, 0.28 + p.z * 0.55 + near * 0.4);
        ctx.globalAlpha = alpha;
        ctx.drawImage(
          p.color === VIOLET ? violetSprite : cyanSprite,
          p.x - glowR,
          p.y - glowR,
          glowR * 2,
          glowR * 2,
        );
      }

      ctx.globalAlpha = 1;
      ctx.globalCompositeOperation = 'source-over';
    };

    const loop = (now: number) => {
      const dt = lastTime ? Math.min(0.05, (now - lastTime) / 1000) : 0;
      lastTime = now;
      for (const p of points) {
        p.x += p.vx * dt;
        p.y += p.vy * dt;
        // Bounce at the edges — keeps the field on-screen without the "snap" that
        // wrapping would cause on the links crossing a seam.
        if (p.x < 0) {
          p.x = 0;
          p.vx = -p.vx;
        } else if (p.x > width) {
          p.x = width;
          p.vx = -p.vx;
        }
        if (p.y < 0) {
          p.y = 0;
          p.vy = -p.vy;
        } else if (p.y > height) {
          p.y = height;
          p.vy = -p.vy;
        }
      }
      render();
      rafId = requestAnimationFrame(loop);
    };

    const onPointerMove = (e: PointerEvent) => {
      pointer.x = e.clientX;
      pointer.y = e.clientY;
      pointer.active = true;
    };
    const onPointerLeave = () => {
      pointer.active = false;
    };

    resize();
    window.addEventListener('resize', resize);

    if (reduce) {
      render(); // one static frame; no loop, no pointer reactivity
    } else {
      window.addEventListener('pointermove', onPointerMove, { passive: true });
      window.addEventListener('blur', onPointerLeave);
      document.addEventListener('mouseleave', onPointerLeave);
      rafId = requestAnimationFrame(loop);
    }

    return () => {
      if (rafId != null) cancelAnimationFrame(rafId);
      window.removeEventListener('resize', resize);
      window.removeEventListener('pointermove', onPointerMove);
      window.removeEventListener('blur', onPointerLeave);
      document.removeEventListener('mouseleave', onPointerLeave);
    };
  }, [reduce]);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden
      className={className}
      style={{ display: 'block', width: '100%', height: '100%', willChange: 'transform' }}
    />
  );
}
