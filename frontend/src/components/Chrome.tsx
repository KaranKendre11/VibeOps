import { Wordmark } from './Wordmark';
import { BrandIcon } from './BrandIcon';
import { ScrambleHover } from './scramble';
import { api } from '../api/client';
import { useStore } from '../store/useStore';

/** Corner-anchored persistent chrome: wordmark (top-left), status + inventory
 *  (top-right), both floating in liquid-glass pills over the cosmic field. */
export function Chrome() {
  const setupComplete = useStore((s) => s.setupComplete);
  const demoMode = useStore((s) => s.demoMode);
  const setInventoryOpen = useStore((s) => s.setInventoryOpen);
  const exitToLanding = useStore((s) => s.exitToLanding);
  const reset = useStore((s) => s.reset);

  // Full sign-out: wipe credentials/setup server-side, drop all client state, and
  // return to the landing gate. Distinct from the soft "×" (which keeps the session).
  async function clearCredentialsAndExit() {
    try {
      await api.resetCredentials();
    } catch {
      // Even if the server call fails, still wipe local state and leave — the
      // in-memory session is short-lived and never persisted.
    }
    reset();
    exitToLanding();
  }

  return (
    <>
      <div className="fixed left-5 top-5 z-40 sm:left-7 sm:top-6">
        <div className="liquid-glass flex items-center gap-2 rounded-pill py-1.5 pl-1.5 pr-4">
          <BrandIcon size={32} />
          <Wordmark className="text-sm" />
        </div>
      </div>

      <div className="fixed right-5 top-5 z-40 flex items-center gap-3 sm:right-7 sm:top-6">
        {demoMode && (
          <span className="liquid-glass text-meta flex items-center gap-2 rounded-pill px-3 py-1.5 !text-accent">
            <span className="h-1.5 w-1.5 rounded-full bg-accent shadow-glow-sm" />
            Demo
          </span>
        )}
        {setupComplete && (
          <button
            onClick={() => setInventoryOpen(true)}
            className="liquid-glass rounded-pill px-4 py-2 text-xs text-fg-muted transition-colors duration-300 ease-quint hover:text-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-4 focus-visible:ring-offset-bg"
          >
            <ScrambleHover text="VM Inventory" />
          </button>
        )}
        {setupComplete && (
          <button
            onClick={() => void clearCredentialsAndExit()}
            title="Clear your OpenAI key & GCP credentials and return to the landing page"
            className="liquid-glass rounded-pill px-4 py-2 text-xs text-fg-muted transition-colors duration-300 ease-quint hover:text-red-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400 focus-visible:ring-offset-4 focus-visible:ring-offset-bg"
          >
            <ScrambleHover text="Clear credentials" />
          </button>
        )}
        <button
          onClick={exitToLanding}
          aria-label="Return to home (keeps your session)"
          title="Return to home — your session and credentials stay active"
          className="liquid-glass grid h-9 w-9 place-items-center rounded-pill text-fg-muted transition-colors duration-300 ease-quint hover:text-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-4 focus-visible:ring-offset-bg"
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
          >
            <path d="M6 6l12 12M18 6L6 18" />
          </svg>
        </button>
      </div>
    </>
  );
}
