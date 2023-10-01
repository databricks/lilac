import type {Path} from '$lilac';
import {getContext, hasContext, setContext} from 'svelte';
import {writable} from 'svelte/store';

const RAG_VIEW_CONTEXT = 'RAG_VIEW_CONTEXT';

export interface RagViewState {
  datasetNamespace: string | null;
  datasetName: string | null;
  path: Path | null;
  embedding: string | null;

  query: string | null;
  promptTemplate: string;
  topK: number;
  semanticSimilarityThreshold: number;
  windowSizeChunks: number;
}
export type RagViewStore = ReturnType<typeof createRagViewStore>;

export function defaultRagViewState(): RagViewState {
  return {
    datasetNamespace: null,
    datasetName: null,
    path: null,
    embedding: null,
    query: null,
    promptTemplate: `Context information is below.
---------------------
{context_str}
---------------------
Given the context information and not prior knowledge, answer the query.
Query: {query_str}
Answer: \
`,
    topK: 10,
    semanticSimilarityThreshold: 0.9,
    windowSizeChunks: 1
  };
}

export function createRagViewStore() {
  const defaultState = defaultRagViewState();

  const {subscribe, set, update} = writable<RagViewState>(
    // Deep copy the initial state so we don't have to worry about mucking the initial state.
    JSON.parse(JSON.stringify(defaultState))
  );

  const store = {
    subscribe,
    set,
    update,
    reset: () => {
      set(JSON.parse(JSON.stringify(defaultState)));
    },
    setDatasetPathEmbedding: (
      dataset: {namespace: string; name: string} | null,
      path: Path | null,
      embedding: string | null
    ) => {
      update(state => {
        if (dataset == null) {
          state.datasetNamespace = null;
          state.datasetName = null;
        } else {
          state.datasetNamespace = dataset.namespace;
          state.datasetName = dataset.name;
        }
        state.path = path;
        state.embedding = embedding;

        return state;
      });
    },
    setQuestion: (question: string | null) => {
      update(state => {
        state.query = question;
        return state;
      });
    }
  };

  return store;
}

export function setRagViewContext(store: RagViewStore) {
  setContext(RAG_VIEW_CONTEXT, store);
}

export function getRagViewContext() {
  if (!hasContext(RAG_VIEW_CONTEXT)) throw new Error('RagViewContext not found');
  return getContext<RagViewStore>(RAG_VIEW_CONTEXT);
}
