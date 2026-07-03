import { cn } from '../lib/utils';

interface CodeBlockProps {
  code: string;
  className?: string;
  /** Show line numbers in a gutter. */
  numbered?: boolean;
}

/** Read-only monospace code surface. */
export function CodeBlock({ code, className, numbered = false }: CodeBlockProps) {
  const lines = code.replace(/\n$/, '').split('\n');
  return (
    <pre
      className={cn(
        'overflow-auto rounded-sm border border-line bg-black/70 p-4 font-mono text-[13px] leading-relaxed text-fg-muted',
        className,
      )}
    >
      {numbered ? (
        <code className="grid grid-cols-[auto_1fr] gap-x-4">
          {lines.map((line, i) => (
            <div key={i} className="contents">
              <span className="select-none text-right text-fg-dim/60">{i + 1}</span>
              <span className="whitespace-pre">{line || ' '}</span>
            </div>
          ))}
        </code>
      ) : (
        <code>{code}</code>
      )}
    </pre>
  );
}
