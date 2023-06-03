import {writable} from 'svelte/store';

const {subscribe, update} = writable({
  hash: '',
  onHashChange(pattern: RegExp | string, callback: ParsedCallback) {
    const match = this.hash.replace(/^#!/, '').match(pattern);
    if (match != null) {
      callback(match.groups || {});
    }
  }
});

export type ParsedCallback = (ctx: Record<string, string>) => void;

export const urlHash = {
  subscribe,
  set(hash: string) {
    update(state => {
      state.hash = hash;
      return state;
    });
  }
};
