import { cn } from '../lib/utils';

export function Spinner({ className }: { className?: string }) {
  return (
    <span
      role="status"
      aria-label="Loading"
      className={cn(
        'inline-block h-5 w-5 animate-spin rounded-full border-2 border-accent/30 border-t-accent',
        className,
      )}
    />
  );
}
