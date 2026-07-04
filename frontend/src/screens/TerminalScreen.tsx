import { motion } from 'framer-motion';
import { Button } from '../components/Button';
import { ScrambleReveal } from '../components/scramble';
import { useStore } from '../store/useStore';
import { QUINT } from '../lib/motion';

interface TerminalScreenProps {
  variant: 'cancelled' | 'done';
}

export function TerminalScreen({ variant }: TerminalScreenProps) {
  const cancelled = variant === 'cancelled';
  const resetPlan = useStore((s) => s.resetPlan);
  return (
    <div className="mx-auto flex min-h-[72vh] max-w-lg flex-col items-center justify-center px-4 text-center">
      <motion.div
        initial={{ opacity: 0, scale: 0.96 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.5, ease: QUINT }}
      >
        <div className="mx-auto mb-6 grid h-14 w-14 place-items-center rounded-full border border-line text-2xl text-fg-dim">
          {cancelled ? '⦸' : '✓'}
        </div>
        <h2 className="text-2xl font-semibold">
          <ScrambleReveal text={cancelled ? 'Deployment cancelled' : 'All done'} />
        </h2>
        <p className="mt-3 text-fg-muted">
          {cancelled
            ? 'Nothing was created. You can start a new request whenever you are ready.'
            : 'The flow is complete. Start a new request to operate your cloud again.'}
        </p>
        <div className="mt-7">
          <Button variant="secondary" size="lg" onClick={resetPlan}>
            Start over
          </Button>
        </div>
      </motion.div>
    </div>
  );
}
