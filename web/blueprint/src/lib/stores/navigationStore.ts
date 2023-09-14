import {isMobile} from '$lilac';
import {getContext, hasContext, setContext} from 'svelte';
import {writable} from 'svelte/store';

const NAVIGATION_CONTEXT = 'NAVIGATION_CONTEXT';

export type NavigationStore = ReturnType<typeof createNavigationStore>;

export interface NavigationState {
  open: boolean;
}
export function createNavigationStore() {
  return writable<NavigationState>({open: !isMobile()});
}

export function setNavigationContext(store: NavigationStore) {
  setContext(NAVIGATION_CONTEXT, store);
}

export function getNavigationContext(): NavigationStore {
  if (!hasContext(NAVIGATION_CONTEXT)) throw new Error('NavigationContext not found');
  return getContext<NavigationStore>(NAVIGATION_CONTEXT);
}
