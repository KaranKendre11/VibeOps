import { useEffect, useRef, useState } from 'react';
import { useReducedMotion } from 'framer-motion';

const CHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()_+~|}{[]:;?><';

function randChar(): string {
  return CHARS[Math.floor(Math.random() * CHARS.length)];
}

interface ScrambleInProps {
  text: string;
  /** ms to wait after `triggered` before the reveal starts. */
  delay?: number;
  /** Flip to true to run the entrance reveal. */
  triggered: boolean;
  className?: string;
}

/**
 * Entrance reveal: once `triggered` (after `delay`), characters lock in
 * left-to-right at ~0.5 chars/frame on a 25ms interval. Characters just ahead of
 * the reveal cursor flicker through random glyphs; ones further out are blank.
 * Spaces always render as spaces. Before triggering, renders a non-breaking space
 * to hold the line's height.
 */
export function ScrambleIn({ text, delay = 0, triggered, className }: ScrambleInProps) {
  const [display, setDisplay] = useState<string>('');
  const [started, setStarted] = useState(false);

  useEffect(() => {
    if (!triggered) return;
    let interval: ReturnType<typeof setInterval> | null = null;
    const timer = setTimeout(() => {
      setStarted(true);
      let revealed = 0; // fractional reveal cursor
      interval = setInterval(() => {
        revealed += 0.5;
        const cursor = Math.floor(revealed);
        let out = '';
        for (let i = 0; i < text.length; i++) {
          if (text[i] === ' ') {
            out += ' ';
          } else if (i < cursor) {
            out += text[i];
          } else if (i < cursor + 3) {
            out += randChar();
          }
          // beyond cursor + 3 → nothing (blank)
        }
        setDisplay(out);
        if (cursor >= text.length) {
          setDisplay(text);
          if (interval) clearInterval(interval);
        }
      }, 25);
    }, delay);

    return () => {
      clearTimeout(timer);
      if (interval) clearInterval(interval);
    };
  }, [triggered, delay, text]);

  if (!triggered || !started) {
    return (
      <span className={className} aria-label={text}>
        &nbsp;
      </span>
    );
  }
  return (
    <span className={className} aria-label={text}>
      {display}
    </span>
  );
}

interface ScrambleTextProps {
  text: string;
  isHovered: boolean;
  className?: string;
}

/**
 * Hover-driven scramble: on hover, every character flickers through random
 * glyphs, then resolves left-to-right (4 frames per character, 25ms interval).
 * On unhover it snaps straight back to the original text.
 */
export function ScrambleText({ text, isHovered, className }: ScrambleTextProps) {
  const [display, setDisplay] = useState(text);
  const frame = useRef(0);

  useEffect(() => {
    if (!isHovered) {
      setDisplay(text);
      return;
    }
    frame.current = 0;
    const interval = setInterval(() => {
      frame.current += 1;
      const revealed = Math.floor(frame.current / 4);
      let out = '';
      for (let i = 0; i < text.length; i++) {
        if (text[i] === ' ') out += ' ';
        else if (i < revealed) out += text[i];
        else out += randChar();
      }
      setDisplay(out);
      if (revealed >= text.length) {
        setDisplay(text);
        clearInterval(interval);
      }
    }, 25);
    return () => clearInterval(interval);
  }, [isHovered, text]);

  return <span className={className}>{display}</span>;
}

// ---------------------------------------------------------------------------
// Ergonomic app-facing wrappers
// ---------------------------------------------------------------------------

interface ScrambleRevealProps {
  text: string;
  delay?: number;
  className?: string;
}

/**
 * Self-triggering entrance scramble for headings and tracked-out labels. Fires
 * once on mount (re-fires if `text` changes). Under prefers-reduced-motion it
 * renders the final text immediately with no animation.
 */
export function ScrambleReveal({ text, delay = 0, className }: ScrambleRevealProps) {
  const reduce = useReducedMotion();
  const [triggered, setTriggered] = useState(false);

  useEffect(() => {
    if (reduce) return;
    setTriggered(false);
    const id = requestAnimationFrame(() => setTriggered(true));
    return () => cancelAnimationFrame(id);
  }, [reduce, text]);

  if (reduce) return <span className={className}>{text}</span>;
  return <ScrambleIn text={text} delay={delay} triggered={triggered} className={className} />;
}

interface ScrambleHoverProps {
  text: string;
  className?: string;
  /** When true (e.g. inside a Radix trigger), the parent controls hover. */
  isHovered?: boolean;
}

/**
 * Self-managed hover scramble for buttons, tabs, and links. Manages its own
 * hover state unless `isHovered` is supplied. Under prefers-reduced-motion it
 * renders plain text and never scrambles.
 */
export function ScrambleHover({ text, className, isHovered }: ScrambleHoverProps) {
  const reduce = useReducedMotion();
  const [hover, setHover] = useState(false);

  if (reduce) return <span className={className}>{text}</span>;

  if (isHovered !== undefined) {
    return <ScrambleText text={text} isHovered={isHovered} className={className} />;
  }
  return (
    <span
      className={className}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      <ScrambleText text={text} isHovered={hover} />
    </span>
  );
}
