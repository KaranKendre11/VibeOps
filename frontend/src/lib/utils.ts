import { clsx, type ClassValue } from 'clsx';

/** Merge conditional class names. */
export function cn(...inputs: ClassValue[]): string {
  return clsx(inputs);
}

/** Format a USD amount with sensible precision. */
export function usd(value: number | null | undefined, opts?: { cents?: boolean }): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  const digits = opts?.cents ? 2 : value < 10 ? 2 : 0;
  return `$${value.toLocaleString('en-US', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })}`;
}

/** Human-friendly key from a snake_case / camelCase field. */
export function humanize(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/** GPU machine-id -> short label, best effort. */
export function gpuLabel(gpu: string | undefined | null): string {
  if (!gpu) return '';
  const map: Record<string, string> = {
    'nvidia-tesla-t4': 'NVIDIA T4',
    'nvidia-l4': 'NVIDIA L4',
    'nvidia-tesla-a100': 'NVIDIA A100',
    'nvidia-a100-80gb': 'NVIDIA A100 80GB',
  };
  return map[gpu] ?? gpu.replace(/^nvidia-/, 'NVIDIA ').replace(/-/g, ' ');
}

/** Choose a status tone from remaining/total quota. */
export function quotaTone(
  remaining: number,
  total: number,
): 'good' | 'warn' | 'bad' | 'neutral' {
  if (total <= 0) return 'neutral';
  const ratio = remaining / total;
  if (ratio <= 0) return 'bad';
  if (ratio < 0.34) return 'warn';
  return 'good';
}

/** Relative-ish timestamp formatting for inventory rows. */
export function formatTimestamp(ts: string | undefined): string {
  if (!ts) return '—';
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return ts;
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}
