import type { InputHTMLAttributes, ReactNode, TextareaHTMLAttributes } from 'react';
import { cn } from '../lib/utils';

const controlBase =
  'w-full rounded-sm border border-line bg-black/50 px-4 py-3 text-sm text-fg placeholder:text-fg-dim ' +
  'transition-colors focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent/60';

export function Label({ children, htmlFor }: { children: ReactNode; htmlFor?: string }) {
  return (
    <label
      htmlFor={htmlFor}
      className="mb-2 block font-mono text-[11px] uppercase tracking-[0.18em] text-fg-dim"
    >
      {children}
    </label>
  );
}

export function TextInput({ className, ...rest }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn(controlBase, className)} {...rest} />;
}

export function TextArea({ className, ...rest }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cn(controlBase, 'resize-y', className)} {...rest} />;
}

export function FieldError({ children }: { children: ReactNode }) {
  if (!children) return null;
  return <p className="mt-2 text-sm text-red-400">{children}</p>;
}

export function FieldHint({ children }: { children: ReactNode }) {
  return <p className="mt-2 text-xs text-fg-dim">{children}</p>;
}
