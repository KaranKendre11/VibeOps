import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { motion } from 'framer-motion';
import { api, ApiError } from '../api/client';
import { streamSSE } from '../api/sse';
import type { DeployFrame, StateResource } from '../api/types';
import { useStore } from '../store/useStore';
import { Panel } from '../components/Panel';
import { Button } from '../components/Button';
import { Spinner } from '../components/Spinner';
import { CodeBlock } from '../components/CodeBlock';
import { MaskReveal } from '../components/MaskReveal';
import { ScrambleReveal } from '../components/scramble';
import { cn } from '../lib/utils';
import { QUINT } from '../lib/motion';

const TERMINAL = ['succeeded', 'failed', 'destroyed', 'cancelled'];

const PHASE_LABEL: Record<string, string> = {
  idle: 'Preparing…',
  planning: 'Planning infrastructure…',
  applying: 'Applying — creating resources…',
  succeeded: 'Deployment succeeded',
  failed: 'Deployment failed',
  destroying: 'Tearing down…',
  destroyed: 'Resources destroyed',
  awaiting_destroy_confirm: 'Awaiting teardown…',
  cancelled: 'Cancelled',
};

export function DeploymentScreen() {
  const graph = useStore((s) => s.graph);
  const demoMode = useStore((s) => s.demoMode);
  const applySnapshot = useStore((s) => s.applySnapshot);
  const setInventoryOpen = useStore((s) => s.setInventoryOpen);
  const resetPlan = useStore((s) => s.resetPlan);

  const phase = graph?.deployment_phase ?? 'idle';
  const inProgress = !TERMINAL.includes(phase);

  const [streaming, setStreaming] = useState(false);
  const [liveLogs, setLiveLogs] = useState<string[]>([]);
  const [busy, setBusy] = useState<'retry' | 'destroy' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [externalIp, setExternalIp] = useState<string | null>(null);

  const startedRef = useRef(false);
  const logRef = useRef<HTMLDivElement>(null);

  const logs = liveLogs.length > 0 ? liveLogs : (graph?.deployment_logs ?? []);

  useEffect(() => {
    const el = logRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [logs.length, streaming]);

  // Open the live log stream once when we arrive mid-deployment.
  useEffect(() => {
    if (startedRef.current || !inProgress) return;
    startedRef.current = true;
    void beginLogs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Surface an external IP for the success card. The demo backend also returns a
  // (simulated) instance from /api/inventory, so this works in demo too.
  useEffect(() => {
    if (phase !== 'succeeded') return;
    let cancelled = false;
    api
      .getInventory()
      .then((r) => {
        if (cancelled || !r.available) return;
        const withIp = r.instances.find((i) => i.external_ip);
        if (withIp?.external_ip) setExternalIp(withIp.external_ip);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [phase]);

  async function beginLogs() {
    setStreaming(true);
    setError(null);
    setLiveLogs([]);
    try {
      await streamSSE<DeployFrame>('/api/deploy/logs', {
        method: 'GET',
        onFrame: (f) => {
          if ('log' in f) setLiveLogs((prev) => [...prev, f.log]);
        },
      });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Log stream interrupted.');
    }
    try {
      const snap = await api.getState();
      applySnapshot(snap);
    } catch {
      // keep last-known state
    }
    setStreaming(false);
  }

  async function teardown() {
    setBusy('destroy');
    setError(null);
    try {
      await api.destroy();
      startedRef.current = true;
      await beginLogs();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not start teardown.');
    } finally {
      setBusy(null);
    }
  }

  async function retry() {
    setBusy('retry');
    setError(null);
    try {
      // Launches the retry in the background (like /api/deploy/start); stream the
      // live logs and let beginLogs() resync authoritative state on completion.
      await api.retryDeploy();
      if (graph) {
        applySnapshot({
          stage: 'deployment',
          state: { ...graph, deployment_phase: 'planning', deployment_error: null, deployment_logs: [] },
        });
      }
      startedRef.current = true;
      await beginLogs();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Retry failed.');
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-10">
      <div className="flex items-center gap-3">
        <PhaseIcon phase={phase} streaming={streaming} />
        <div>
          <h2 className="text-2xl font-semibold">
            <ScrambleReveal key={phase} text={PHASE_LABEL[phase] ?? 'Deployment'} />
          </h2>
          {inProgress && <div className="shimmer-line mt-2 h-0.5 w-40 rounded-full" />}
        </div>
      </div>

      {/* Terminal log — near-opaque so streamed output stays crisp. */}
      <Panel tone="solid" className="mt-6 overflow-hidden">
        <div className="flex items-center gap-2 border-b border-line px-4 py-2.5">
          <span className="h-3 w-3 rounded-full bg-red-500/70" />
          <span className="h-3 w-3 rounded-full bg-amber-500/70" />
          <span className="h-3 w-3 rounded-full bg-emerald-500/70" />
          <span className="ml-2 font-mono text-xs text-fg-dim">terraform</span>
          {streaming && (
            <span className="ml-auto flex items-center gap-2 text-xs text-accent">
              <span className="h-2 w-2 animate-pulse-glow rounded-full bg-accent shadow-glow-sm" />
              streaming
            </span>
          )}
        </div>
        <div ref={logRef} className="max-h-[46vh] overflow-auto bg-black/80 p-4">
          {logs.length === 0 ? (
            <p className="font-mono text-sm text-fg-dim">
              {streaming ? 'Waiting for output…' : 'No log output yet.'}
            </p>
          ) : (
            <pre className="whitespace-pre-wrap break-words font-mono text-[13px] leading-relaxed text-fg-muted">
              {logs.map((line, i) => (
                <MaskReveal key={i}>{line || ' '}</MaskReveal>
              ))}
            </pre>
          )}
        </div>
      </Panel>

      {error && <p className="mt-4 text-sm text-red-400">{error}</p>}

      {/* Result cards */}
      {phase === 'succeeded' && (
        <ResultCard tone="good" title="Your infrastructure is live">
          <ResourceList resources={graph?.created_resources ?? []} />
          {externalIp && (
            <div className="mt-4 rounded-sm border border-line bg-black/40 px-4 py-3">
              <div className="text-xs text-fg-dim">External IP</div>
              <div className="font-mono text-accent">{externalIp}</div>
            </div>
          )}
          <SshHint resources={graph?.created_resources ?? []} externalIp={externalIp} />
          <div className="mt-5 flex flex-wrap gap-3">
            <Button variant="danger" onClick={teardown} loading={busy === 'destroy'}>
              Tear down
            </Button>
            <Button variant="ghost" onClick={() => setInventoryOpen(true)}>
              Open resource dashboard
            </Button>
          </div>
        </ResultCard>
      )}

      {phase === 'failed' && (
        <ResultCard tone="bad" title="Deployment failed">
          {graph?.deployment_error && (
            <pre className="mt-1 whitespace-pre-wrap rounded-sm border border-red-500/40 bg-red-500/5 p-3 font-mono text-xs text-red-200">
              {graph.deployment_error}
            </pre>
          )}
          {(graph?.created_resources?.length ?? 0) > 0 && (
            <div className="mt-4">
              <p className="mb-2 text-sm text-fg-dim">Partial resources were created:</p>
              <ResourceList resources={graph?.created_resources ?? []} />
            </div>
          )}
          <div className="mt-5 flex flex-wrap gap-3">
            <Button onClick={retry} loading={busy === 'retry'}>
              Retry deployment
            </Button>
            {(graph?.created_resources?.length ?? 0) > 0 && (
              <Button variant="danger" onClick={teardown} loading={busy === 'destroy'}>
                Tear down partial
              </Button>
            )}
          </div>
        </ResultCard>
      )}

      {phase === 'destroyed' && (
        <ResultCard tone="neutral" title="Resources torn down">
          <p className="text-sm text-fg-muted">
            Everything created for this deployment has been destroyed. You are billed for nothing.
          </p>
          <div className="mt-5">
            <Button variant="secondary" onClick={resetPlan}>
              Start something new
            </Button>
          </div>
        </ResultCard>
      )}

      {demoMode && inProgress && (
        <p className="mt-4 text-xs text-fg-dim">
          Demo mode — no real cloud resources are created.
        </p>
      )}
    </div>
  );
}

function PhaseIcon({ phase, streaming }: { phase: string; streaming: boolean }) {
  if (streaming || (phase !== 'succeeded' && phase !== 'failed' && phase !== 'destroyed')) {
    return <Spinner className="h-7 w-7" />;
  }
  const map: Record<string, { ch: string; cls: string }> = {
    succeeded: { ch: '✓', cls: 'border-emerald-400 text-emerald-400 shadow-[0_0_16px_rgba(52,211,153,0.5)]' },
    failed: { ch: '✕', cls: 'border-red-400 text-red-400 shadow-[0_0_16px_rgba(248,113,113,0.5)]' },
    destroyed: { ch: '↺', cls: 'border-fg-dim text-fg-dim' },
  };
  const m = map[phase] ?? { ch: '•', cls: 'border-line text-fg-dim' };
  return (
    <span className={cn('grid h-8 w-8 place-items-center rounded-full border text-lg', m.cls)}>
      {m.ch}
    </span>
  );
}

function ResultCard({
  tone,
  title,
  children,
}: {
  tone: 'good' | 'bad' | 'neutral';
  title: string;
  children: ReactNode;
}) {
  const border =
    tone === 'good'
      ? 'border-emerald-500/40'
      : tone === 'bad'
        ? 'border-red-500/40'
        : 'border-line';
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: QUINT }}
      className={cn('glass-2 mt-6 rounded-md p-6', border)}
    >
      <h3 className="text-xl font-semibold">
        <ScrambleReveal text={title} />
      </h3>
      <div className="mt-3">{children}</div>
    </motion.div>
  );
}

function ResourceList({ resources }: { resources: StateResource[] }) {
  if (resources.length === 0) {
    return <p className="text-sm text-fg-dim">No resources reported.</p>;
  }
  return (
    <ul className="space-y-1.5">
      {resources.map((r, i) => (
        <li key={i} className="flex items-center gap-3 font-mono text-sm">
          <span className="text-accent">›</span>
          <span className="text-fg">{r.name}</span>
          <span className="text-fg-dim">{r.type}</span>
          {r.zone && <span className="text-fg-dim">· {r.zone}</span>}
        </li>
      ))}
    </ul>
  );
}

function SshHint({
  resources,
  externalIp,
}: {
  resources: StateResource[];
  externalIp: string | null;
}) {
  const instance = resources.find((r) => r.type.includes('instance'));
  let hint: string | null = null;
  if (instance) {
    hint = `gcloud compute ssh ${instance.name}${instance.zone ? ` --zone ${instance.zone}` : ''}`;
  } else if (externalIp) {
    hint = `ssh <user>@${externalIp}`;
  }
  if (!hint) return null;
  return (
    <div className="mt-4">
      <div className="mb-1 text-xs text-fg-dim">Connect</div>
      <CodeBlock code={hint} />
    </div>
  );
}
