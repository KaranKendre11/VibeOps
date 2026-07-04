import { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { api, ApiError } from '../api/client';
import { streamSSE } from '../api/sse';
import type { ChatFrame } from '../api/types';
import { useStore } from '../store/useStore';
import { Marquee } from '../components/Marquee';
import { Button } from '../components/Button';
import { Spinner } from '../components/Spinner';
import { ScrambleReveal } from '../components/scramble';
import { cn } from '../lib/utils';
import { useParallax } from '../lib/useParallax';
import { QUINT } from '../lib/motion';

interface Example {
  title: string;
  desc: string;
  prompt: string;
}

const EXAMPLES: Example[] = [
  {
    title: 'Jupyter on a T4',
    desc: 'A GPU notebook for quick ML experiments.',
    prompt: 'Launch a Jupyter notebook server on a T4 GPU VM for machine-learning experiments.',
  },
  {
    title: 'nginx web app',
    desc: 'A public web server on a small VM.',
    prompt: 'Deploy an nginx web server on a small VM with port 80 open to the internet.',
  },
  {
    title: 'Fine-tune Llama on A100',
    desc: 'A heavy training run with plenty of disk.',
    prompt: 'Set up an A100 GPU VM with a 200GB disk to fine-tune a Llama model.',
  },
];

const MARQUEE = [
  'Describe the change',
  'Agent plans',
  'Review Terraform',
  'You approve',
  'Safe teardown',
];

// Deterministic, credential-free demo — the same pre-written example for everyone.
const DEMO_PROMPT = 'Run a Jupyter notebook on a T4 with port 8888 open';
const DEMO_SUMMARY =
  "On it. I'll provision an NVIDIA T4 GPU VM running Jupyter, open port 8888 to the internet, " +
  'and size the disk for notebooks. Next I check live zone capacity and quota, then show you the ' +
  'plan and cost to review before anything is created.';

// The model emits this control sentinel on its confirmation turn. The backend
// strips it from the stored conversation but NOT from the live token stream, so
// without this it briefly flashes in the chat bubble while streaming.
const PROCEED_SENTINEL = '[[PROCEED]]';

/**
 * Remove the `[[PROCEED]]` control sentinel from streamed text, for display.
 *
 * Robust against the sentinel arriving split across SSE chunks (e.g. one token
 * ends `…[[PRO` and the next is `CEED]]`):
 *  (a) every complete `[[PROCEED]]` occurrence is removed, and
 *  (b) a trailing partial sentinel — a suffix of `text` that is a non-empty
 *      prefix of the sentinel (e.g. a dangling `[[PRO`) — is withheld so it is
 *      never shown. It reappears naturally once more tokens arrive, or is gone
 *      for good once the stream completes and the cleaned message swaps in.
 *
 * Pure and side-effect-free so the raw stream can still be accumulated verbatim.
 */
function stripProceedSentinel(text: string): string {
  // (a) drop every complete occurrence.
  let out = text.split(PROCEED_SENTINEL).join('');
  // (b) withhold a dangling partial sentinel at the very end of the text.
  for (let n = Math.min(PROCEED_SENTINEL.length - 1, out.length); n > 0; n--) {
    if (out.endsWith(PROCEED_SENTINEL.slice(0, n))) {
      out = out.slice(0, out.length - n);
      break;
    }
  }
  return out;
}

export function ChatScreen() {
  const demoMode = useStore((s) => s.demoMode);
  if (demoMode) return <DemoWalkthrough />;
  return <LiveChat />;
}

// --------------------------------------------------------------------------
// Demo: a scripted walkthrough (no free-text chat that ignores input).
// --------------------------------------------------------------------------
function DemoWalkthrough() {
  const applySnapshot = useStore((s) => s.applySnapshot);
  const reduce = useReducedMotion();
  const [showReply, setShowReply] = useState(false);
  const [advancing, setAdvancing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Cancelled-flag-only pattern (StrictMode-safe): each run fires its own start
    // and the previous run is cancelled on cleanup, so the reply always resolves.
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    api
      .startGraph(DEMO_PROMPT)
      .then((snap) => {
        if (cancelled) return;
        setShowReply(true);
        timer = setTimeout(
          () => {
            setAdvancing(true);
            applySnapshot(snap);
          },
          reduce ? 500 : 1900,
        );
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof ApiError ? e.message : 'Could not start the demo.');
      });
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [applySnapshot, reduce]);

  return (
    <div className="mx-auto flex min-h-[72vh] max-w-3xl flex-col px-4">
      <div className="flex-1 space-y-5 overflow-y-auto py-8">
        <div className="flex justify-center">
          <span className="glass-1 rounded-pill px-3 py-1 font-mono text-[10px] uppercase tracking-[0.22em] text-accent">
            Guided demo
          </span>
        </div>
        <ChatBubble role="user" content={DEMO_PROMPT} />
        {!showReply && !error && <ThinkingRow />}
        {showReply && <ChatBubble role="agent" content={DEMO_SUMMARY} />}
        {error && <p className="text-center text-sm text-red-400">{error}</p>}
      </div>

      <div className="sticky bottom-0 bg-gradient-to-t from-bg via-bg/95 to-transparent pb-6 pt-3">
        <div className="flex items-center justify-center gap-2 text-xs text-fg-dim">
          {advancing || showReply ? <Spinner className="h-3.5 w-3.5" /> : null}
          <span>
            {advancing
              ? 'Opening the plan…'
              : showReply
                ? 'Preparing the plan…'
                : 'The agent is reading your request…'}
          </span>
        </div>
        <p className="mt-2 text-center text-xs text-fg-dim">
          Scripted, credential-free walkthrough. Connect credentials for live chat.
        </p>
      </div>
    </div>
  );
}

// --------------------------------------------------------------------------
// Live (credentialed) chat — hero + streaming conversation.
// --------------------------------------------------------------------------
function LiveChat() {
  const graph = useStore((s) => s.graph);
  const applySnapshot = useStore((s) => s.applySnapshot);

  const conversation = graph?.conversation ?? [];
  const hasConversation = conversation.length > 0;

  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [streamText, setStreamText] = useState('');
  const [pendingUser, setPendingUser] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const scrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
  }, [conversation.length, streamText, pendingUser]);

  async function startFlow(prompt: string) {
    const text = prompt.trim();
    if (!text || busy) return;
    setInput('');
    setError(null);
    setPendingUser(text);
    setBusy(true);
    try {
      const snap = await api.startGraph(text);
      applySnapshot(snap);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not start the flow.');
    } finally {
      setPendingUser(null);
      setBusy(false);
    }
  }

  async function sendTurn(reply: string) {
    const text = reply.trim();
    if (!text || busy || streaming) return;
    setInput('');
    setError(null);
    setPendingUser(text);
    setStreaming(true);
    setStreamText('');
    setBusy(true);
    try {
      await streamSSE<ChatFrame>('/api/chat/turn', {
        method: 'POST',
        body: { reply: text },
        onFrame: (f) => {
          if ('token' in f) setStreamText((prev) => prev + f.token);
        },
      });
      const snap = await api.getState();
      applySnapshot(snap);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'The turn failed to stream.');
    } finally {
      setStreaming(false);
      setStreamText('');
      setPendingUser(null);
      setBusy(false);
    }
  }

  function submit() {
    if (hasConversation) void sendTurn(input);
    else void startFlow(input);
  }

  const showConversation = hasConversation || pendingUser !== null;
  // Never render the raw stream directly — strip the `[[PROCEED]]` sentinel first
  // so it can't flash in the bubble mid-stream.
  const streamDisplay = stripProceedSentinel(streamText);

  return (
    <div className="mx-auto flex min-h-[72vh] max-w-3xl flex-col px-4">
      {showConversation ? (
        <div ref={scrollRef} className="flex-1 space-y-5 overflow-y-auto py-8">
          <AnimatePresence initial={false}>
            {conversation.map((turn, i) => (
              <ChatBubble key={i} role={turn.role} content={turn.content} />
            ))}
          </AnimatePresence>
          {pendingUser && <ChatBubble role="user" content={pendingUser} />}
          {streaming && (
            <ChatBubble role="agent" content={streamDisplay} streaming={streamDisplay.length === 0} />
          )}
          {busy && !streaming && pendingUser && <ThinkingRow />}
        </div>
      ) : (
        <Landing onPick={startFlow} busy={busy} />
      )}

      {/* Composer */}
      <div className="sticky bottom-0 bg-gradient-to-t from-bg via-bg/95 to-transparent pb-6 pt-3">
        {error && <p className="mb-2 text-center text-sm text-red-400">{error}</p>}
        <div className="glass-2 flex items-end gap-2 rounded-lg p-2 focus-within:border-accent/60">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
            rows={1}
            placeholder={hasConversation ? 'Reply to the agent…' : 'Describe the cloud change you want…'}
            className="max-h-40 flex-1 resize-none bg-transparent px-3 py-2 text-sm text-fg placeholder:text-fg-dim focus:outline-none"
          />
          <Button onClick={submit} loading={busy} disabled={!input.trim()} className="mb-0.5">
            {hasConversation ? 'Send' : 'Start'}
          </Button>
        </div>
      </div>
    </div>
  );
}

function Landing({ onPick, busy }: { onPick: (p: string) => void; busy: boolean }) {
  const parallax = useParallax(14);
  return (
    <div className="relative flex flex-1 flex-col items-center justify-center py-16 text-center">
      <div className="bg-grid pointer-events-none absolute inset-0 -z-10" />
      <motion.div
        className="flex flex-col items-center"
        style={{ x: parallax.x, y: parallax.y }}
      >
        <ScrambleReveal text="Autonomous cloud operations" className="text-meta !text-accent" />
        <h1 className="mt-5 max-w-2xl font-sans text-4xl font-semibold leading-[1.1] sm:text-5xl">
          <ScrambleReveal text="The AI agent that" className="block" />
          <ScrambleReveal text="safely operates your cloud." className="block text-accent" delay={250} />
        </h1>
      </motion.div>

      <motion.div
        className="mt-11 grid w-full gap-3 sm:grid-cols-3"
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.55, duration: 0.6, ease: QUINT }}
      >
        {EXAMPLES.map((ex) => (
          <button
            key={ex.title}
            disabled={busy}
            onClick={() => onPick(ex.prompt)}
            className={cn(
              'glass-1 group rounded-md p-4 text-left transition-all duration-300 ease-quint',
              'hover:-translate-y-1 hover:border-accent/60 hover:shadow-glow-sm disabled:opacity-50',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-bg',
            )}
          >
            <div className="mb-2 font-mono text-[11px] uppercase tracking-[0.15em] text-accent">
              Example
            </div>
            <div className="font-medium text-fg">{ex.title}</div>
            <div className="mt-1 text-sm text-fg-dim">{ex.desc}</div>
          </button>
        ))}
      </motion.div>

      <div className="mt-12 w-full">
        <Marquee items={MARQUEE} />
      </div>
    </div>
  );
}

function ChatBubble({
  role,
  content,
  streaming = false,
}: {
  role: string;
  content: string;
  streaming?: boolean;
}) {
  const isUser = role === 'user';
  return (
    <motion.div
      className={cn('flex', isUser ? 'justify-end' : 'justify-start')}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: QUINT }}
    >
      <div
        className={cn(
          'max-w-[85%] whitespace-pre-wrap rounded-md px-4 py-3 text-sm leading-relaxed',
          // User = accent glass; agent = near-opaque so streamed text stays crisp.
          isUser
            ? 'glass-cyan text-fg'
            : 'border border-white/10 bg-surface-2/90 text-fg-muted',
        )}
      >
        {!isUser && (
          <div className="mb-1 font-mono text-[10px] uppercase tracking-[0.2em] text-accent">
            Agent
          </div>
        )}
        {content}
        {streaming && (
          <span className="ml-0.5 inline-block h-4 w-2 animate-blink bg-accent align-middle" />
        )}
      </div>
    </motion.div>
  );
}

function ThinkingRow() {
  return (
    <div className="flex justify-start">
      <div className="glass-1 flex items-center gap-3 rounded-md px-4 py-3">
        <span className="text-meta">Thinking</span>
        <span className="shimmer-line h-0.5 w-16 rounded-full" />
      </div>
    </div>
  );
}
