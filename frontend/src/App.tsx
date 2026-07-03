import { useEffect } from 'react';
import type { ReactElement } from 'react';
import { AnimatePresence, motion, MotionConfig } from 'framer-motion';
import { api } from './api/client';
import { screenTransition } from './lib/motion';
import { useStore } from './store/useStore';
import { AmbientBlobs } from './components/AmbientBlobs';
import { Chrome } from './components/Chrome';
import { JourneyLine } from './components/JourneyLine';
import { InventoryDialog } from './components/InventoryDialog';
import { Spinner } from './components/Spinner';
import { Wordmark } from './components/Wordmark';
import { BrandIcon } from './components/BrandIcon';
import { LandingScreen } from './landing/LandingScreen';
import { SetupScreen } from './screens/SetupScreen';
import { ChatScreen } from './screens/ChatScreen';
import { ArchitectureScreen } from './screens/ArchitectureScreen';
import { ReviewScreen } from './screens/ReviewScreen';
import { DeploymentScreen } from './screens/DeploymentScreen';
import { TerminalScreen } from './screens/TerminalScreen';

export default function App() {
  const entered = useStore((s) => s.entered);
  const enterApp = useStore((s) => s.enterApp);
  const booted = useStore((s) => s.booted);
  const bootError = useStore((s) => s.bootError);
  const setupComplete = useStore((s) => s.setupComplete);
  const stage = useStore((s) => s.stage);
  const setBoot = useStore((s) => s.setBoot);
  const setBootError = useStore((s) => s.setBootError);

  // Boot: allocate a session (sets the httpOnly cookie) + load public config.
  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [session, config] = await Promise.all([api.createSession(), api.getConfig()]);
        if (active) setBoot({ config, threadId: session.thread_id });
      } catch (e) {
        if (active) setBootError(e instanceof Error ? e.message : 'Failed to reach the API.');
      }
    })();
    return () => {
      active = false;
    };
  }, [setBoot, setBootError]);

  // The cinematic landing gates the product; session boot runs in the background
  // (the effect above) so the app is ready by the time the user clicks "Try it".
  if (!entered) return <LandingScreen onEnter={enterApp} />;

  if (!booted) return <BootSplash />;
  if (bootError) return <BootError message={bootError} />;

  const { key, node } = pickScreen(setupComplete, stage);
  const showJourney = setupComplete && key !== 'setup';

  return (
    <MotionConfig reducedMotion="user">
      <AmbientBlobs />
      <Chrome />
      <main className="min-h-screen pt-16 sm:pt-20">
        {showJourney && (
          <div className="px-4 pb-2 pt-4">
            <JourneyLine />
          </div>
        )}
        <AnimatePresence mode="wait">
          <motion.div key={key} {...screenTransition}>
            {node}
          </motion.div>
        </AnimatePresence>
      </main>
      <InventoryDialog />
    </MotionConfig>
  );
}

function pickScreen(setupComplete: boolean, stage: string): { key: string; node: ReactElement } {
  if (!setupComplete) return { key: 'setup', node: <SetupScreen /> };
  switch (stage) {
    case 'architecture':
      return { key: 'architecture', node: <ArchitectureScreen /> };
    case 'review':
      return { key: 'review', node: <ReviewScreen /> };
    case 'deployment':
      return { key: 'deployment', node: <DeploymentScreen /> };
    case 'cancelled':
      return { key: 'cancelled', node: <TerminalScreen variant="cancelled" /> };
    case 'done':
      return { key: 'done', node: <TerminalScreen variant="done" /> };
    case 'chat':
    case 'idle':
    default:
      return { key: 'chat', node: <ChatScreen /> };
  }
}

function BootSplash() {
  return (
    <div className="grid min-h-screen place-items-center bg-bg">
      <div className="flex flex-col items-center gap-6">
        <BrandIcon size={96} className="drop-shadow-[0_0_28px_rgba(255,77,141,0.55)]" />
        <Wordmark hero />
        <div className="flex items-center gap-3 text-fg-dim">
          <Spinner className="h-4 w-4" /> starting session…
        </div>
      </div>
    </div>
  );
}

function BootError({ message }: { message: string }) {
  return (
    <div className="grid min-h-screen place-items-center bg-bg px-6 text-center">
      <div>
        <Wordmark className="text-2xl" />
        <p className="mt-6 text-red-400">Could not reach the VibeOps API.</p>
        <p className="mt-2 max-w-md text-sm text-fg-dim">{message}</p>
        <p className="mt-4 text-xs text-fg-dim">
          Ensure the FastAPI backend is running (uvicorn on :8000 in dev).
        </p>
      </div>
    </div>
  );
}
