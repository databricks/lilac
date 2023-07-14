import {getContext, hasContext, setContext} from 'svelte';
import {persisted} from './persistedStore';

const SETTINGS_CONTEXT = 'SETTINGS_CONTEXT';

export interface SettingsState {
  embedding?: string;
}

const LS_KEY = 'settingsStore';

export type SettingsStore = ReturnType<typeof createSettingsStore>;

export function createSettingsStore() {
  const initialState: SettingsState = {};
  const {subscribe, set, update} = persisted<SettingsState>(LS_KEY, initialState, {
    storage: 'session'
  });

  return {
    subscribe,
    set,
    update,
    reset() {
      set(JSON.parse(JSON.stringify(initialState)));
    },
    setEmbedding(embedding?: string) {
      update(state => {
        state.embedding = embedding;
        return state;
      });
    }
  };
}

export function setSettingsContext(store: SettingsStore) {
  setContext(SETTINGS_CONTEXT, store);
}

export function getSettingsContext(): SettingsStore {
  if (!hasContext(SETTINGS_CONTEXT)) throw new Error('SettingsContext not found');
  return getContext<SettingsStore>(SETTINGS_CONTEXT);
}
