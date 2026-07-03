import { useEffect, useRef, useState } from 'react';
import {
  motion,
  useMotionTemplate,
  useReducedMotion,
  useScroll,
  useSpring,
  useTransform,
} from 'framer-motion';
import { ScrambleIn, ScrambleText } from '../components/scramble';
import { BrandIcon } from '../components/BrandIcon';

// CloudFront background clips (abstract). Used exactly as provided.
const VIDEOS = {
  hero: 'https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260622_083515_290e5a10-0b95-41af-a5e2-32b6389baa4d.mp4',
  cinematic:
    'https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260622_092455_089c54f8-3b03-4966-9df1-e9746063d0ef.mp4',
  metrics:
    'https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260622_095810_ecea3dd2-fc5e-4e41-8696-4219290b6589.mp4',
  tech: 'https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260622_095750_32a52ce0-2005-45c9-9093-41f03fde9530.mp4',
  footer:
    'https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260622_080203_fd7f4f85-3a86-4837-8192-85e7bfe68e75.mp4',
} as const;

const EASE_OUT = [0.215, 0.61, 0.355, 1.0] as const;

interface LandingProps {
  onEnter: () => void;
}

export function LandingScreen({ onEnter }: LandingProps) {
  const [entranceComplete, setEntranceComplete] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setEntranceComplete(true), 800);
    return () => clearTimeout(t);
  }, []);

  function scrollToId(id: string) {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });
    setMenuOpen(false);
  }

  return (
    <div
      className="relative w-full bg-black text-white"
      style={{ fontFamily: '"Space Mono", monospace' }}
    >
      <Navbar
        entranceComplete={entranceComplete}
        menuOpen={menuOpen}
        setMenuOpen={setMenuOpen}
        onEnter={onEnter}
        scrollToId={scrollToId}
      />
      <Hero entranceComplete={entranceComplete} onEnter={onEnter} />
      <CinematicText />
      <Metrics />
      <Capabilities />
      <Architecture onEnter={onEnter} />
      <Footer />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Navbar
// ---------------------------------------------------------------------------

interface NavbarProps {
  entranceComplete: boolean;
  menuOpen: boolean;
  setMenuOpen: (v: boolean) => void;
  onEnter: () => void;
  scrollToId: (id: string) => void;
}

function Navbar({ entranceComplete, menuOpen, setMenuOpen, onEnter, scrollToId }: NavbarProps) {
  const [hoverCap, setHoverCap] = useState(false);
  const [hoverMetrics, setHoverMetrics] = useState(false);
  const [hoverTry, setHoverTry] = useState(false);

  return (
    <motion.nav
      className="fixed inset-x-0 top-0 z-50 flex h-20 items-center justify-between px-4 sm:px-6 md:px-8"
      initial={{ opacity: 0 }}
      animate={{ opacity: entranceComplete ? 1 : 0 }}
      transition={{ duration: 0.8 }}
    >
      {/* Left group: logo pill + expanding menu pill */}
      <div className="flex items-center gap-2">
        <motion.button
          type="button"
          onClick={onEnter}
          className="flex h-12 items-center gap-2 rounded-[14px] bg-white/15 pl-1.5 pr-4 backdrop-blur-md"
          animate={{ width: menuOpen ? 0 : 'auto', opacity: menuOpen ? 0 : 1 }}
          style={{ overflow: 'hidden' }}
          whileHover={{ scale: 1.02, backgroundColor: 'rgba(255,255,255,0.22)' }}
          whileTap={{ scale: 0.98 }}
        >
          <BrandIcon size={38} />
          <span className="whitespace-nowrap text-[13px] font-medium tracking-tight sm:text-[16px]">
            VibeOps
          </span>
        </motion.button>

        <motion.div
          className="flex h-12 items-center rounded-[14px] bg-white/15 backdrop-blur-md"
          animate={{ width: menuOpen ? 290 : 48 }}
          transition={{ type: 'spring', stiffness: 350, damping: 28 }}
          style={{ overflow: 'hidden' }}
        >
          <button
            type="button"
            aria-label={menuOpen ? 'Close menu' : 'Open menu'}
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen(!menuOpen)}
            className={
              menuOpen
                ? 'ml-1.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-[11px] bg-white/10 hover:bg-white/20'
                : 'flex h-12 w-12 shrink-0 items-center justify-center rounded-[14px]'
            }
          >
            <SquashHamburger open={menuOpen} />
          </button>
          <motion.div
            className="flex shrink-0 items-center gap-5 pl-3"
            initial={false}
            animate={{ opacity: menuOpen ? 1 : 0, x: menuOpen ? 0 : 15 }}
            transition={{ duration: 0.25 }}
          >
            <button
              type="button"
              onClick={() => scrollToId('capabilities')}
              onMouseEnter={() => setHoverCap(true)}
              onMouseLeave={() => setHoverCap(false)}
              className="whitespace-nowrap text-[16px] font-normal text-white/85 hover:text-white"
            >
              <ScrambleText text="Capabilities" isHovered={hoverCap} />
            </button>
            <button
              type="button"
              onClick={() => scrollToId('metrics')}
              onMouseEnter={() => setHoverMetrics(true)}
              onMouseLeave={() => setHoverMetrics(false)}
              className="whitespace-nowrap text-[16px] font-normal text-white/85 hover:text-white"
            >
              <ScrambleText text="Metrics" isHovered={hoverMetrics} />
            </button>
          </motion.div>
        </motion.div>
      </div>

      {/* Right: primary CTA — enters the product */}
      <motion.button
        type="button"
        onClick={onEnter}
        onMouseEnter={() => setHoverTry(true)}
        onMouseLeave={() => setHoverTry(false)}
        className="flex h-12 items-center gap-2 rounded-full bg-white px-6 text-black"
        whileHover={{ scale: 1.03, backgroundColor: '#e2e2e6' }}
        whileTap={{ scale: 0.97 }}
      >
        <span className="text-[15px] font-medium">
          <ScrambleText text="Try it" isHovered={hoverTry} />
        </span>
        <span aria-hidden className="text-[15px]">
          →
        </span>
      </motion.button>
    </motion.nav>
  );
}

function SquashHamburger({ open }: { open: boolean }) {
  const spring = { type: 'spring', stiffness: 300, damping: 20 } as const;
  // Three 1.5px bars in a 12px box (rows centered at 0.75 / 6 / 11.25). Positioned
  // with `top` (not a translate) so Framer's transform doesn't fight the centering;
  // on open the outer bars slide ±5.25px to meet exactly at the middle and cross.
  const bar = 'absolute left-0 block h-[1.5px] w-full rounded-full bg-white';
  return (
    <span className="relative block h-3 w-[18px]">
      <motion.span
        className={bar}
        style={{ top: 0, transformOrigin: 'center' }}
        animate={open ? { rotate: 45, y: 5.25 } : { rotate: 0, y: 0 }}
        transition={spring}
      />
      <motion.span
        className={bar}
        style={{ top: 5.25 }}
        animate={open ? { opacity: 0, scaleX: 0 } : { opacity: 1, scaleX: 1 }}
        transition={spring}
      />
      <motion.span
        className={bar}
        style={{ top: 10.5, transformOrigin: 'center' }}
        animate={open ? { rotate: -45, y: -5.25 } : { rotate: 0, y: 0 }}
        transition={spring}
      />
    </span>
  );
}

// ---------------------------------------------------------------------------
// Section 1 — Hero (mouse-scrubbed video)
// ---------------------------------------------------------------------------

function Hero({ entranceComplete, onEnter }: { entranceComplete: boolean; onEnter: () => void }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const reduce = useReducedMotion();

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    let duration = 0;
    let target = 0;
    let seeking = false;

    // Nudge a frame so the paused hero shows imagery instead of a black rectangle
    // before the first scrub (and always, under reduced motion).
    const onMeta = () => {
      duration = video.duration || 0;
      if (video.currentTime === 0) video.currentTime = 0.05;
    };
    const onSeeked = () => {
      if (!seeking) return;
      if (Math.abs(video.currentTime - target) > 0.01) {
        video.currentTime = target;
      } else {
        seeking = false;
      }
    };
    const onMove = (e: MouseEvent) => {
      if (!duration) return;
      const step = (e.movementX * 0.8 * duration) / Math.max(1, window.innerWidth);
      target = Math.min(duration - 0.05, Math.max(0, target + step));
      if (!seeking) {
        seeking = true;
        video.currentTime = target;
      }
    };

    video.addEventListener('loadedmetadata', onMeta);
    if (video.readyState >= 1) onMeta(); // metadata already loaded (cache)

    // Reduced motion: show a still frame only, no cursor scrubbing.
    if (reduce) {
      return () => video.removeEventListener('loadedmetadata', onMeta);
    }

    video.addEventListener('seeked', onSeeked);
    window.addEventListener('mousemove', onMove);
    return () => {
      video.removeEventListener('loadedmetadata', onMeta);
      video.removeEventListener('seeked', onSeeked);
      window.removeEventListener('mousemove', onMove);
    };
  }, [reduce]);

  return (
    <section className="relative flex h-screen min-h-[100dvh] flex-col overflow-hidden px-4 pb-8 pt-20 sm:px-6 sm:pb-12 sm:pt-24 md:px-8">
      {/* Background video (z-auto — a negative z-index would hide it behind the
          page's black background). Content is lifted above it with z-10. */}
      <video
        ref={videoRef}
        src={VIDEOS.hero}
        muted
        playsInline
        preload="auto"
        className="absolute inset-0 h-full w-full object-cover"
      />
      {/* Legibility scrim — darken toward the bottom where the copy sits. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-gradient-to-t from-black/85 via-black/25 to-black/40"
      />
      {/* Dot grid overlay */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          backgroundImage: 'radial-gradient(#ffffff 1px, transparent 1px)',
          backgroundSize: '24px 24px',
          opacity: 0.05,
        }}
      />
      {/* Watermark */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 flex items-center justify-center"
        style={{ transform: 'translateY(50px)' }}
      >
        <span
          style={{
            fontFamily: '"Anton SC", sans-serif',
            fontSize: 'clamp(120px, 30vw, 521px)',
            letterSpacing: '-4px',
            opacity: 0.1,
            background: 'radial-gradient(circle, rgba(142,127,148,0) 0%, #8E7F94 70%)',
            WebkitBackgroundClip: 'text',
            backgroundClip: 'text',
            color: 'transparent',
            lineHeight: 1,
          }}
          className="uppercase"
        >
          VibeOps
        </span>
      </div>

      <div className="relative z-10 flex-1" />

      {/* Bottom content row */}
      <motion.div
        className="relative z-10 flex flex-col gap-6 md:flex-row md:items-end md:justify-between"
        initial={{ opacity: 0 }}
        animate={{ opacity: entranceComplete ? 1 : 0 }}
        transition={{ duration: 1 }}
      >
        <div className="flex flex-col gap-4">
          <h1 className="text-[clamp(40px,10vw,100px)] font-light leading-[0.95] tracking-[-0.03em] text-white">
            <ScrambleIn text="Ship" delay={200} triggered={entranceComplete} />
            <br />
            <ScrambleIn text="Any Cloud" delay={500} triggered={entranceComplete} />
          </h1>
          <motion.p
            className="max-w-sm text-[13px] leading-relaxed text-white/60 sm:text-[15px]"
            initial={{ opacity: 0, y: 25 }}
            animate={entranceComplete ? { opacity: 1, y: 0 } : {}}
            transition={{ duration: 0.9, ease: EASE_OUT, delay: 0.2 }}
          >
            Built at the intersection of natural language and cloud infrastructure. VibeOps turns a
            plain-English request into reviewed Terraform and a running GPU VM on GCP — you describe
            the change, review the plan, and approve.
          </motion.p>
          <motion.button
            type="button"
            onClick={onEnter}
            className="mt-2 w-fit rounded-full bg-white px-6 py-3 text-[14px] font-medium text-black"
            initial={{ opacity: 0, y: 25 }}
            animate={entranceComplete ? { opacity: 1, y: 0 } : {}}
            transition={{ duration: 0.9, ease: EASE_OUT, delay: 0.35 }}
            whileHover={{ scale: 1.03, backgroundColor: '#e2e2e6' }}
            whileTap={{ scale: 0.97 }}
          >
            Try it →
          </motion.button>
        </div>
        <h1 className="text-[clamp(40px,10vw,100px)] font-light leading-[0.95] tracking-[-0.03em] text-white md:text-right">
          <ScrambleIn text="One" delay={700} triggered={entranceComplete} />
          <br />
          <ScrambleIn text="Prompt" delay={1000} triggered={entranceComplete} />
        </h1>
      </motion.div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Section 2 — Cinematic 3D text
// ---------------------------------------------------------------------------

function CinematicText() {
  const ref = useRef<HTMLElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ['start end', 'end start'],
  });
  const smooth = useSpring(scrollYProgress, { stiffness: 15, damping: 32, mass: 1.8 });
  const y = useTransform(smooth, [0, 1], [60, -120]);
  const opacity = useTransform(smooth, [0.3, 0.5], [0, 1]);
  const transform = useMotionTemplate`rotateX(24deg) translateY(${y}px) translateZ(15px)`;

  return (
    <section
      id="cinematic"
      ref={ref}
      className="relative flex h-screen min-h-[100dvh] items-center justify-center overflow-hidden"
    >
      <video
        src={VIDEOS.cinematic}
        autoPlay
        muted
        loop
        playsInline
        className="absolute inset-0 h-full w-full object-cover"
      />
      <div
        aria-hidden
        className="absolute inset-x-0 top-0 z-10 h-[180px]"
        style={{ background: 'linear-gradient(to bottom, #010103, transparent)' }}
      />
      <div className="relative z-20 max-w-5xl px-6 sm:px-12" style={{ perspective: '400px' }}>
        <motion.p
          style={{ transform, opacity }}
          className="select-none text-center text-[22px] font-normal leading-[1.35] tracking-[-0.02em] text-white sm:text-[30px] md:text-[36px] lg:text-[42px]"
        >
          An AI agent built to operate your cloud the way you describe it. VibeOps translates
          plain-English intent into infrastructure as code. Every request becomes a reviewable
          Terraform plan. It provisions, verifies, and reports back — then tears everything down on
          command. Guesswork becomes a plan you approve.
        </motion.p>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Section 3 — Metrics
// ---------------------------------------------------------------------------

const METRICS = [
  { value: '~60s', label: 'Prompt to Terraform plan' },
  { value: '100%', label: 'Applies you review & approve' },
  { value: '$0', label: 'Idle spend after teardown' },
] as const;

function Metrics() {
  return (
    <section id="metrics" className="relative min-h-screen overflow-hidden">
      <video
        src={VIDEOS.metrics}
        autoPlay
        muted
        loop
        playsInline
        className="absolute inset-0 h-full w-full object-cover"
      />
      <div aria-hidden className="pointer-events-none absolute inset-0 bg-black/45" />
      <div className="relative z-10 mx-auto max-w-6xl px-6 pb-32 pt-32">
        <motion.p
          className="mb-20 text-center text-[13px] uppercase tracking-[0.2em] text-white/40 sm:text-[14px]"
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{ duration: 1.2 }}
        >
          Operational Metrics
        </motion.p>
        <div className="grid grid-cols-1 gap-16 md:grid-cols-3 md:gap-8">
          {METRICS.map((m, i) => (
            <motion.div
              key={m.label}
              className="text-center"
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.3 }}
              transition={{ duration: 0.8, delay: i * 0.15 }}
            >
              <div className="text-[clamp(48px,10vw,96px)] font-light leading-none tracking-[-0.04em] text-white">
                {m.value}
              </div>
              <div className="mt-4 text-[13px] tracking-wide text-white/40 sm:text-[15px]">
                {m.label}
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Section 4 — Capabilities
// ---------------------------------------------------------------------------

const CAPABILITIES = [
  { title: 'Natural Language', desc: 'Describe the change in plain English — no HCL required.' },
  { title: 'Generated Terraform', desc: 'Produces reviewable, scoped infrastructure as code.' },
  { title: 'Cost Preview', desc: 'Estimates spend and enforces your cost cap before any apply.' },
  { title: 'Safe Teardown', desc: 'One command destroys everything and stops the meter.' },
] as const;

function Capabilities() {
  return (
    <section
      id="capabilities"
      className="relative flex h-screen min-h-[100dvh] flex-col overflow-hidden px-8 py-12 sm:px-12 sm:py-16 md:px-16"
    >
      <video
        src={VIDEOS.tech}
        autoPlay
        muted
        loop
        playsInline
        className="absolute inset-0 h-full w-full object-cover"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-gradient-to-b from-black/70 via-black/30 to-black/70"
      />
      <div className="relative z-10 flex flex-col gap-6 md:flex-row md:items-start md:justify-between">
        <motion.h2
          className="text-[clamp(36px,8vw,72px)] font-light leading-[0.95] tracking-[-0.03em] text-white"
          initial={{ opacity: 0, y: 40 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{ duration: 1.0 }}
        >
          Infrastructure
          <br />
          You Approve
        </motion.h2>
        <motion.p
          className="max-w-xs text-[13px] leading-relaxed text-white/50 sm:text-[15px] md:pt-2 md:text-right"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{ duration: 1.0, delay: 0.2 }}
        >
          VibeOps discovers your zones and machine types, then generates Terraform scoped to exactly
          what you asked for — nothing runs until you say go.
        </motion.p>
      </div>

      <div className="relative z-10 flex-1" />

      <motion.div
        className="relative z-10 grid grid-cols-2 gap-8 md:grid-cols-4 md:gap-6"
        initial={{ opacity: 0 }}
        whileInView={{ opacity: 1 }}
        viewport={{ once: true, amount: 0.2 }}
        transition={{ duration: 1.0, delay: 0.3 }}
      >
        {CAPABILITIES.map((c, i) => (
          <motion.div
            key={c.title}
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.2 }}
            transition={{ duration: 0.7, delay: i * 0.1 }}
          >
            <div className="mb-2 text-[14px] font-normal text-white sm:text-[16px]">{c.title}</div>
            <div className="text-[12px] leading-relaxed text-white/40 sm:text-[14px]">{c.desc}</div>
          </motion.div>
        ))}
      </motion.div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Section 5 — Architecture (pure black)
// ---------------------------------------------------------------------------

const LAYERS = [
  { n: 'Step 1', name: 'Describe' },
  { n: 'Step 2', name: 'Plan' },
  { n: 'Step 3', name: 'Apply' },
] as const;

function Architecture({ onEnter }: { onEnter: () => void }) {
  return (
    <section className="relative min-h-screen bg-black px-6 py-32">
      <div className="mx-auto max-w-3xl text-center">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.4 }}
          transition={{ duration: 1.0 }}
        >
          <p className="mb-8 text-[13px] uppercase tracking-[0.2em] text-white/40 sm:text-[14px]">
            How it works
          </p>
          <h2 className="mb-10 text-[clamp(28px,6vw,56px)] font-light leading-[1.15] tracking-[-0.02em] text-white">
            Three steps. Full control.
          </h2>
          <p className="mx-auto max-w-xl text-[15px] leading-relaxed text-white/45 sm:text-[17px]">
            Describe your intent in plain English. VibeOps generates and prices the Terraform. It
            provisions on GCP — only after you approve. Tear it all down when you're done.
          </p>
        </motion.div>

        <motion.div
          className="mt-20 flex flex-col items-center gap-4"
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true, amount: 0.4 }}
          transition={{ duration: 1.2, delay: 0.4 }}
        >
          {LAYERS.map((l) => (
            <div
              key={l.n}
              className="flex h-[72px] w-full max-w-md items-center justify-between rounded-lg border border-white/10 px-6"
            >
              <span className="text-[12px] uppercase tracking-[0.15em] text-white/30">{l.n}</span>
              <span className="text-[16px] font-light text-white sm:text-[18px]">{l.name}</span>
            </div>
          ))}
        </motion.div>

        <motion.button
          type="button"
          onClick={onEnter}
          className="mt-16 rounded-full bg-white px-8 py-3.5 text-[15px] font-medium text-black"
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true, amount: 0.5 }}
          transition={{ duration: 0.8, delay: 0.6 }}
          whileHover={{ scale: 1.03, backgroundColor: '#e2e2e6' }}
          whileTap={{ scale: 0.97 }}
        >
          Try it →
        </motion.button>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Footer
// ---------------------------------------------------------------------------

function Footer() {
  return (
    <footer className="flex min-h-[400px] flex-col overflow-hidden bg-black md:flex-row">
      <div className="md:w-1/2">
        <video
          src={VIDEOS.footer}
          autoPlay
          muted
          loop
          playsInline
          className="h-[300px] w-full object-cover md:h-full"
        />
      </div>
      <div className="flex flex-col justify-between p-10 sm:p-16 md:w-1/2">
        <div>
          <div className="mb-8 flex items-center gap-3 text-white/70">
            <BrandIcon size={44} />
            <span className="text-[17px] font-medium tracking-tight">VibeOps</span>
          </div>
          <p className="max-w-sm text-[14px] leading-relaxed text-white/40 sm:text-[15px]">
            The AI agent that safely operates your cloud. Describe the change, review the plan,
            approve — done.
          </p>
        </div>
        <p className="mt-12 text-[12px] text-white/25">© 2026 VibeOps. All rights reserved.</p>
      </div>
    </footer>
  );
}
