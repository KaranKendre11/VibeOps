import * as Dialog from '@radix-ui/react-dialog';
import { AnimatePresence, motion } from 'framer-motion';
import { Button } from './Button';
import { QUINT } from '../lib/motion';

interface ConfirmNavProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
}

/**
 * Small guarded-navigation confirmation. Used by the progress rail when going
 * back to an earlier stage could discard/regenerate work. Focus-trapped and
 * Esc-dismissible via Radix Dialog; closing (overlay/Esc/Cancel) = stay put.
 */
export function ConfirmNav({
  open,
  title,
  message,
  confirmLabel = 'Continue',
  onConfirm,
  onCancel,
}: ConfirmNavProps) {
  return (
    <Dialog.Root
      open={open}
      onOpenChange={(next) => {
        if (!next) onCancel();
      }}
    >
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
                className="surface-solid fixed left-1/2 top-1/2 z-50 w-[min(92vw,28rem)] -translate-x-1/2 -translate-y-1/2 rounded-md p-6"
                initial={{ opacity: 0, scale: 0.96, y: '-46%', x: '-50%' }}
                animate={{ opacity: 1, scale: 1, y: '-50%', x: '-50%' }}
                exit={{ opacity: 0, scale: 0.96 }}
                transition={{ duration: 0.24, ease: QUINT }}
              >
                <Dialog.Title className="font-mono text-xs uppercase tracking-[0.2em] text-accent">
                  {title}
                </Dialog.Title>
                <Dialog.Description className="mt-3 text-sm leading-relaxed text-fg-muted">
                  {message}
                </Dialog.Description>
                <div className="mt-6 flex justify-end gap-3">
                  <Button variant="ghost" size="sm" onClick={onCancel}>
                    Stay here
                  </Button>
                  <Button variant="secondary" size="sm" onClick={onConfirm}>
                    {confirmLabel}
                  </Button>
                </div>
              </motion.div>
            </Dialog.Content>
          </Dialog.Portal>
        )}
      </AnimatePresence>
    </Dialog.Root>
  );
}
