import * as Dialog from '@radix-ui/react-dialog';
import { AnimatePresence, motion } from 'framer-motion';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import type { RunningInstance } from '../api/types';
import { useStore } from '../store/useStore';
import { Spinner } from './Spinner';
import { StatusDot } from './StatusDot';
import { Button } from './Button';
import { formatTimestamp } from '../lib/utils';
import { QUINT } from '../lib/motion';

function statusTone(status: string): 'good' | 'warn' | 'bad' | 'neutral' {
  const s = status.toUpperCase();
  if (s === 'RUNNING') return 'good';
  if (s === 'TERMINATED' || s === 'STOPPING') return 'bad';
  if (s === 'PROVISIONING' || s === 'STAGING') return 'warn';
  return 'neutral';
}

export function InventoryDialog() {
  const open = useStore((s) => s.inventoryOpen);
  const setOpen = useStore((s) => s.setInventoryOpen);
  const queryClient = useQueryClient();

  const inventory = useQuery({
    queryKey: ['inventory'],
    queryFn: api.getInventory,
    enabled: open,
    refetchOnWindowFocus: false,
  });

  const del = useMutation({
    mutationFn: ({ zone, name }: { zone: string; name: string }) =>
      api.deleteInstance(zone, name),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['inventory'] }),
  });

  const instances: RunningInstance[] = inventory.data?.instances ?? [];
  const available = inventory.data?.available ?? false;

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
                <div className="flex items-center justify-between border-b border-line px-6 py-4">
                  <div>
                    <Dialog.Title className="font-mono text-xs uppercase tracking-[0.2em] text-accent">
                      VM Inventory
                    </Dialog.Title>
                    <Dialog.Description className="mt-1 text-sm text-fg-dim">
                      Running instances in your GCP project.
                    </Dialog.Description>
                  </div>
                  <Dialog.Close className="rounded-pill border border-line px-3 py-1.5 text-xs text-fg-muted transition-colors hover:border-accent/60 hover:text-accent">
                    Close
                  </Dialog.Close>
                </div>

                <div className="max-h-[62vh] overflow-auto p-6">
                  {inventory.isLoading && (
                    <div className="flex items-center justify-center gap-3 py-16 text-fg-dim">
                      <Spinner /> Loading inventory…
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
                        Connect your OpenAI key and GCP service account in setup to list and
                        manage running VMs. Demo mode does not touch your cloud.
                      </p>
                    </div>
                  )}

                  {!inventory.isLoading && available && instances.length === 0 && (
                    <p className="py-14 text-center text-fg-dim">
                      No running instances found in this project.
                    </p>
                  )}

                  {available && instances.length > 0 && (
                    <table className="w-full border-collapse text-sm">
                      <thead>
                        <tr className="border-b border-line text-left font-mono text-[11px] uppercase tracking-[0.15em] text-fg-dim">
                          <th className="py-2 pr-4 font-normal">Name</th>
                          <th className="py-2 pr-4 font-normal">Zone</th>
                          <th className="py-2 pr-4 font-normal">Machine</th>
                          <th className="py-2 pr-4 font-normal">GPU</th>
                          <th className="py-2 pr-4 font-normal">Status</th>
                          <th className="py-2 pr-4 font-normal">External IP</th>
                          <th className="py-2 pr-4 font-normal">Created</th>
                          <th className="py-2" />
                        </tr>
                      </thead>
                      <tbody>
                        {instances.map((vm) => {
                          const pending =
                            del.isPending &&
                            del.variables?.name === vm.name &&
                            del.variables?.zone === vm.zone;
                          return (
                            <tr key={`${vm.zone}/${vm.name}`} className="border-b border-line/60">
                              <td className="py-3 pr-4 font-medium text-fg">{vm.name}</td>
                              <td className="py-3 pr-4 text-fg-muted">{vm.zone}</td>
                              <td className="py-3 pr-4 font-mono text-xs text-fg-muted">
                                {vm.machine_type}
                              </td>
                              <td className="py-3 pr-4 text-fg-muted">
                                {vm.gpu_summary || '—'}
                              </td>
                              <td className="py-3 pr-4">
                                <span className="inline-flex items-center gap-2 text-fg-muted">
                                  <StatusDot tone={statusTone(vm.status)} />
                                  {vm.status}
                                </span>
                              </td>
                              <td className="py-3 pr-4 font-mono text-xs text-fg-muted">
                                {vm.external_ip || '—'}
                              </td>
                              <td className="py-3 pr-4 text-xs text-fg-dim">
                                {formatTimestamp(vm.creation_timestamp)}
                              </td>
                              <td className="py-3 text-right">
                                <Button
                                  variant="danger"
                                  size="sm"
                                  loading={pending}
                                  onClick={() => del.mutate({ zone: vm.zone, name: vm.name })}
                                >
                                  Delete
                                </Button>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  )}

                  {del.isError && (
                    <p className="mt-4 text-sm text-red-400">{(del.error as Error).message}</p>
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
