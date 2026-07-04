import { useState } from 'react';
import type { ReactNode } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { AnimatePresence, motion } from 'framer-motion';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import type { CustomImage, Disk, Network, RunningInstance } from '../api/types';
import { useStore } from '../store/useStore';
import { Spinner } from './Spinner';
import { StatusDot } from './StatusDot';
import { Button } from './Button';
import { cn, formatTimestamp, usd } from '../lib/utils';
import { QUINT } from '../lib/motion';

type TabKey = 'instances' | 'disks' | 'images' | 'networks';

function statusTone(status: string): 'good' | 'warn' | 'bad' | 'neutral' {
  const s = status.toUpperCase();
  if (s === 'RUNNING' || s === 'READY') return 'good';
  if (s === 'TERMINATED' || s === 'STOPPING' || s === 'FAILED') return 'bad';
  if (s === 'PROVISIONING' || s === 'STAGING' || s === 'PENDING' || s === 'CREATING') return 'warn';
  return 'neutral';
}

/** Format a per-resource monthly cost, or "—" when it can't be estimated. */
function costLabel(c: number | null | undefined): string {
  return c == null ? '—' : `${usd(c, { cents: true })}/mo`;
}

const TH = 'py-2 pr-4 font-normal';
const THEAD_ROW =
  'border-b border-line text-left font-mono text-[11px] uppercase tracking-[0.15em] text-fg-dim';

function Empty({ children }: { children: ReactNode }) {
  return <p className="py-14 text-center text-fg-dim">{children}</p>;
}

function StatusCell({ status }: { status: string }) {
  return (
    <td className="py-3 pr-4">
      <span className="inline-flex items-center gap-2 text-fg-muted">
        <StatusDot tone={statusTone(status)} />
        {status || '—'}
      </span>
    </td>
  );
}

function CostCell({ value }: { value: number | null | undefined }) {
  return <td className="py-3 pr-4 font-mono text-xs text-fg-muted">{costLabel(value)}</td>;
}

function DeleteCell({ pending, onClick }: { pending: boolean; onClick: () => void }) {
  return (
    <td className="py-3 text-right">
      <Button variant="danger" size="sm" loading={pending} onClick={onClick}>
        Delete
      </Button>
    </td>
  );
}

export function InventoryDialog() {
  const open = useStore((s) => s.inventoryOpen);
  const setOpen = useStore((s) => s.setInventoryOpen);
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<TabKey>('instances');

  const inventory = useQuery({
    queryKey: ['inventory'],
    queryFn: api.getInventory,
    enabled: open,
    refetchOnWindowFocus: false,
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['inventory'] });

  const delInstance = useMutation({
    mutationFn: ({ zone, name }: { zone: string; name: string }) => api.deleteInstance(zone, name),
    onSuccess: invalidate,
  });
  const delDisk = useMutation({
    mutationFn: ({ zone, name }: { zone: string; name: string }) => api.deleteDisk(zone, name),
    onSuccess: invalidate,
  });
  const delImage = useMutation({
    mutationFn: ({ name }: { name: string }) => api.deleteImage(name),
    onSuccess: invalidate,
  });
  const delNetwork = useMutation({
    mutationFn: ({ name }: { name: string }) => api.deleteNetwork(name),
    onSuccess: invalidate,
  });

  const instances: RunningInstance[] = inventory.data?.instances ?? [];
  const disks: Disk[] = inventory.data?.disks ?? [];
  const images: CustomImage[] = inventory.data?.images ?? [];
  const networks: Network[] = inventory.data?.networks ?? [];
  const available = inventory.data?.available ?? false;

  // Total estimated monthly cost = sum of estimable (non-null) instance + disk costs.
  const totalCost = [...instances, ...disks].reduce((s, r) => s + (r.monthly_cost_usd ?? 0), 0);

  const mutError = (delInstance.error ??
    delDisk.error ??
    delImage.error ??
    delNetwork.error) as Error | undefined;

  const tabs: { key: TabKey; label: string; count: number }[] = [
    { key: 'instances', label: 'Instances', count: instances.length },
    { key: 'disks', label: 'Disks', count: disks.length },
    { key: 'images', label: 'Images', count: images.length },
    { key: 'networks', label: 'Networks', count: networks.length },
  ];

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <AnimatePresence>
        {open && (
          <Dialog.Portal forceMount>
            <Dialog.Overlay asChild forceMount>
              <motion.div
                className="fixed inset-0 z-40 bg-black/70 backdrop-blur-sm"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              />
            </Dialog.Overlay>
            <Dialog.Content asChild forceMount>
              <motion.div
                className="surface-solid fixed left-1/2 top-1/2 z-50 w-[min(92vw,64rem)] -translate-x-1/2 -translate-y-1/2 rounded-md"
                initial={{ opacity: 0, scale: 0.96, y: '-46%', x: '-50%' }}
                animate={{ opacity: 1, scale: 1, y: '-50%', x: '-50%' }}
                exit={{ opacity: 0, scale: 0.96 }}
                transition={{ duration: 0.28, ease: QUINT }}
              >
                <div className="flex items-center justify-between gap-4 border-b border-line px-6 py-4">
                  <div>
                    <Dialog.Title className="font-mono text-xs uppercase tracking-[0.2em] text-accent">
                      Cloud resources
                    </Dialog.Title>
                    <Dialog.Description className="mt-1 text-sm text-fg-dim">
                      Compute Engine resources in your GCP project — with estimated monthly cost.
                    </Dialog.Description>
                  </div>
                  <div className="flex items-center gap-3">
                    {available && (
                      <div
                        className="rounded-md border border-line px-3 py-1.5 text-right"
                        title="Sum of estimable instance + disk costs"
                      >
                        <div className="font-mono text-[10px] uppercase tracking-[0.15em] text-fg-dim">
                          Est. total
                        </div>
                        <div className="font-mono text-sm text-accent">
                          {usd(totalCost, { cents: true })}/mo
                        </div>
                      </div>
                    )}
                    <Dialog.Close className="rounded-pill border border-line px-3 py-1.5 text-xs text-fg-muted transition-colors hover:border-accent/60 hover:text-accent">
                      Close
                    </Dialog.Close>
                  </div>
                </div>

                {/* Tab bar */}
                {available && (
                  <div className="flex items-center gap-1 border-b border-line px-4 pt-3">
                    {tabs.map((t) => (
                      <button
                        key={t.key}
                        onClick={() => setTab(t.key)}
                        className={cn(
                          'rounded-t-sm px-4 py-2 text-xs transition-colors',
                          tab === t.key
                            ? 'border-b-2 border-accent text-accent'
                            : 'border-b-2 border-transparent text-fg-muted hover:text-fg',
                        )}
                      >
                        {t.label}
                        <span className="ml-2 font-mono text-[10px] text-fg-dim">{t.count}</span>
                      </button>
                    ))}
                  </div>
                )}

                <div className="max-h-[56vh] overflow-auto p-6">
                  {inventory.isLoading && (
                    <div className="flex items-center justify-center gap-3 py-16 text-fg-dim">
                      <Spinner /> Loading resources…
                    </div>
                  )}

                  {inventory.isError && (
                    <p className="py-12 text-center text-red-400">
                      {(inventory.error as Error).message}
                    </p>
                  )}

                  {!inventory.isLoading && !inventory.isError && !available && (
                    <div className="rounded-md border border-dashed border-line px-6 py-14 text-center">
                      <p className="text-fg-muted">No live GCP connection.</p>
                      <p className="mx-auto mt-2 max-w-md text-sm text-fg-dim">
                        Connect your OpenAI key and GCP service account in setup to list and manage
                        your cloud resources. Demo mode does not touch your cloud.
                      </p>
                    </div>
                  )}

                  {!inventory.isLoading && available && (
                    <>
                      {tab === 'instances' &&
                        (instances.length === 0 ? (
                          <Empty>No instances in this project.</Empty>
                        ) : (
                          <table className="w-full border-collapse text-sm">
                            <thead>
                              <tr className={THEAD_ROW}>
                                <th className={TH}>Name</th>
                                <th className={TH}>Zone</th>
                                <th className={TH}>Machine</th>
                                <th className={TH}>GPU</th>
                                <th className={TH}>Status</th>
                                <th className={TH}>External IP</th>
                                <th className={TH}>Created</th>
                                <th className={TH}>Cost/mo</th>
                                <th className="py-2" />
                              </tr>
                            </thead>
                            <tbody>
                              {instances.map((vm) => {
                                const pending =
                                  delInstance.isPending &&
                                  delInstance.variables?.name === vm.name &&
                                  delInstance.variables?.zone === vm.zone;
                                return (
                                  <tr
                                    key={`${vm.zone}/${vm.name}`}
                                    className="border-b border-line/60"
                                  >
                                    <td className="py-3 pr-4 font-medium text-fg">{vm.name}</td>
                                    <td className="py-3 pr-4 text-fg-muted">{vm.zone}</td>
                                    <td className="py-3 pr-4 font-mono text-xs text-fg-muted">
                                      {vm.machine_type}
                                    </td>
                                    <td className="py-3 pr-4 text-fg-muted">
                                      {vm.gpu_summary || '—'}
                                    </td>
                                    <StatusCell status={vm.status} />
                                    <td className="py-3 pr-4 font-mono text-xs text-fg-muted">
                                      {vm.external_ip || '—'}
                                    </td>
                                    <td className="py-3 pr-4 text-xs text-fg-dim">
                                      {formatTimestamp(vm.creation_timestamp)}
                                    </td>
                                    <CostCell value={vm.monthly_cost_usd} />
                                    <DeleteCell
                                      pending={pending}
                                      onClick={() =>
                                        delInstance.mutate({ zone: vm.zone, name: vm.name })
                                      }
                                    />
                                  </tr>
                                );
                              })}
                            </tbody>
                          </table>
                        ))}

                      {tab === 'disks' &&
                        (disks.length === 0 ? (
                          <Empty>No persistent disks in this project.</Empty>
                        ) : (
                          <table className="w-full border-collapse text-sm">
                            <thead>
                              <tr className={THEAD_ROW}>
                                <th className={TH}>Name</th>
                                <th className={TH}>Zone</th>
                                <th className={TH}>Type</th>
                                <th className={TH}>Size</th>
                                <th className={TH}>Attached to</th>
                                <th className={TH}>Status</th>
                                <th className={TH}>Cost/mo</th>
                                <th className="py-2" />
                              </tr>
                            </thead>
                            <tbody>
                              {disks.map((d) => {
                                const pending =
                                  delDisk.isPending &&
                                  delDisk.variables?.name === d.name &&
                                  delDisk.variables?.zone === d.zone;
                                return (
                                  <tr
                                    key={`${d.zone}/${d.name}`}
                                    className="border-b border-line/60"
                                  >
                                    <td className="py-3 pr-4 font-medium text-fg">{d.name}</td>
                                    <td className="py-3 pr-4 text-fg-muted">{d.zone}</td>
                                    <td className="py-3 pr-4 font-mono text-xs text-fg-muted">
                                      {d.type || '—'}
                                    </td>
                                    <td className="py-3 pr-4 text-fg-muted">{d.size_gb} GB</td>
                                    <td className="py-3 pr-4 font-mono text-xs text-fg-muted">
                                      {d.users && d.users.length > 0 ? d.users.join(', ') : '—'}
                                    </td>
                                    <StatusCell status={d.status ?? ''} />
                                    <CostCell value={d.monthly_cost_usd} />
                                    <DeleteCell
                                      pending={pending}
                                      onClick={() =>
                                        delDisk.mutate({ zone: d.zone, name: d.name })
                                      }
                                    />
                                  </tr>
                                );
                              })}
                            </tbody>
                          </table>
                        ))}

                      {tab === 'images' &&
                        (images.length === 0 ? (
                          <Empty>No custom images in this project.</Empty>
                        ) : (
                          <table className="w-full border-collapse text-sm">
                            <thead>
                              <tr className={THEAD_ROW}>
                                <th className={TH}>Name</th>
                                <th className={TH}>Family</th>
                                <th className={TH}>Size</th>
                                <th className={TH}>Status</th>
                                <th className={TH}>Created</th>
                                <th className={TH}>Cost/mo</th>
                                <th className="py-2" />
                              </tr>
                            </thead>
                            <tbody>
                              {images.map((img) => {
                                const pending =
                                  delImage.isPending && delImage.variables?.name === img.name;
                                return (
                                  <tr key={img.name} className="border-b border-line/60">
                                    <td className="py-3 pr-4 font-medium text-fg">{img.name}</td>
                                    <td className="py-3 pr-4 text-fg-muted">{img.family || '—'}</td>
                                    <td className="py-3 pr-4 text-fg-muted">
                                      {img.disk_size_gb} GB
                                    </td>
                                    <StatusCell status={img.status ?? ''} />
                                    <td className="py-3 pr-4 text-xs text-fg-dim">
                                      {formatTimestamp(img.creation_timestamp)}
                                    </td>
                                    <CostCell value={img.monthly_cost_usd} />
                                    <DeleteCell
                                      pending={pending}
                                      onClick={() => delImage.mutate({ name: img.name })}
                                    />
                                  </tr>
                                );
                              })}
                            </tbody>
                          </table>
                        ))}

                      {tab === 'networks' &&
                        (networks.length === 0 ? (
                          <Empty>No VPC networks in this project.</Empty>
                        ) : (
                          <table className="w-full border-collapse text-sm">
                            <thead>
                              <tr className={THEAD_ROW}>
                                <th className={TH}>Name</th>
                                <th className={TH}>Subnet mode</th>
                                <th className={TH}>Cost/mo</th>
                                <th className="py-2" />
                              </tr>
                            </thead>
                            <tbody>
                              {networks.map((n) => {
                                const pending =
                                  delNetwork.isPending && delNetwork.variables?.name === n.name;
                                return (
                                  <tr key={n.name} className="border-b border-line/60">
                                    <td className="py-3 pr-4 font-medium text-fg">{n.name}</td>
                                    <td className="py-3 pr-4 text-fg-muted">
                                      {n.auto_create_subnetworks ? 'auto' : 'custom'}
                                    </td>
                                    <CostCell value={null} />
                                    <DeleteCell
                                      pending={pending}
                                      onClick={() => delNetwork.mutate({ name: n.name })}
                                    />
                                  </tr>
                                );
                              })}
                            </tbody>
                          </table>
                        ))}
                    </>
                  )}

                  {mutError && <p className="mt-4 text-sm text-red-400">{mutError.message}</p>}

                  {available && (
                    <p className="mt-6 border-t border-line/60 pt-4 text-xs text-fg-dim">
                      Cost is an estimate from a maintained GCP price snapshot; images and networks
                      are usage/egress-based and shown as “—”. Deleting here acts directly on GCP,
                      outside Terraform state.
                    </p>
                  )}
                </div>
              </motion.div>
            </Dialog.Content>
          </Dialog.Portal>
        )}
      </AnimatePresence>
    </Dialog.Root>
  );
}
