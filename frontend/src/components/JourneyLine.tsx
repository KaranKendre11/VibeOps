import { useState } from 'react';
import { motion } from 'framer-motion';
import { JOURNEY_STEPS, stepIndexForStage, useStore } from '../store/useStore';
import type { NavDecision, StepKey } from '../store/useStore';
import { QUINT } from '../lib/motion';
import { cn } from '../lib/utils';
import { ConfirmNav } from './ConfirmNav';

interface PendingNav {
  target: StepKey;
  title: string;
  message: string;
  confirmLabel: string;
}

/**
 * The progress rail — VibeOps's safety-gated pipeline as an interactive, guarded
 * tab bar: a thin charged line, a glowing marker riding the ACTIVE node. Stages the
 * flow has reached are clickable tabs; stages ahead (or locked after deployment) are
 * disabled and dimmed. Going back to a stage where re-work could be discarded opens a
 * confirmation first. Navigation is UI-only — it switches the visible screen and never
 * re-runs or mutates the LangGraph state.
 */
export function JourneyLine() {
  const stage = useStore((s) => s.stage);
  const maxReached = useStore((s) => s.maxReached);
  const canNavigate = useStore((s) => s.canNavigate);
  const navigateTo = useStore((s) => s.navigateTo);
  const [pending, setPending] = useState<PendingNav | null>(null);

  const active = stepIndexForStage(stage);
  const traveledPct = (active / (JOURNEY_STEPS.length - 1)) * 100;
  // Referenced so the rail re-renders (and re-evaluates canNavigate) as reach grows.
  void maxReached;

  function handleClick(target: StepKey, decision: NavDecision) {
    if (decision.kind === 'allowed') {
      navigateTo(target);
    } else if (decision.kind === 'warn') {
      setPending({
        target,
        title: decision.title,
        message: decision.message,
        confirmLabel: decision.confirmLabel,
      });
    }
    // 'blocked' (button disabled) and 'current' are no-ops.
  }

  return (
    <div className="relative mx-auto w-full max-w-lg pb-7 pt-4">
      <nav
        aria-label="Deployment progress"
        className="relative flex h-4 items-center justify-between"
      >
        {/* Base track. */}
        <span aria-hidden className="absolute inset-x-0 top-1/2 h-px -translate-y-1/2 bg-line" />
        {/* Charged (traveled) portion — glowing cyan gradient. */}
        <motion.span
          aria-hidden
          className="absolute left-0 top-1/2 h-px -translate-y-1/2"
          style={{
            background: 'linear-gradient(90deg, rgba(255,77,141,0.15), rgba(255,77,141,0.75))',
            boxShadow: '0 0 10px rgba(255,77,141,0.5)',
          }}
          animate={{ width: `${traveledPct}%` }}
          transition={{ duration: 0.6, ease: QUINT }}
        />

        {JOURNEY_STEPS.map((step, i) => {
          const state = i < active ? 'done' : i === active ? 'active' : 'upcoming';
          const decision = canNavigate(step.key);
          const disabled = decision.kind === 'blocked';
          const isCurrent = decision.kind === 'current';
          const interactive = decision.kind === 'allowed' || decision.kind === 'warn';
          const reason = decision.kind === 'blocked' ? decision.reason : undefined;

          return (
            <button
              key={step.key}
              type="button"
              disabled={disabled}
              onClick={() => handleClick(step.key, decision)}
              aria-current={isCurrent ? 'step' : undefined}
              aria-label={`${step.label}${
                isCurrent ? ' — current step' : disabled ? ' — locked' : ''
              }`}
              title={reason}
              className={cn(
                'group relative flex flex-col items-center bg-transparent outline-none',
                interactive
                  ? 'cursor-pointer'
                  : isCurrent
                    ? 'cursor-default'
                    : 'cursor-not-allowed',
              )}
            >
              {/* Enlarged transparent hit + focus target (absolute → no layout impact). */}
              <span
                aria-hidden
                className={cn(
                  'absolute left-1/2 top-1/2 h-9 w-16 -translate-x-1/2 -translate-y-1/2 rounded-lg transition-colors',
                  'group-focus-visible:ring-2 group-focus-visible:ring-accent group-focus-visible:ring-offset-2 group-focus-visible:ring-offset-bg',
                  interactive && 'group-hover:bg-white/5',
                )}
              />

              {/* Pulsing ring + soft glow ride the active node (shared layout so they
                  slide as the stage advances — or retreats when navigating back). The
                  ring hugs the node itself so it reads as "you are here" rather than a
                  detached marker floating above the dot. */}
              {state === 'active' && (
                <>
                  {/* Centered with negative margins (NOT translate): a shared-layout
                      element must leave `transform` free for Framer's projection, or the
                      marker drifts off the node mid-slide. */}
                  <motion.span
                    aria-hidden
                    layoutId="journeyGlow"
                    transition={{ duration: 0.6, ease: QUINT }}
                    className="absolute left-1/2 top-1/2 h-7 w-7 rounded-full bg-accent/25 blur-md"
                    style={{ marginLeft: -14, marginTop: -14 }}
                  />
                  <motion.span
                    aria-hidden
                    layoutId="journeyCraft"
                    transition={{ duration: 0.6, ease: QUINT }}
                    className="absolute left-1/2 top-1/2 rounded-full"
                    style={{ marginLeft: -11, marginTop: -11 }}
                  >
                    <motion.span
                      className="block h-[22px] w-[22px] rounded-full border border-accent/70"
                      style={{ boxShadow: '0 0 8px rgba(255,77,141,0.5)' }}
                      animate={{ scale: [1, 1.18, 1], opacity: [0.75, 0.35, 0.75] }}
                      transition={{ duration: 2.4, ease: 'easeInOut', repeat: Infinity }}
                    />
                  </motion.span>
                </>
              )}
              <span
                className={cn(
                  'relative rounded-full transition-all duration-500 ease-quint',
                  state === 'active'
                    ? 'h-3 w-3 bg-accent shadow-[0_0_14px_rgba(255,77,141,0.9)]'
                    : state === 'done'
                      ? 'h-2 w-2 bg-accent/80'
                      : 'h-2 w-2 bg-white/20',
                  disabled && 'opacity-40',
                  interactive && 'group-hover:scale-[1.35]',
                )}
              />
              <span
                className={cn(
                  'text-meta absolute top-5 whitespace-nowrap transition-colors duration-500 ease-quint',
                  state === 'active'
                    ? 'text-accent'
                    : state === 'done'
                      ? 'text-fg-muted'
                      : 'text-fg-dim/50',
                  disabled && 'opacity-40',
                  interactive && 'group-hover:text-fg',
                )}
              >
                {step.label}
              </span>
            </button>
          );
        })}
      </nav>

      <ConfirmNav
        open={pending !== null}
        title={pending?.title ?? ''}
        message={pending?.message ?? ''}
        confirmLabel={pending?.confirmLabel}
        onConfirm={() => {
          if (pending) navigateTo(pending.target);
          setPending(null);
        }}
        onCancel={() => setPending(null)}
      />
    </div>
  );
}
