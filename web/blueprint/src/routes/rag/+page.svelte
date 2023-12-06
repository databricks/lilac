<script lang="ts">
  import DatasetFieldEmbeddingSelector from '$lib/components/concepts/DatasetFieldEmbeddingSelector.svelte';
  import Expandable from '$lib/components/Expandable.svelte';
  import Page from '$lib/components/Page.svelte';
  import RagPrompt from '$lib/components/rag/RagPrompt.svelte';
  import RagRetrieval from '$lib/components/rag/RagRetrieval.svelte';
  import {getRagGeneration} from '$lib/queries/ragQueries';
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
  import type {Path, RagRetrievalResultItem} from '$lilac';
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
  let retrievalResults: RagRetrievalResultItem[] | undefined;
  let retrievalIsFetching = false;

  // Prompt.
  let promptTemplate: string | undefined;

  // Get the answer.
  let answer: string | null = null;
  let numInputTokens: number | null = null;
  let numOutputTokens: number | null = null;

  $: generationResult =
    questionInputText != null && promptTemplate != null && retrievalResults != null
      ? getRagGeneration({
          query: questionInputText,
          prompt_template: promptTemplate,
          retrieval_results: retrievalResults
        })
      : null;
  $: {
    if (
      generationResult != null &&
      $generationResult?.data != null &&
      !$generationResult.isFetching &&
      !$generationResult.isStale
    ) {
      answer = $generationResult.data.result;
      numInputTokens = $generationResult.data.num_input_tokens;
      numOutputTokens = $generationResult.data.num_output_tokens;
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
  <div slot="header-subtext" class="text-lg">Retrieval Augmented Generation (RAG)</div>
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

  <div class="flex-grow overflow-y-scroll">
    <div class="mx-4 mb-8 mt-8 flex flex-row gap-x-8 px-4">
      <div class="flex h-fit w-1/2 flex-col gap-y-4 rounded-xl border border-gray-300">
        <div class="relative overflow-x-auto rounded-t-xl">
          <div class="w-full text-left text-sm text-gray-500 rtl:text-right">
            <div class="bg-neutral-100 text-xs uppercase text-gray-700">
              <div>
                <div class="px-6 py-3">Question</div>
              </div>
            </div>
          </div>
        </div>
        <!-- Input question -->
        <div class="mx-6 mt-2 flex flex-col gap-y-4">
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
        <div class="mx-6 mb-4 mt-4 flex flex-col gap-y-4">
          <div>
            {#if $generationResult?.isFetching || retrievalIsFetching}
              <SkeletonText />
            {:else if answer != null}
              <div class="markdown whitespace-break-spaces leading-5">
                <SvelteMarkdown source={answer} />
              </div>
            {:else}
              <div class="whitespace-break-spaces font-light italic leading-5">
                Press enter to answer the question.
              </div>
            {/if}
          </div>
        </div>
      </div>
      <div class="flex w-1/2 flex-col gap-y-4 rounded-xl border border-gray-300">
        <div>
          <div class="relative overflow-x-auto rounded-t-xl">
            <div class="w-full text-left text-sm text-gray-500 rtl:text-right">
              <div class="bg-gray-100 text-xs uppercase text-gray-700">
                <div>
                  <div class="px-6 py-3">Editor</div>
                </div>
              </div>
            </div>
          </div>
          <div class="relative w-full overflow-x-auto rounded-xl">
            <div class="mt-4 flex flex-col gap-y-2 text-left text-sm text-gray-500 rtl:text-right">
              <div class="flex flex-row bg-white">
                <div class="w-48 px-6 text-gray-900 backdrop:whitespace-nowrap">Input tokens</div>
                {#if $generationResult?.isFetching || retrievalIsFetching}
                  <div class="w-8"><SkeletonText /></div>
                {:else if numInputTokens != null}
                  <div class="text-right">
                    {numInputTokens.toLocaleString()}
                  </div>
                {:else}
                  <div class="text-right italic">None</div>
                {/if}
              </div>
              <div class="flex flex-row bg-white">
                <div class="w-48 whitespace-nowrap px-6 text-gray-900">Output tokens</div>
                {#if $generationResult?.isFetching || retrievalIsFetching}
                  <div class="w-8"><SkeletonText /></div>
                {:else if numOutputTokens != null}
                  <div class="text-right">
                    {numOutputTokens.toLocaleString()}
                  </div>
                {:else}
                  <div class="text-right italic">None</div>
                {/if}
              </div>
            </div>
          </div>
        </div>
        <div class="mx-4 mb-4 flex flex-col gap-y-4">
          <Expandable expanded on:results>
            <div slot="above" class="flex flex-row gap-x-12">
              <div class="font-medium">Retrieval</div>
            </div>
            <div slot="below">
              <RagRetrieval
                on:results={e => (retrievalResults = e.detail)}
                bind:isFetching={retrievalIsFetching}
              />
            </div>
          </Expandable>
          <Expandable>
            <div slot="above" class="flex flex-row gap-x-12">
              <div class="font-medium">Generation</div>
            </div>
            <div slot="below">
              <RagPrompt
                {questionInputText}
                {retrievalResults}
                on:promptTemplate={e => {
                  promptTemplate = e.detail;
                }}
              />
            </div>
          </Expandable>
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
</style>
