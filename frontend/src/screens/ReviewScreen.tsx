import { useMemo, useState } from 'react';
import * as Tabs from '@radix-ui/react-tabs';
import { Reveal, RevealGroup } from '../components/Reveal';
import { api, ApiError } from '../api/client';
import type { DeploymentSpec, Snapshot } from '../api/types';
import { useStore } from '../store/useStore';
import { Panel, PanelHeader } from '../components/Panel';
import { Button } from '../components/Button';
import { ScrambleHover, ScrambleReveal } from '../components/scramble';
import { cn, gpuLabel, humanize, usd } from '../lib/utils';

interface SpecRow {
  label: string;
  value: string;
}

function specSections(spec: DeploymentSpec): { title: string; rows: SpecRow[] }[] {
  const c = spec.compute;
  const s = spec.storage;
  const n = spec.network;
  return [
    {
      title: 'Compute',
      rows: [
        { label: 'Machine type', value: c.machine_type },
        { label: 'Zone', value: c.zone },
        { label: 'GPU', value: `${c.gpu_count}× ${gpuLabel(c.gpu_type)}` },
        { label: 'Preemptible', value: c.preemptible ? 'yes' : 'no' },
      ],
    },
    {
      title: 'Storage',
      rows: [
        { label: 'Disk size', value: `${s.disk_size_gb} GB` },
        { label: 'OS image', value: s.os_image_family },
      ],
    },
    {
      title: 'Network',
      rows: [
        { label: 'Network', value: n.network_name },
        { label: 'Open ports', value: n.open_ports.length ? n.open_ports.join(', ') : 'none' },
        { label: 'External IP', value: n.create_external_ip ? 'yes' : 'no' },
      ],
    },
    {
      title: 'Project',
      rows: [{ label: 'Project ID', value: spec.project_id }],
    },
  ];
}

export function ReviewScreen() {
  const graph = useStore((s) => s.graph);
  const demoMode = useStore((s) => s.demoMode);
  const costCap = useStore((s) => s.costCap);
  const applySnapshot = useStore((s) => s.applySnapshot);

  const spec = graph?.deployment_spec ?? null;
  const files = useMemo(() => graph?.terraform_files ?? {}, [graph?.terraform_files]);
  const cost = graph?.cost_estimate ?? null;
  const costStale = Boolean(graph?.cost_estimate_stale);
  const capExceeded = Boolean(graph?.cost_cap_exceeded);
  const validationErrors = graph?.validation_errors ?? [];

  const fileNames = useMemo(() => Object.keys(files), [files]);
  const [edited, setEdited] = useState<Record<string, string>>(files);
  const [activeTab, setActiveTab] = useState(fileNames[0] ?? 'main.tf');
  const [busy, setBusy] = useState<'approve' | 'cancel' | 'save' | 'reestimate' | null>(null);
  const [error, setError] = useState<string | null>(null);

  const dirty = useMemo(
    () => fileNames.some((f) => (edited[f] ?? '') !== (files[f] ?? '')),
    [edited, files, fileNames],
  );

  async function approve() {
    setBusy('approve');
    setError(null);
    try {
      await api.startDeploy();
      // Optimistically enter the deployment screen. The background worker may not
      // have flipped the phase yet, so we transition locally and let the log stream
      // (opened by DeploymentScreen) resync the authoritative state on completion.
      if (graph) {
        applySnapshot({
          stage: 'deployment',
          state: { ...graph, deployment_phase: 'planning', deployment_logs: [] },
        });
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not start deployment.');
      setBusy(null);
    }
  }

  async function cancel() {
    setBusy('cancel');
    setError(null);
    try {
      const snap = await api.resumeGraph({});
      applySnapshot(snap);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not cancel.');
      setBusy(null);
    }
  }

  async function saveEdits() {
    setBusy('save');
    setError(null);
    try {
      // /api/review/edit takes one file at a time and updates the graph WITHOUT
      // advancing, so the flow stays on review. Save each dirty file in turn.
      const dirtyFiles = fileNames.filter((f) => (edited[f] ?? '') !== (files[f] ?? ''));
      let snap: Snapshot | null = null;
      for (const f of dirtyFiles) {
        snap = await api.reviewEdit(f, edited[f] ?? '');
      }
      if (snap) {
        applySnapshot(snap);
        // Re-sync the editor from the persisted files (clears the dirty flag and
        // reflects any server-side normalization).
        setEdited(snap.state?.terraform_files ?? edited);
      }
    } catch (e) {
      // 422 -> invalid/disallowed HCL, 409 -> no review in progress. ApiError.message
      // carries the backend `detail`.
      setError(e instanceof ApiError ? e.message : 'Could not save Terraform.');
    } finally {
      setBusy(null);
    }
  }

  async function reestimate() {
    setBusy('reestimate');
    setError(null);
    try {
      const snap = await api.reviewReestimate();
      applySnapshot(snap);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not re-estimate cost.');
    } finally {
      setBusy(null);
    }
  }

  const cap = costCap ?? null;
  const monthly = cost?.monthly_usd ?? null;
  const barPct =
    cap && monthly ? Math.max(4, Math.min(100, (monthly / cap) * 100)) : capExceeded ? 100 : 0;

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <RevealGroup>
      <Reveal>
        <h2 className="text-3xl font-semibold">
          <ScrambleReveal text="Review the plan" />
        </h2>
        <p className="mt-3 max-w-2xl text-fg-muted">
          Nothing has been created yet. Inspect the spec, the generated Terraform, and the cost
          estimate — then approve to deploy.
        </p>
      </Reveal>

      {(capExceeded || validationErrors.length > 0) && (
        <Reveal className="mt-6 space-y-2">
          {capExceeded && (
            <div className="rounded-sm border border-amber-500/50 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
              Estimated cost exceeds your monthly cap{cap ? ` of ${usd(cap)}` : ''}.
            </div>
          )}
          {validationErrors.map((v, i) => (
            <div
              key={i}
              className="rounded-sm border border-red-500/50 bg-red-500/10 px-4 py-3 text-sm text-red-200"
            >
              {v}
            </div>
          ))}
        </Reveal>
      )}

      <Reveal className="mt-8 grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
        {/* Left column: spec + cost */}
        <div className="space-y-5">
          <Panel tone="solid">
            <PanelHeader title="Deployment spec" />
            <div className="divide-y divide-line">
              {spec ? (
                specSections(spec).map((section) => (
                  <div key={section.title} className="px-5 py-4">
                    <div className="mb-2 text-xs font-medium uppercase tracking-wide text-fg-dim">
                      {section.title}
                    </div>
                    <dl className="space-y-1.5">
                      {section.rows.map((row) => (
                        <div key={row.label} className="flex items-center justify-between gap-4 text-sm">
                          <dt className="text-fg-dim">{row.label}</dt>
                          <dd className="text-right font-medium text-fg">{row.value}</dd>
                        </div>
                      ))}
                    </dl>
                  </div>
                ))
              ) : (
                <p className="px-5 py-6 text-sm text-fg-dim">No spec available.</p>
              )}
            </div>
          </Panel>

          <Panel>
            <PanelHeader title="Cost estimate" right={cost && <SourceChip cost={cost} />} />
            <div className="px-5 py-4">
              {costStale && (
                <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-sm border border-amber-500/40 bg-amber-500/5 px-3 py-2">
                  <span className="text-xs text-amber-200">
                    Estimate may be out of date after your edits.
                  </span>
                  <Button
                    variant="secondary"
                    size="sm"
                    loading={busy === 'reestimate'}
                    onClick={reestimate}
                  >
                    Re-estimate cost
                  </Button>
                </div>
              )}
              {cost ? (
                <>
                  <div className="flex items-end justify-between">
                    <div>
                      <div className="text-3xl font-semibold text-fg">{usd(cost.monthly_usd)}</div>
                      <div className="text-xs text-fg-dim">per month</div>
                    </div>
                    <div className="text-right">
                      <div className="text-lg font-medium text-fg-muted">
                        {usd(cost.hourly_usd, { cents: true })}
                      </div>
                      <div className="text-xs text-fg-dim">per hour</div>
                    </div>
                  </div>

                  {cap && (
                    <div className="mt-4">
                      <div className="mb-1 flex justify-between text-xs text-fg-dim">
                        <span>Budget</span>
                        <span>
                          {usd(monthly)} / {usd(cap)} cap
                        </span>
                      </div>
                      <div className="h-2 overflow-hidden rounded-pill bg-white/10">
                        <div
                          className={cn(
                            'h-full rounded-pill transition-all',
                            capExceeded ? 'bg-amber-400' : 'bg-accent shadow-glow-sm',
                          )}
                          style={{ width: `${barPct}%` }}
                        />
                      </div>
                    </div>
                  )}

                  {cost.breakdown.length > 0 && (
                    <div className="mt-5 space-y-1.5 border-t border-line pt-4">
                      {cost.breakdown.map((item, i) => (
                        <div key={i} className="flex justify-between gap-4 text-sm">
                          <span className="text-fg-dim">{item.description}</span>
                          <span className="font-medium text-fg">{usd(item.monthly_usd)}/mo</span>
                        </div>
                      ))}
                    </div>
                  )}

                  {cost.notes.length > 0 && (
                    <ul className="mt-4 space-y-1 text-xs text-fg-dim">
                      {cost.notes.map((note, i) => (
                        <li key={i}>· {note}</li>
                      ))}
                    </ul>
                  )}
                </>
              ) : (
                <p className="text-sm text-fg-dim">
                  Cost estimate unavailable. Deploy will still be gated by your cap where possible.
                </p>
              )}
            </div>
          </Panel>
        </div>

        {/* Right column: terraform */}
        <Panel tone="solid" className="flex flex-col">
          <PanelHeader
            title="Terraform"
            subtitle="Generated infrastructure-as-code"
            right={
              dirty ? (
                <Button
                  variant="secondary"
                  size="sm"
                  loading={busy === 'save'}
                  onClick={saveEdits}
                >
                  Save changes
                </Button>
              ) : undefined
            }
          />
          {fileNames.length > 0 ? (
            <Tabs.Root
              value={activeTab}
              onValueChange={setActiveTab}
              className="flex flex-1 flex-col"
            >
              <Tabs.List className="flex gap-1 border-b border-line px-3">
                {fileNames.map((name) => (
                  <Tabs.Trigger
                    key={name}
                    value={name}
                    className={cn(
                      'relative rounded-sm px-3 py-2.5 font-mono text-xs text-fg-dim transition-colors duration-300 ease-quint hover:text-fg-muted',
                      'focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent/70',
                      'data-[state=active]:text-accent',
                      'data-[state=active]:after:absolute data-[state=active]:after:inset-x-2 data-[state=active]:after:bottom-0 data-[state=active]:after:h-px data-[state=active]:after:bg-accent',
                    )}
                  >
                    <ScrambleHover text={name} />
                  </Tabs.Trigger>
                ))}
              </Tabs.List>
              {fileNames.map((name) => (
                <Tabs.Content key={name} value={name} className="flex-1 p-3">
                  <textarea
                    spellCheck={false}
                    value={edited[name] ?? ''}
                    onChange={(e) => setEdited((prev) => ({ ...prev, [name]: e.target.value }))}
                    className="h-[28rem] w-full resize-none rounded-sm border border-line bg-black/70 p-4 font-mono text-[13px] leading-relaxed text-fg-muted focus:border-accent/50 focus:outline-none"
                  />
                </Tabs.Content>
              ))}
            </Tabs.Root>
          ) : (
            <p className="px-5 py-6 text-sm text-fg-dim">No Terraform generated.</p>
          )}
          <p className="border-t border-line px-4 py-2 text-[11px] text-fg-dim">
            Editing is optional. Saving validates your changes in place — the flow stays here, and
            the cost estimate can be refreshed.
          </p>
        </Panel>
      </Reveal>

      <Reveal>
        {error && <p className="mt-6 text-sm text-red-400">{error}</p>}

        <div className="mt-8 flex flex-wrap items-center gap-3">
          <Button size="lg" onClick={approve} loading={busy === 'approve'} disabled={busy !== null}>
            Approve & Deploy
          </Button>
          <Button
            variant="ghost"
            onClick={cancel}
            loading={busy === 'cancel'}
            disabled={busy !== null}
          >
            Cancel
          </Button>
          {demoMode && (
            <span className="text-xs text-fg-dim">
              Demo mode — deployment is simulated. No real cloud resources are created.
            </span>
          )}
        </div>
      </Reveal>
      </RevealGroup>
    </div>
  );
}

function SourceChip({ cost }: { cost: { source: string; confidence?: string } }) {
  return (
    <span className="rounded-pill border border-line px-3 py-1 font-mono text-[10px] uppercase tracking-[0.15em] text-fg-dim">
      {humanize(cost.source)}
      {cost.confidence ? ` · ${cost.confidence}` : ''}
    </span>
  );
}
