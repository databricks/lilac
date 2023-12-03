<script lang="ts">
  import DatasetFieldEmbeddingSelector from '$lib/components/concepts/DatasetFieldEmbeddingSelector.svelte';
  import Page from '$lib/components/Page.svelte';
  import RagPrompt from '$lib/components/rag/RagPrompt.svelte';
  import RagRetrieval, {type RagRetrievalResult} from '$lib/components/rag/RagRetrieval.svelte';
  import {
    createRagViewStore,
    defaultRagViewState,
    setRagViewContext,
    type RagViewState
  } from '$lib/stores/ragViewStore';
  import {
    deserializeState,
    getUrlHashContext,
    persistedHashStore,
    serializeState
  } from '$lib/stores/urlHashStore';
  import {RagService, type Path} from '$lilac';
  import {SkeletonText, TextInput} from 'carbon-components-svelte';
  import {Search} from 'carbon-icons-svelte';
  import SvelteMarkdown from 'svelte-markdown';

  const ragViewStore = createRagViewStore();
  setRagViewContext(ragViewStore);

  // URL state.
  const urlHashStore = getUrlHashContext();
  const identifier = '';
  let hasLoadedFromUrl = false;
  persistedHashStore<RagViewState>(
    'rag',
    identifier,
    ragViewStore,
    urlHashStore,
    hashState => deserializeState(hashState, defaultRagViewState()),
    state => serializeState(state, defaultRagViewState()),
    () => {
      hasLoadedFromUrl = true;
    }
  );

  // Dataset, field, and embedding selection.
  let selectedDataset: {namespace: string; name: string} | undefined | null = undefined;
  let selectedPath: Path | undefined = undefined;
  let selectedEmbedding: string | undefined;

  $: {
    if ($ragViewStore.datasetNamespace != null && $ragViewStore.datasetName != null) {
      selectedDataset = {
        namespace: $ragViewStore.datasetNamespace,
        name: $ragViewStore.datasetName
      };
    }
    if ($ragViewStore.path != null) {
      selectedPath = $ragViewStore.path;
    }
    if ($ragViewStore.embedding != null) {
      selectedEmbedding = $ragViewStore.embedding;
    }
  }

  let questionInputText = '';
  $: {
    if ($ragViewStore.query != null) {
      questionInputText = $ragViewStore.query;
    }
  }

  // Retrieval.
  let retrievalResults: RagRetrievalResult[] | undefined;
  let retrievalIsFetching = false;

  // Prompt.
  let prompt: string | undefined;

  // Get the answer.
  let answerFetching = false;
  let answer: string | null = null;
  $: {
    if (prompt != null) {
      answerFetching = true;
      answer = null;
      RagService.generateCompletion(prompt).then(result => {
        answer = result;
        answerFetching = false;
      });
    }
  }

  function questionTextChanged(e: CustomEvent<string | number | null>) {
    answer = null;
    retrievalResults = undefined;

    questionInputText = `${e.detail}`;
  }

  function answerQuestion() {
    ragViewStore.setQuestion(questionInputText);
  }
</script>

<Page hideTasks>
  <div slot="header-subtext" class="text-lg">Retrival Augmented Generation (RAG)</div>
  <div slot="header-right" class="dataset-selector py-2">
    {#if hasLoadedFromUrl}
      <!-- Dataset selector -->
      <DatasetFieldEmbeddingSelector
        inputSize={'sm'}
        dataset={selectedDataset}
        path={selectedPath}
        embedding={selectedEmbedding}
        on:change={e => {
          const {dataset, path, embedding} = e.detail;
          if (
            dataset != selectedDataset ||
            path != selectedPath ||
            embedding != selectedEmbedding
          ) {
            selectedDataset = dataset;
            selectedPath = path;
            selectedEmbedding = embedding;
            ragViewStore.setDatasetPathEmbedding(dataset, path, embedding);
          }
        }}
      />
    {/if}
  </div>

  <div class="h-full w-full overflow-x-hidden overflow-y-scroll">
    <div class="mx-4 mb-8 mt-2 flex h-full w-full flex-col items-start gap-y-24 px-4">
      <div class="mt-6 flex w-1/2 flex-col gap-y-10">
        <!-- Input question -->
        <div class="flex flex-col gap-y-4">
          <div class="font-medium">Question</div>
          <div class="question-input flex w-full flex-row items-end">
            <button
              class="z-10 -mr-10 mb-2"
              class:opacity-10={$ragViewStore.datasetName == null}
              disabled={$ragViewStore.datasetName == null}
              on:click={() => answerQuestion()}
              ><Search size={16} />
            </button>
            <TextInput
              on:input={questionTextChanged}
              on:change={answerQuestion}
              value={questionInputText}
              size="xl"
              disabled={$ragViewStore.datasetName == null}
              placeholder={$ragViewStore.datasetName != null
                ? 'Enter a question'
                : 'Choose a dataset'}
            />
          </div>
        </div>
        <div class="flex flex-col gap-y-4">
          <div class="font-medium">Answer</div>

          <div class="pt-4">
            {#if answerFetching || retrievalIsFetching}
              <SkeletonText />
            {:else if answer != null}
              <div class="markdown whitespace-break-spaces leading-5">
                <SvelteMarkdown source={answer} />
              </div>
            {:else}
              <div class="whitespace-break-spaces font-light italic leading-5">
                Press the search button to answer the question.
              </div>
            {/if}
          </div>
        </div>
      </div>

      <div class="flex w-full flex-row gap-x-8">
        <div class="w-1/2">
          <RagRetrieval bind:retrievalResults bind:isFetching={retrievalIsFetching} />
        </div>
        <div class="w-1/2">
          <RagPrompt {questionInputText} {retrievalResults} on:prompt={e => (prompt = e.detail)} />
        </div>
      </div>
    </div>
  </div>
</Page>

<style lang="postcss">
  .dataset-selector {
    width: 34rem;
  }
  :global(.question-input .bx--text-input) {
    @apply pl-11;
  }

  .markdown {
    /** Add a tiny bit of padding so that the hover doesn't flicker between rows. */
    padding-top: 1.5px;
    padding-bottom: 1.5px;
  }
  :global(.markdown pre) {
    @apply overflow-x-auto bg-slate-200 p-2 text-sm;
  }
  :global(.markdown pre) {
    @apply my-3;
  }
  :global(.markdown p),
  :global(.markdown h1) {
    background-color: inherit;
  }
  :global(.markdown p) {
    @apply mt-3 text-sm;
    font-weight: inherit;
  }
  :global(.markdown ul) {
    @apply mt-3 list-inside list-disc;
  }
  /** Inline the last paragraph that preceeds the highlight. */
  :global(.markdown:has(+ .highlighted) p:last-child) {
    @apply !inline;
  }
  /** Inline the first paragraph that succeeds the highlight. */
  :global(.highlighted + .markdown p:first-child) {
    @apply !inline;
  }
  :global(.highlighted p) {
    @apply !inline;
  }
</style>
