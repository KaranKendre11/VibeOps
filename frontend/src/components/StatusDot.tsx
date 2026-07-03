import { cn } from '../lib/utils';

type Tone = 'good' | 'warn' | 'bad' | 'neutral';

const tones: Record<Tone, string> = {
  good: 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.9)]',
  warn: 'bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.9)]',
  bad: 'bg-red-400 shadow-[0_0_8px_rgba(248,113,113,0.9)]',
  neutral: 'bg-fg-dim',
};

export function StatusDot({ tone, className }: { tone: Tone; className?: string }) {
  return <span className={cn('inline-block h-2.5 w-2.5 rounded-full', tones[tone], className)} />;
}
