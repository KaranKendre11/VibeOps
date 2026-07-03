import { useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { api, ApiError } from '../api/client';
import type { ArchitectureCandidate, NetworkOption } from '../api/types';
import { useStore } from '../store/useStore';
import { Button } from '../components/Button';
import { Select } from '../components/Select';
import { StatusDot } from '../components/StatusDot';
import { Label } from '../components/Field';
import { ScrambleReveal } from '../components/scramble';
import { cn, gpuLabel, quotaTone } from '../lib/utils';
import { QUINT } from '../lib/motion';

function networkName(n: NetworkOption): string {
  return typeof n === 'string' ? n : n.name;
}

function candidateCpus(c: ArchitectureCandidate): number | undefined {
  return c.cpus ?? c.vcpus;
}
function candidateRam(c: ArchitectureCandidate): number | undefined {
  return c.memory_gb ?? c.ram_gb;
}

export function ArchitectureScreen() {
  const graph = useStore((s) => s.graph);
  const applySnapshot = useStore((s) => s.applySnapshot);

  const options = graph?.architecture_options;
  const candidates = options?.candidates ?? [];
  const networks = useMemo(
    () => (options?.networks ?? []).map(networkName),
    [options?.networks],
  );
  const gpuFromReq =
    typeof options?.requirement?.gpu_type === 'string' ? options.requirement.gpu_type : undefined;

  const [selected, setSelected] = useState(0);
  const [network, setNetwork] = useState<string | undefined>(networks[0]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      const snap = await api.resumeGraph(
        {
          architecture_response: {
            candidate_index: selected,
            network_name: network ?? networks[0] ?? 'default',
          },
        },
        'architecture_pause',
      );
      applySnapshot(snap);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not confirm the architecture.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-10">
      <div>
        <h2 className="text-3xl font-semibold">
          <ScrambleReveal text="Pick a machine" />
        </h2>
        <p className="mt-3 max-w-2xl text-fg-muted">
          The agent discovered these GPU-capable configurations in your project, ranked by fit and
          live quota. Choose one to generate Terraform.
        </p>
      </div>

      {candidates.length === 0 ? (
        <p className="mt-10 rounded-md border border-dashed border-line px-6 py-12 text-center text-fg-dim">
          No candidates were returned. Try describing your workload again.
        </p>
      ) : (
        <div className="mt-8 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {candidates.map((c, i) => {
            const active = i === selected;
            const gpu = c.gpu_type ?? gpuFromReq;
            const cpus = candidateCpus(c);
            const ram = candidateRam(c);
            return (
              <motion.button
                key={`${c.zone}-${c.machine_type}-${i}`}
                onClick={() => setSelected(i)}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.06, duration: 0.5, ease: QUINT }}
                className={cn(
                  'group relative rounded-md p-5 text-left transition-all duration-300 ease-quint',
                  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-bg',
                  active
                    ? 'glass-cyan shadow-glow-sm'
                    : 'glass-1 hover:-translate-y-1 hover:border-accent/50 hover:shadow-glow-sm',
                )}
              >
                <div
                  className={cn(
                    'absolute right-4 top-4 grid h-5 w-5 place-items-center rounded-full border text-[10px]',
                    active ? 'border-accent bg-accent text-black' : 'border-line text-transparent',
                  )}
                >
                  ✓
                </div>

                <div className="font-mono text-sm text-accent">{c.machine_type}</div>
                <div className="mt-1 text-xs text-fg-dim">{c.zone}</div>

                <div className="mt-4 space-y-1.5 text-sm">
                  {gpu && (
                    <Row label="GPU" value={gpuLabel(gpu)} />
                  )}
                  {cpus !== undefined && <Row label="vCPUs" value={String(cpus)} />}
                  {ram !== undefined && <Row label="RAM" value={`${ram} GB`} />}
                </div>

                <div className="mt-4 flex items-center gap-2 border-t border-line pt-3">
                  <StatusDot tone={quotaTone(c.quota_remaining, c.quota_total)} />
                  <span className="text-xs text-fg-muted">
                    Quota {c.quota_remaining}/{c.quota_total} free
                  </span>
                </div>

                {c.rationale && (
                  <p className="mt-3 text-xs leading-relaxed text-fg-dim">{c.rationale}</p>
                )}
              </motion.button>
            );
          })}
        </div>
      )}

      {networks.length > 0 && (
        <div className="mt-8 max-w-sm">
          <Label htmlFor="network">Network</Label>
          <Select
            id="network"
            value={network}
            onChange={setNetwork}
            options={networks.map((n) => ({ value: n, label: n }))}
          />
        </div>
      )}

      {error && <p className="mt-6 text-sm text-red-400">{error}</p>}

      <div className="mt-8 flex items-center gap-3">
        <Button size="lg" onClick={confirm} loading={busy} disabled={candidates.length === 0}>
          Confirm & generate Terraform →
        </Button>
        <span className="text-xs text-fg-dim">
          You will review the plan and cost before anything is created.
        </span>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-fg-dim">{label}</span>
      <span className="font-medium text-fg">{value}</span>
    </div>
  );
}
