import {writable} from 'svelte/store';

const {subscribe, update} = writable({
  hash: '',
  onHashChange(
    pattern: RegExp | string,
    matchedCallback: ParsedCallback,
    notMatchedCallback?: (hash: string) => unknown
  ) {
    console.log(this.hash);
    const match = this.hash.replace(/^#!/, '').match(pattern);
    if (match != null) {
      matchedCallback(match.groups || {});
    } else {
      if (notMatchedCallback != null) {
        notMatchedCallback(this.hash);
      }
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
