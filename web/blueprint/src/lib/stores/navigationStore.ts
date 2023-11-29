import {isMobile} from '$lilac';
import {getContext, hasContext, setContext} from 'svelte';
import {writable} from 'svelte/store';
export const NAV_STORE_KEY = 'nav';

const NAVIGATION_CONTEXT = 'NAVIGATION_CONTEXT';

export type NavigationStore = ReturnType<typeof createNavigationStore>;

export interface NavigationState {
  open: boolean;
  expanded: {[key: string]: boolean};
}
export function defaultNavigationState() {
  return {open: !isMobile(), expanded: {}};
}
export function createNavigationStore() {
  const {subscribe, update, set} = writable<NavigationState>(defaultNavigationState());
  return {
    subscribe,
    update,
    set,
    toggleExpanded(key: string) {
      update(state => {
        state.expanded[key] = !(state.expanded[key] == null ? true : state.expanded[key]);
        return state;
      });
    }
  };
}
export function setNavigationContext(store: NavigationStore) {
  setContext(NAVIGATION_CONTEXT, store);
}

export function getNavigationContext(): NavigationStore {
  if (!hasContext(NAVIGATION_CONTEXT)) throw new Error('NavigationContext not found');
  return getContext<NavigationStore>(NAVIGATION_CONTEXT);
}
