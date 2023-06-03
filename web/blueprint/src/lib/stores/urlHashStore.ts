import {writable} from 'svelte/store';

export const urlHash = writable('');

export type ParsedCallback = (ctx: Record<string, string>) => void;

export function parseHash(hash: string, pattern: RegExp | string, callback: ParsedCallback) {
  const match = hash.replace(/^#!/, '').match(pattern);
  if (match != null) {
    callback(match.groups || {});
  }
}
