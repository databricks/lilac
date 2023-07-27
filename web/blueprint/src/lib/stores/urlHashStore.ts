import {mergeDeep} from '$lilac';
import {getContext, hasContext, setContext} from 'svelte';
import {derived, writable, type Readable, type Writable} from 'svelte/store';
import type {DatasetViewState} from './datasetViewStore';

export type AppPage = 'home' | 'concepts' | 'datasets' | 'settings';
interface AppState {
  hash: string;
  // updateSubscribers: boolean;
  page: AppPage | null;
  identifier: string | null;
  hashState: string | null;
  datasetViewState: DatasetViewState | null;
  // initializePage: (appPage: AppPage) => unknown;
  onUrlChange: (
    page: AppPage,
    identifier: string | null,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    defaultState: any,
    callback: ParsedCallback
  ) => void;
}

export type AppStateStore = ReturnType<typeof createAppStore>;
export type PageStateCallback = (page: AppPage) => void;

const APP_CONTEXT = 'APP_CONTEXT';

export type ParsedCallback = (identifier: string, hashState: string) => void;

export function createAppStore() {
  const {subscribe, update} = writable<AppState>({
    hash: '',
    // updateSubscribers: false,
    page: null,
    identifier: null,
    hashState: null,
    datasetViewState: null,
    onUrlChange(
      page: AppPage,
      identifier: string | null,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      defaultState: any,
      callback: ParsedCallback
    ) {
      // if (!this.updateSubscribers) return;
      if (this.page != page) return;
      // Remove the '#'.
      const hash = this.hash.slice(1);
      const [hashIdentifier, hashState] = hash.split('&', 2);
      if (identifier != null && hashIdentifier != identifier) return;

      // const state = deserializeState(stateHash, defaultState);
      callback(hashIdentifier, hashState);
    }
  });

  return {
    subscribe,
    setHash(page: AppPage, hash: string) {
      update(state => {
        state.page = page;
        state.hash = hash;

        // Update the page, identifier so subscribers can listen.

        // Remove the '#'.
        // const [identifier, hashState] = hash.slice(1).split('&', 2);
        const [identifier, ...hashStateValues] = hash.slice(1).split('&');
        console.log('...hashy', hash.slice(1).split('&'), identifier, hashStateValues);
        state.identifier = identifier;
        state.hashState = hashStateValues.join('&');
        console.log('urlHashStore.setHash called', state.page, state.identifier, state.hashState);

        // state.updateSubscribers = true;
        return state;
      });
    }
  };
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function pushState(identifier: string, hashState: string) {
  const hash = `#${identifier}` + (hashState != '' ? `&${hashState}` : '');
  console.log('pushState', identifier, 'new hash', hash, 'current hash', location.hash);
  // Sometimes state can be double rendered, so to avoid that at all costs we check the existing
  // hash before pushing a new one.
  if (hash != location.hash) {
    console.log('pushState: change', location.hash, '=>', hash);
    history.pushState(null, '', hash);
  }
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function pushState2(identifier: string, state: any, defaultState: any = {}) {
  const serializedState = serializeState(state, defaultState);
  const hash = `#${identifier}` + (serializedState != '' ? `&${serializedState}` : '');
  console.log('pushState', identifier, 'new hash', hash, 'current hash', location.hash);
  // Sometimes state can be double rendered, so to avoid that at all costs we check the existing
  // hash before pushing a new one.
  if (hash != location.hash) {
    console.log('pushState: change', location.hash, '=>', hash);
    history.pushState(null, '', hash);
  }
}

export function setAppStoreContext(store: AppStateStore) {
  setContext(APP_CONTEXT, store);
}

export function getAppStoreContext() {
  if (!hasContext(APP_CONTEXT)) throw new Error('AppStateContext not found');
  return getContext<AppStateStore>(APP_CONTEXT);
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
  return flatFields.map(([key, value]) => `${key}=${value}`).join('&');
}

/**
 * When the key contains a period, we have to quote it to preserve the object structure.
 */
function getSerializableKey(key: string): string {
  if (key.includes('.')) {
    return `"${key}"`;
  }
  return key;
}

export function flattenFields(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  json: any,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  defaultState: any,
  prefixes: string[] = []
): [string, string][] {
  const flatFields: [string, string][] = [];
  for (const [key, value] of Object.entries(json)) {
    const serializableKey = getSerializableKey(key);
    const defaultValue = (defaultState || {})[key];
    if (value == null) continue;
    if (Array.isArray(value)) {
      console.log('is array', value);
      if (((value as []) || []).every((v, i) => v === (defaultValue || [])[i])) continue;
      console.log('not default');
      //flatFields.push([prefixes.concat(serializableKey).join('.'), value.join(',')]);
    }
    if (typeof value === 'object') {
      flatFields.push(...flattenFields(value, defaultValue, [...prefixes, serializableKey]));
    } else {
      if (value == defaultValue) continue;
      flatFields.push([prefixes.concat(serializableKey).join('.'), `${value}`]);
    }
  }
  console.log(flatFields);
  return flatFields;
}

/**
 * Deserialize a URL to a store.
 */
export function deserializeState(
  stateString: string | null,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  defaultState: any | null
) {
  defaultState = defaultState != null ? JSON.parse(JSON.stringify(defaultState)) : {};
  if (stateString == null) return defaultState;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const urlState: Record<string, any> = {};
  console.log('ss', stateString);
  const params = (decodeURIComponent(stateString) || '').split('&');
  // Override with URL params.
  for (const param of params) {
    if (param == null) continue;
    const [key, value] = param.split('=');
    console.log('key=', key, value);
    urlState[key] = JSON.parse(value);
  }
  console.log('url state=', urlState);
  const merged = mergeDeep(defaultState, urlState);
  console.log('merged=', merged);
  return merged;
}

export interface UrlStoreState {
  // Whether an update came from the URL. When true, the original store subscribers will not be
  // called.
  fromUrl: boolean;
  hashState: string | null;
  // storeState: T;
}
export function createURLStore<T extends object>(
  page: string,
  identifier: string,
  store: Writable<T>,
  appStore: AppStateStore,
  stateFromHash: (hashState: string) => T,
  hashFromState: (state: T) => string
): Writable<T> {
  const urlStore = writable<UrlStoreState>(
    // Deep copy the initial state so we don't have to worry about mucking the initial state.
    {fromUrl: false, hashState: null}
  );

  appStore.subscribe(appState => {
    // App store URL changed.
    console.log(
      'setting from url [appstorechange] = true',
      appState.page,
      appState.identifier,
      appState.hashState
    );

    console.log('appStore url change subscribe');
    if (appState.page === page && appState.identifier === identifier) {
      urlStore.set({fromUrl: true, hashState: appState.hashState});
    }
  });

  // When the URL changes, set from URL = false, and update the state directly.
  // onUrlChange('datasets', identifier, defaultState, (identifier, stateHash) => {});

  let firstStoreUpdate = true;
  // When the original store changes, set fromUrl = false and push state.
  store.subscribe(state => {
    console.log('original store change', state);
    // Ignore the first store's update as this happens at initialization.
    if (firstStoreUpdate) {
      firstStoreUpdate = false;
      return;
    }
    urlStore.set({fromUrl: false, hashState: null});
    const hashState = hashFromState(state);
    console.log('[PUSHING STATE TO URL] [storechange]', state, hashState);

    pushState(identifier, hashState);
  });

  const derivedStore = derived<[Readable<T>, Readable<UrlStoreState>], T>(
    [store, urlStore],
    ([$store, $urlStore], set) => {
      // Only inform the subscribers of the derived store if the state change wasn't from the URL.
      if (!$urlStore.fromUrl) {
        console.log('[NOT READ URL] derived store: notifying subscribers');
        set($store);

        // Update the app store with the new state so it can be serialized.
      } else {
        const state = stateFromHash($urlStore.hashState!);
        console.log(
          '[READ URL] derived store: notifying subscribers from url',
          $urlStore.hashState,
          state
        );

        set(state);
      }
    }
  );

  // Return the derived store.

  return {
    ...store,
    subscribe: derivedStore.subscribe
  };
}
