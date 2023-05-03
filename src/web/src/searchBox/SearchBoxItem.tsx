import {Command} from 'cmdk';
import * as React from 'react';

export function SearchBoxItem({
  children,
  shortcut,
  onSelect = () => {
    return;
  },
  disabled,
}: {
  children: React.ReactNode;
  shortcut?: string;
  onSelect?: (value: string) => void;
  disabled?: boolean;
}) {
  return (
    <Command.Item
      onSelect={onSelect}
      disabled={disabled}
      style={{color: disabled ? 'var(--sl-color-gray-500)' : ''}}
    >
      {children}
      {shortcut && (
        <div data-cmdk-shortcuts>
          {shortcut.split(' ').map((key) => {
            return <kbd key={key}>{key}</kbd>;
          })}
        </div>
      )}
    </Command.Item>
  );
}
