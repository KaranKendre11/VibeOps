import { Wordmark } from './Wordmark';
import { BrandIcon } from './BrandIcon';
import { ScrambleHover } from './scramble';
import { useStore } from '../store/useStore';

/** Corner-anchored persistent chrome: wordmark (top-left), status + inventory
 *  (top-right), both floating in liquid-glass pills over the cosmic field. */
export function Chrome() {
  const setupComplete = useStore((s) => s.setupComplete);
  const demoMode = useStore((s) => s.demoMode);
  const setInventoryOpen = useStore((s) => s.setInventoryOpen);
  const exitToLanding = useStore((s) => s.exitToLanding);

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
        <button
          onClick={exitToLanding}
          aria-label="Exit to home"
          title="Exit to home"
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
