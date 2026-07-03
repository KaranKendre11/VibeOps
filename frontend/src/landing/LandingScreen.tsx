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
      <Problem />
      <Metrics />
      <Capabilities />
      <Finale onEnter={onEnter} />
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
            VibeOps turns a plain-English request into reviewed Terraform and a running GPU VM on
            GCP. You describe the change, review the plan, approve — it provisions, then tears it all
            down on command.
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
// Section 3 — The problem (the manual grind VibeOps removes)
// ---------------------------------------------------------------------------

const MANUAL_STEPS = [
  'Pick a machine type',
  'Hunt for a zone with GPU quota',
  'Find an OS image that ships CUDA',
  'Hand-write the Terraform',
  'Open the right firewall ports',
  'terraform validate, then apply',
  'SSH in and install your stack',
  'Debug the startup script',
  'Remember to tear it all down',
] as const;

function Problem() {
  return (
    <section className="relative flex min-h-screen items-center overflow-hidden bg-black px-6 py-28 sm:px-10 md:px-16">
      {/* faint dot grid for texture between the two video sections */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          backgroundImage: 'radial-gradient(#ffffff 1px, transparent 1px)',
          backgroundSize: '24px 24px',
          opacity: 0.04,
        }}
      />
      <div className="relative z-10 mx-auto w-full max-w-6xl">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{ duration: 0.9 }}
        >
          <p className="mb-6 text-[13px] uppercase tracking-[0.2em] text-white/40 sm:text-[14px]">
            The problem
          </p>
          <h2 className="max-w-3xl text-[clamp(32px,6.5vw,64px)] font-light leading-[1.05] tracking-[-0.03em] text-white">
            Nine steps to a GPU box.
            <br />
            Or one sentence.
          </h2>
        </motion.div>

        <div className="mt-14 grid grid-cols-1 gap-12 md:mt-20 md:grid-cols-2 md:gap-16">
          {/* The manual grind */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.3 }}
            transition={{ duration: 0.9, delay: 0.1 }}
          >
            <p className="mb-6 text-[12px] uppercase tracking-[0.18em] text-white/30">The usual way</p>
            <ul className="space-y-3.5">
              {MANUAL_STEPS.map((s, i) => (
                <li
                  key={s}
                  className="flex items-baseline gap-4 text-[14px] leading-snug text-white/45 sm:text-[15px]"
                >
                  <span className="w-5 shrink-0 text-right text-[12px] tabular-nums text-white/20">
                    {String(i + 1).padStart(2, '0')}
                  </span>
                  <span>{s}</span>
                </li>
              ))}
            </ul>
          </motion.div>

          {/* The VibeOps way */}
          <motion.div
            className="flex flex-col justify-center"
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.3 }}
            transition={{ duration: 0.9, delay: 0.25 }}
          >
            <p className="mb-6 text-[12px] uppercase tracking-[0.18em] text-white/30">With VibeOps</p>
            <div className="rounded-xl border border-white/10 bg-white/[0.02] p-6 backdrop-blur-sm">
              <div className="mb-4 flex items-center gap-1.5" aria-hidden>
                <span className="h-2.5 w-2.5 rounded-full bg-white/15" />
                <span className="h-2.5 w-2.5 rounded-full bg-white/15" />
                <span className="h-2.5 w-2.5 rounded-full bg-white/15" />
              </div>
              <p className="text-[15px] leading-relaxed text-white/90 sm:text-[17px]">
                <span className="text-white/40">$ </span>
                deploy a jupyter box on a T4 with port 8888 open to the web
              </p>
            </div>
            <p className="mt-6 text-[14px] leading-relaxed text-white/45 sm:text-[15px]">
              You write one sentence. VibeOps handles the other nine — including the teardown you&rsquo;d
              rather not forget.
            </p>
          </motion.div>
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Section 4 — Metrics
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
// Section 5 — Capabilities
// ---------------------------------------------------------------------------

const CAPABILITIES = [
  {
    title: 'Intent extraction',
    desc: 'One LLM pass pulls GPU, ports, OS, and region from your words — and never re-asks what you already said.',
  },
  {
    title: 'GPU-aware zones',
    desc: 'Live GCP queries for accelerator stock and your project quota, ranked by free capacity.',
  },
  {
    title: 'Editable Terraform',
    desc: 'Generated HCL sits beside the spec. Edit it inline; it re-validates before deploy.',
  },
  {
    title: 'Real cost estimates',
    desc: 'Priced from GCP’s Cloud Catalog and capped at your monthly budget, with override.',
  },
  {
    title: 'Firewall, startup & containers',
    desc: '“port 443 running nginx” becomes a firewall rule, container metadata, and a clickable URL.',
  },
  {
    title: 'Inventory & recovery',
    desc: 'See every VM from any screen, tear down in bulk, and retry a new zone when quota runs out.',
  },
] as const;

function Capabilities() {
  return (
    <section
      id="capabilities"
      className="relative flex min-h-screen flex-col overflow-hidden px-8 py-24 sm:px-12 sm:py-28 md:px-16"
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
        className="relative z-10 grid grid-cols-2 gap-x-8 gap-y-10 md:grid-cols-3 md:gap-x-10 md:gap-y-12"
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
// Section 6 — How it works + close (the pipeline pinned beside the llama)
// ---------------------------------------------------------------------------

const STAGES = [
  {
    name: 'Understand',
    desc: 'One LLM pass pulls every detail from your words — GPU, ports, OS, region — then asks plain-language follow-ups for anything still missing.',
  },
  {
    name: 'Locate',
    desc: 'Live GCP lookups for accelerator availability and your project quota, ranked by free capacity, so the box lands where there is room.',
  },
  {
    name: 'Generate',
    desc: 'Renders valid, scoped Terraform — firewall rules, startup scripts, and containers included. Edit the HCL inline before anything runs.',
  },
  {
    name: 'Price',
    desc: 'Estimates monthly cost from GCP’s Cloud Catalog and holds it against your cap. Over budget fails closed unless you override.',
  },
  {
    name: 'Deploy',
    desc: 'Checks the plan against a resource allowlist, then applies — only after you approve. The live log streams as resources come up.',
  },
  {
    name: 'Live',
    desc: 'Hands back a clickable URL the moment the box is up. One click tears everything down and stops the meter.',
  },
] as const;

function Finale({ onEnter }: { onEnter: () => void }) {
  return (
    <section id="how" className="relative bg-black md:flex md:items-stretch">
      {/* The llama asset — a banner on mobile, pinned beside the pipeline on desktop */}
      <div className="relative w-full md:w-1/2">
        <div className="relative h-[38vh] overflow-hidden md:sticky md:top-0 md:h-screen">
          <video
            src={VIDEOS.footer}
            autoPlay
            muted
            loop
            playsInline
            className="h-full w-full object-cover"
          />
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0 bg-gradient-to-t from-black via-black/10 to-transparent md:bg-gradient-to-r md:from-transparent md:via-black/5 md:to-black"
          />
        </div>
      </div>

      {/* How it works + close */}
      <div className="relative w-full px-6 py-20 sm:px-10 md:w-1/2 md:px-14 md:py-24">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{ duration: 0.9 }}
        >
          <p className="mb-6 text-[13px] uppercase tracking-[0.2em] text-white/40 sm:text-[14px]">
            How it works
          </p>
          <h2 className="text-[clamp(28px,4.5vw,48px)] font-light leading-[1.05] tracking-[-0.03em] text-white">
            One sentence in.
            <br />
            A running box out.
          </h2>
          <p className="mt-6 max-w-md text-[14px] leading-relaxed text-white/45 sm:text-[16px]">
            Every request runs the same six-stage pipeline. The agent pauses for you at each
            decision — nothing touches your cloud until you approve.
          </p>

          <div className="mt-8 rounded-xl border border-white/10 bg-white/[0.02] p-5 backdrop-blur-sm">
            <p className="mb-2 text-[11px] uppercase tracking-[0.18em] text-white/30">Your prompt</p>
            <p className="text-[15px] leading-relaxed text-white/90 sm:text-[18px]">
              <span className="text-white/40">&gt; </span>
              Jupyter notebook on a T4 with port 8888 open to the web
            </p>
          </div>
        </motion.div>

        <div className="relative mt-12 border-l border-white/10 pl-8">
          {STAGES.map((s, i) => (
            <motion.div
              key={s.name}
              className="relative pb-10 last:pb-0"
              initial={{ opacity: 0, x: 20 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true, amount: 0.5 }}
              transition={{ duration: 0.6, delay: i * 0.06 }}
            >
              <span className="absolute -left-8 top-1.5 -translate-x-1/2" aria-hidden>
                <span className="block h-2 w-2 rounded-full bg-white/50 ring-4 ring-black" />
              </span>
              <div className="flex items-baseline gap-4">
                <span className="text-[12px] tracking-[0.15em] text-white/30">
                  {String(i + 1).padStart(2, '0')}
                </span>
                <span className="text-[17px] font-light text-white sm:text-[20px]">{s.name}</span>
              </div>
              <p className="mt-2 text-[13px] leading-relaxed text-white/45 sm:text-[14px]">
                {s.desc}
              </p>
            </motion.div>
          ))}
        </div>

        <motion.button
          type="button"
          onClick={onEnter}
          className="mt-12 rounded-full bg-white px-8 py-3.5 text-[15px] font-medium text-black"
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true, amount: 0.5 }}
          transition={{ duration: 0.8, delay: 0.2 }}
          whileHover={{ scale: 1.03, backgroundColor: '#e2e2e6' }}
          whileTap={{ scale: 0.97 }}
        >
          Try it →
        </motion.button>

        {/* Close — brand, tagline, copyright, folded in beside the llama */}
        <div className="mt-20 border-t border-white/10 pt-8">
          <div className="mb-4 flex items-center gap-3 text-white/70">
            <BrandIcon size={40} />
            <span className="text-[16px] font-medium tracking-tight">VibeOps</span>
          </div>
          <p className="max-w-sm text-[13px] leading-relaxed text-white/40 sm:text-[14px]">
            The AI agent that safely operates your cloud. Describe the change, review the plan,
            approve — done.
          </p>
          <p className="mt-8 text-[12px] text-white/25">© 2026 VibeOps. All rights reserved.</p>
        </div>
      </div>
    </section>
  );
}
