<script lang="ts">
  import {page} from '$app/stores';
  import {computeSignalColumnMutation} from '$lib/queries/datasetQueries';

  import {queryEmbeddings} from '$lib/queries/signalQueries';
  import {getDatasetContext} from '$lib/stores/datasetStore';
  import {SEARCH_TABS, getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {
    getComputedEmbeddings,
    getSearchEmbedding,
    getSearchPath,
    getVisibleFields
  } from '$lib/view_utils';
  import {deserializePath, serializePath} from '$lilac';
  import {
    Button,
    InlineLoading,
    Select,
    SelectItem,
    Tab,
    TabContent,
    Tabs,
    TextInput
  } from 'carbon-components-svelte';
  import {Checkmark, Chip, Close} from 'carbon-icons-svelte';

  $: namespace = $page.params.namespace;
  $: datasetName = $page.params.datasetName;

  let datasetViewStore = getDatasetViewContext();

  $: selectedTab = $datasetViewStore.searchTab;
  $: selectedTabIndex = Object.values(SEARCH_TABS).findIndex(v => v === selectedTab);

  let keywordSearchText: string;
  // Semantic search.
  let semanticSearchText: string;
  // Concepts.
  let conceptSearchText = 'Not implemented yet.';

  const computeSignalMutation = computeSignalColumnMutation();

  let datasetStore = getDatasetContext();

  // Only show the visible string fields in the dropdown.
  $: visibleStringPaths = getVisibleFields($datasetViewStore, $datasetStore, null, 'string').map(
    f => f.path
  );

  $: searchPath = getSearchPath($datasetViewStore, $datasetStore);

  // Get the embeddings.
  const embeddings = queryEmbeddings();

  $: selectedEmbedding = getSearchEmbedding(
    $datasetViewStore,
    $datasetStore,
    searchPath,
    ($embeddings.data || []).map(e => e.name)
  );

  // Populate existing embeddings for the selected field.
  $: existingEmbeddings = getComputedEmbeddings($datasetStore, searchPath);

  $: isEmbeddingComputed =
    existingEmbeddings != null && !!existingEmbeddings.includes(selectedEmbedding || '');
  let isWaitingForIndexing: {[key: string]: boolean} = {};
  $: isIndexing =
    !isEmbeddingComputed &&
    isWaitingForIndexing[`${serializePath(searchPath || '')}_${selectedEmbedding}`];

  $: keywordSearchEnabled = SEARCH_TABS[selectedTabIndex] === 'Keyword' && searchPath != null;
  $: semanticSearchEnabled = SEARCH_TABS[selectedTabIndex] === 'Semantic' && isEmbeddingComputed;

  $: searchEnabled = keywordSearchEnabled || semanticSearchEnabled;

  $: showClearSearch =
    (selectedTab === 'Keyword' && keywordSearchText != '') ||
    (selectedTab === 'Semantic' && semanticSearchText != '');

  const clearSearch = () => {
    // TODO(nsthorat): Don't clear from the searchbox, clear from pills.
    if (selectedTab === 'Keyword') {
      keywordSearchText = '';
    } else if (selectedTab === 'Semantic') {
      semanticSearchText = '';
    }
  };
  const search = () => {
    if (searchPath == null) {
      return;
    }
    // TODO(nsthorat): Support multiple searches at the same time. Currently each search overrides
    // the set of searches.
    if (selectedTab === 'Keyword') {
      if (keywordSearchText == '') {
        datasetViewStore.clearSearchType('contains');
        return;
      }
      datasetViewStore.addSearch({
        path: [serializePath(searchPath)],
        type: 'contains',
        query: keywordSearchText
      });
      keywordSearchText = '';
    } else if (selectedTab === 'Semantic') {
      if (selectedEmbedding == null) {
        return;
      }
      if (semanticSearchText == '') {
        datasetViewStore.clearSearchType('semantic');
        return;
      }
      datasetViewStore.addSearch({
        path: [serializePath(searchPath)],
        type: 'semantic',
        query: semanticSearchText,
        embedding: selectedEmbedding
      });
      semanticSearchText = '';
    } else if (selectedTab === 'Concepts') {
      // TODO: Implement concept search.
    }
  };

  const selectEmbedding = (e: Event) => {
    selectedEmbedding = (e.target as HTMLInputElement).value;
    datasetViewStore.setSearchEmbedding((e.target as HTMLInputElement).value);
  };
  const computeEmbedding = () => {
    if (selectedEmbedding == null) return;
    isWaitingForIndexing[`${serializePath(searchPath || '')}_${selectedEmbedding}`] = true;
    $computeSignalMutation.mutate([
      namespace,
      datasetName,
      {
        leaf_path: deserializePath(searchPath || []),
        signal: {
          signal_name: selectedEmbedding
        }
      }
    ]);
  };
  const selectField = (e: Event) => {
    datasetViewStore.setSearchPath((e.target as HTMLInputElement).value);
  };
  const selectTab = (e: {detail: number}) => {
    datasetViewStore.setSearchTab(SEARCH_TABS[e.detail]);
  };
</script>

<div class="mx-4 my-2 flex h-24 flex-row items-start">
  <div class="mr-12 mt-4 w-44">
    <!-- Field select -->
    <Select
      class="field-select"
      selected={searchPath ? serializePath(searchPath) : ''}
      on:change={selectField}
      labelText={'Search field'}
      disabled={visibleStringPaths.length === 0}
      warn={visibleStringPaths.length === 0}
      warnText={visibleStringPaths.length === 0 ? 'Select a schema field!' : undefined}
    >
      {#each visibleStringPaths as field}
        <SelectItem value={serializePath(field)} text={serializePath(field)} />
      {/each}
    </Select>
  </div>
  <!-- Search boxes -->
  <div class="search-container flex w-full flex-row">
    <div class="w-full">
      <Tabs class="flex flex-row" selected={selectedTabIndex} on:change={selectTab}>
        <Tab>{SEARCH_TABS[0]}</Tab>
        <Tab>{SEARCH_TABS[1]}</Tab>
        <Tab>{SEARCH_TABS[2]}</Tab>
        <svelte:fragment slot="content">
          <div class="flex flex-row">
            <div class="-ml-6 mr-2 flex h-10 items-center">
              <button
                class="z-10 opacity-50 hover:opacity-100"
                class:opacity-20={searchPath == null}
                class:hover:opacity-20={searchPath == null}
                class:invisible={!showClearSearch}
                on:click|stopPropagation={() => {
                  clearSearch();
                  search();
                }}
              >
                <Close />
              </button>
            </div>
            <!-- Keyword input -->
            <TabContent class="w-full">
              <TextInput
                placeholder="Search by keywords"
                disabled={!keywordSearchEnabled}
                bind:value={keywordSearchText}
                on:keydown={e => (e.key == 'Enter' ? search() : null)}
              />
            </TabContent>

            <!-- Semantic input -->
            <TabContent class="w-full">
              <div class="flex flex-row items-start justify-items-start">
                <TextInput
                  helperText={isEmbeddingComputed
                    ? ''
                    : 'No index found. Please run the embedding index.'}
                  placeholder="Search by natural language"
                  disabled={!semanticSearchEnabled}
                  bind:value={semanticSearchText}
                  on:keydown={e => (e.key == 'Enter' ? search() : null)}
                />
                <div class="embedding-select -ml-8">
                  <Select
                    noLabel={true}
                    on:change={selectEmbedding}
                    selected={selectedEmbedding || ''}
                    name={selectedEmbedding || ''}
                    helperText={'Embedding'}
                  >
                    {#each $embeddings.data || [] as embedding}
                      <SelectItem value={embedding.name} text={embedding.name} />
                    {/each}
                  </Select>
                </div>
                <div>
                  <Button
                    size="small"
                    disabled={searchPath == null || isEmbeddingComputed || isIndexing}
                    on:click={() => {
                      computeEmbedding();
                    }}
                    icon={isEmbeddingComputed ? Checkmark : isIndexing ? InlineLoading : Chip}
                    >Index
                  </Button>
                </div>
              </div>
            </TabContent>

            <!-- Concept input -->
            <TabContent class="w-full">
              <TextInput
                class="w-full"
                placeholder={'Search by concepts'}
                disabled={true}
                value={conceptSearchText}
              />
            </TabContent>
          </div>
        </svelte:fragment>
      </Tabs>
    </div>
  </div>

  <div class="ml-2 mt-10 flex h-full">
    <Button disabled={searchPath == null || !searchEnabled} on:click={() => search()} size="small">
      Search
    </Button>
  </div>
</div>

<style lang="postcss">
  :global(.bx--tabs__nav) {
    @apply flex w-full flex-row;
  }
  :global(.bx--tabs__nav-item) {
    @apply w-28;
  }
  :global(.bx--tabs__nav-item .bx--tabs__nav-link) {
    @apply w-28;
  }

  :global(.bx--form__helper-text) {
    padding: 0 0 0 1rem;
  }
  :global(.bx--btn--sm) {
    height: 2.5rem;
    @apply w-24;
    @apply px-3;
  }
</style>
