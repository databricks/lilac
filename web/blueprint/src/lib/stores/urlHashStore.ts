import {mergeDeep} from '$lilac';
import {getContext, hasContext, setContext} from 'svelte';
import {writable, type Writable} from 'svelte/store';

export type AppPage =
  | 'home'
  | 'concepts'
  | 'datasets'
  | 'signals'
  | 'settings'
  | 'datasets/loading'
  | 'rag';
interface UrlHashState {
  hash: string;
  page: AppPage | null;
  // The sub-page identifier, e.g. local/movies.
  identifier: string | null;
  // The sub-page serialized state.
  hashState: string | null;
}

export type UrlHashStateStore = ReturnType<typeof createUrlHashStore>;
export type PageStateCallback = (page: AppPage) => void;

const URL_HASH_CONTEXT = 'URL_HASH_CONTEXT';

export function createUrlHashStore() {
  const {subscribe, update} = writable<UrlHashState>({
    hash: '',
    page: null,
    identifier: null,
    hashState: null
  });

  return {
    subscribe,
    setHash(page: AppPage, hash: string) {
      update(state => {
        const [identifier, ...hashStateValues] = hash.slice(1).split('&');
        state.page = page;
        state.hash = hash;
        state.identifier = identifier;
        state.hashState = hashStateValues.join('&');
        return state;
      });
    }
  };
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function pushState(identifier: string, hashState: string) {
  const hash = `#${identifier}` + (hashState != '' ? `&${hashState}` : '');
  // Sometimes state can be double rendered, so to avoid that at all costs we check the existing
  // hash before pushing a new one.
  if (hash != location.hash) {
    history.pushState(null, '', hash);
  }
}

export function setUrlHashContext(store: UrlHashStateStore) {
  setContext(URL_HASH_CONTEXT, store);
}

export function getUrlHashContext() {
  if (!hasContext(URL_HASH_CONTEXT)) throw new Error('UrlHashStoreContext not found');
  return getContext<UrlHashStateStore>(URL_HASH_CONTEXT);
}

function removeDefaultValues(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  state: Record<string, any>,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  defaultState: Record<string, any>
) {
  const keys = Object.keys(state);
  for (const stateKey of keys) {
    const stateValue = state[stateKey];
    const defaultStateValue = defaultState[stateKey];
    const jsonValue = JSON.stringify(stateValue);
    const defaultJsonValue = JSON.stringify(defaultStateValue);
    if (jsonValue == defaultJsonValue) {
      delete state[stateKey];
    }
    if (typeof stateValue === 'object') {
      if (defaultStateValue != null && stateValue != null) {
        removeDefaultValues(stateValue, defaultStateValue);
      }
    }
  }
}
/**
 * Serialize an object state for the URL.
 */
export function serializeState(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  state: Record<string, any>,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  defaultState: Record<string, any>
): string {
  // Deep copy the state so we don't modify the callers state.
  state = JSON.parse(JSON.stringify(state));
  removeDefaultValues(state, defaultState);
  const flatFields: [string, string][] = [];
  for (const stateKey of Object.keys(state)) {
    const jsonValue = JSON.stringify(state[stateKey]);
    flatFields.push([stateKey, jsonValue]);
  }
  return flatFields
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`)
    .join('&');
}

/**
 * Deserialize a URL to a store.
 */
export function deserializeState(
  stateString: string | null,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  defaultState: any | null
) {
  // Deep copy the default state as we modify this object and return it.
  defaultState = JSON.parse(JSON.stringify(defaultState));
  if (stateString == null || stateString == '') return defaultState;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const urlState: Record<string, any> = {};
  const params = (stateString || '').split('&');
  // Override with URL params.
  for (const param of params) {
    if (param == null) continue;
    const [key, value] = param.split('=');
    urlState[decodeURIComponent(key)] = JSON.parse(decodeURIComponent(value));
  }
  return mergeDeep(urlState, defaultState);
}

/**
 * Subscribes to the store and serializes it toe the URL.
 */
export function persistedHashStore<T extends object>(
  page: string,
  identifier: string,
  store: Writable<T>,
  urlHashStore: UrlHashStateStore,
  stateFromHash: (hashState: string) => T,
  hashFromState: (state: T) => string,
  // Calls the user back when a load from the URL happens.
  loadFromUrlCallback?: () => void
) {
  // Skip the first update which happens on store initialization.
  let skipUpdate = true;
  urlHashStore.subscribe(urlHashState => {
    if (urlHashState.page === page && urlHashState.identifier === identifier) {
      // Skip the URL update when the state change came from the URL.
      skipUpdate = true;

      // The original store needs to be updated so it reflects the changes from the URL.
      store.set(stateFromHash(urlHashState.hashState!));

      if (loadFromUrlCallback) {
        loadFromUrlCallback();
      }
    }
  });

  store.subscribe(state => {
    if (state == null) return;
    if (!skipUpdate) {
      pushState(identifier, hashFromState(state));
    }
    skipUpdate = false;
  });
}
