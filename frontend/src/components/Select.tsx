import * as RSelect from '@radix-ui/react-select';
import { cn } from '../lib/utils';

export interface SelectOption {
  value: string;
  label: string;
}

interface SelectProps {
  value: string | undefined;
  onChange: (value: string) => void;
  options: SelectOption[];
  placeholder?: string;
  disabled?: boolean;
  id?: string;
  className?: string;
}

export function Select({
  value,
  onChange,
  options,
  placeholder = 'Select…',
  disabled,
  id,
  className,
}: SelectProps) {
  return (
    <RSelect.Root value={value} onValueChange={onChange} disabled={disabled}>
      <RSelect.Trigger
        id={id}
        className={cn(
          'flex w-full items-center justify-between gap-3 rounded-sm border border-line bg-black/50 px-4 py-3 text-sm text-fg',
          'transition-colors focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent/60',
          'data-[placeholder]:text-fg-dim disabled:opacity-50',
          className,
        )}
      >
        <RSelect.Value placeholder={placeholder} />
        <RSelect.Icon className="text-accent">▾</RSelect.Icon>
      </RSelect.Trigger>
      <RSelect.Portal>
        <RSelect.Content
          position="popper"
          sideOffset={6}
          className="glass-2 z-50 max-h-72 min-w-[var(--radix-select-trigger-width)] overflow-hidden rounded-sm"
        >
          <RSelect.Viewport className="p-1">
            {options.map((opt) => (
              <RSelect.Item
                key={opt.value}
                value={opt.value}
                className={cn(
                  'relative flex cursor-pointer select-none items-center rounded-sm px-3 py-2 text-sm text-fg-muted outline-none',
                  'data-[highlighted]:bg-accent/15 data-[highlighted]:text-accent data-[state=checked]:text-accent',
                )}
              >
                <RSelect.ItemText>{opt.label}</RSelect.ItemText>
              </RSelect.Item>
            ))}
          </RSelect.Viewport>
        </RSelect.Content>
      </RSelect.Portal>
    </RSelect.Root>
  );
}
