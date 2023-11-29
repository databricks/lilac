import {isMobile} from '$lilac';
import {getContext, hasContext, setContext} from 'svelte';
import {writable} from 'svelte/store';
export const NAV_STORE_KEY = 'nav';

const NAVIGATION_CONTEXT = 'NAVIGATION_CONTEXT';

export type NavigationStore = ReturnType<typeof createNavigationStore>;

export interface NavigationState {
  open: boolean;
}
export function defaultNavigationState() {
  return {open: !isMobile()};
}
export function createNavigationStore() {
  return writable<NavigationState>(defaultNavigationState());
}

export function setNavigationContext(store: NavigationStore) {
  setContext(NAVIGATION_CONTEXT, store);
}

export function getNavigationContext(): NavigationStore {
  if (!hasContext(NAVIGATION_CONTEXT)) throw new Error('NavigationContext not found');
  return getContext<NavigationStore>(NAVIGATION_CONTEXT);
}
