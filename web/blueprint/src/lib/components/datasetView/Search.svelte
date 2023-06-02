<script lang="ts">
  import {page} from '$app/stores';
  import {
    computeSignalColumnMutation,
    queryDatasetSchema,
    queryManyDatasetStats
  } from '$lib/queries/datasetQueries';

  import {queryEmbeddings} from '$lib/queries/signalQueries';
  import {getDatasetViewContext, isPathVisible} from '$lib/stores/datasetViewStore';
  import {
    deserializePath,
    getField,
    listFields,
    pathIsEqual,
    serializePath,
    type Path,
    type SignalInfoWithTypedSchema
  } from '$lilac';
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
  import {onMount} from 'svelte';

  $: namespace = $page.params.namespace;
  $: datasetName = $page.params.datasetName;

  let selectedPath: string | undefined;
  let defaultEmbedding: string | undefined;
  let selectedEmbedding: string | undefined;

  const tabs: {[key: number]: 'Keyword' | 'Semantic' | 'Concepts'} = {
    0: 'Keyword',
    1: 'Semantic',
    2: 'Concepts'
  };

  let selectedTabIndex = 0;
  $: selectedTab = tabs[selectedTabIndex];

  let keywordSearchText: string;
  // Semantic search.
  let semanticSearchText: string;
  // Concepts.
  let conceptSearchText = 'Not implemented yet.';

  let datasetViewStore = getDatasetViewContext();
  const computeSignalMutation = computeSignalColumnMutation();

  $: schema = queryDatasetSchema($datasetViewStore.namespace, $datasetViewStore.datasetName);

  // Only show the visible string fields in the dropdown.
  let visibleStringFields: Path[] = [];
  $: {
    let allFields = $schema?.isSuccess ? listFields($schema.data) : [];
    visibleStringFields = allFields
      .filter(f => isPathVisible($datasetViewStore.visibleColumns, f.path, undefined))
      .filter(f => f.dtype == 'string')
      .map(f => f.path);
  }

  // Query stats so we can sort by the length.
  // TODO(nsthorat): Make this a util.
  $: statsQueries = queryManyDatasetStats(
    visibleStringFields.map(path => {
      return [
        $datasetViewStore.namespace,
        $datasetViewStore.datasetName,
        {
          leaf_path: path
        }
      ];
    })
  );

  // Sort the visible string fields by average length.
  $: {
    if ($statsQueries && $statsQueries.length > 0 && $statsQueries.every(q => q.isSuccess)) {
      const stats = $statsQueries.map(q => q.data);
      const pathToLength: {[path: string]: number | null} = {};
      for (const [i, stat] of stats.entries()) {
        pathToLength[serializePath(visibleStringFields[i])] = stat?.avg_text_length || null;
      }

      // Sort the visible string fields by average length.
      visibleStringFields.sort((a, b) => {
        const aLength = pathToLength[serializePath(a)];
        const bLength = pathToLength[serializePath(b)];
        if (aLength == null && bLength == null) {
          return 0;
        } else if (aLength == null) {
          return 1;
        } else if (bLength == null) {
          return -1;
        } else {
          return bLength - aLength;
        }
      });
    }
  }
  $: {
    if (selectedPath != null) {
      // If the path is selected, and the user has changed the visible columns, remove the
      // selected path.
      let hasSelectedPath = visibleStringFields.some(path => pathIsEqual(path, selectedPath));
      if (!hasSelectedPath) {
        selectedPath = undefined;
      }
    } else if (selectedPath == null && visibleStringFields.length > 0) {
      // Choose the longest string on the first render.
      selectedPath = serializePath(visibleStringFields[0]);
    }
  }

  // Get the embeddings.
  const embeddings = queryEmbeddings();

  // Populate existing embeddings for the selected field.
  let existingEmbeddings: Set<string>;

  let sortedEmbeddings: SignalInfoWithTypedSchema[] = [];
  // Find all existing pre-computed embeddings for the current split from the schema
  $: {
    if (selectedPath != null && $schema.data != null) {
      existingEmbeddings = new Set();
      const embeddingSignalRoots = listFields(
        getField($schema.data, deserializePath(selectedPath))
      ).filter(f => f.signal != null && listFields(f).some(f => f.dtype === 'embedding'));

      for (const field of embeddingSignalRoots) {
        if (field.signal?.signal_name != null) {
          existingEmbeddings.add(field.signal.signal_name);
        }
      }

      sortedEmbeddings =
        existingEmbeddings != null
          ? [...($embeddings.data || [])].sort((a, b) => {
              const hasA = existingEmbeddings.has(a.name);
              const hasB = existingEmbeddings.has(b.name);
              if (hasA && hasB) {
                return 0;
              } else if (hasA) {
                return -1;
              } else if (hasB) {
                return 1;
              }
              return 0;
            })
          : [];
    }
  }

  $: defaultEmbedding = sortedEmbeddings[0]?.name;

  $: {
    // Choose the first embedding if the user hasn't already selected an embedding.
    if (selectedEmbedding == null) {
      selectedEmbedding = defaultEmbedding;
    }
  }

  $: isEmbeddingComputed =
    existingEmbeddings != null && !!existingEmbeddings.has(selectedEmbedding || '');
  let isWaitingForIndexing: {[key: string]: boolean} = {};
  $: isIndexing =
    !isEmbeddingComputed && isWaitingForIndexing[`${selectedPath}_${selectedEmbedding}`];

  $: keywordSearchEnabled = tabs[selectedTabIndex] === 'Keyword' && selectedPath != null;
  $: semanticSearchEnabled = tabs[selectedTabIndex] === 'Semantic' && isEmbeddingComputed;

  $: searchEnabled = keywordSearchEnabled || semanticSearchEnabled;

  $: showClearSearch =
    (selectedTab === 'Keyword' && keywordSearchText != '') ||
    (selectedTab === 'Semantic' && semanticSearchText != '');

  // Copy filters from query options
  onMount(() => {
    const searches = structuredClone($datasetViewStore.queryOptions.searches || []);
    // TODO(nsthorat): Support multiple searches.
    const keywordSearches = searches.filter(s => s.type == 'contains');
    if (keywordSearches.length > 0) {
      keywordSearchText = keywordSearches[0].query;
    }
    const semanticSearches = searches.filter(s => s.type == 'semantic');
    if (semanticSearches.length > 0) {
      semanticSearchText = semanticSearches[0].query;
    }
  });

  const clearSearch = () => {
    if (selectedTab === 'Keyword') {
      keywordSearchText = '';
    } else if (selectedTab === 'Semantic') {
      semanticSearchText = '';
    }
  };
  const search = () => {
    if (selectedPath == null) {
      return;
    }
    // TODO(nsthorat): Support multiple searches at the same time. Currently each search overrides
    // the set of searches.
    if (selectedTab === 'Keyword') {
      if (keywordSearchText == '') {
        $datasetViewStore.queryOptions.searches = [];
        return;
      }
      $datasetViewStore.queryOptions.searches = [
        {
          path: [selectedPath],
          type: 'contains',
          query: keywordSearchText
        }
      ];
    } else if (selectedTab === 'Semantic') {
      if (semanticSearchText == '') {
        // TODO: Don't clear this.
        $datasetViewStore.queryOptions.searches = [];
        return;
      }
      $datasetViewStore.queryOptions.searches = [
        {
          path: [selectedPath],
          embedding: selectedEmbedding,
          type: 'semantic',
          query: semanticSearchText
        }
      ];
    } else if (selectedTab === 'Concepts') {
      // TODO: Implement concept search.
    }
  };

  const selectEmbedding = (e: Event) => {
    selectedEmbedding = (e.target as HTMLInputElement).value;
  };
  const computeEmbedding = () => {
    isWaitingForIndexing[`${selectedPath}_${selectedEmbedding}`] = true;
    $computeSignalMutation.mutate([
      namespace,
      datasetName,
      {
        leaf_path: deserializePath(selectedPath || []),
        signal: {
          signal_name: selectedEmbedding
        }
      }
    ]);
  };
</script>

<div class="mx-4 my-2 flex h-24 flex-row items-start">
  <div class="mr-12 mt-4 w-32">
    <!-- Field select -->
    <Select
      class="field-select"
      bind:selected={selectedPath}
      name={selectedPath}
      labelText={'Search field'}
      disabled={visibleStringFields.length === 0}
      warn={visibleStringFields.length === 0}
      warnText={visibleStringFields.length === 0 ? 'Select a schema field!' : undefined}
    >
      {#each visibleStringFields as field}
        <SelectItem value={serializePath(field)} text={serializePath(field)} />
      {/each}
    </Select>
  </div>
  <!-- Search boxes -->
  <div class="search-container flex w-full flex-row">
    <div class="w-full">
      <Tabs class="flex flex-row" bind:selected={selectedTabIndex}>
        <Tab>{tabs[0]}</Tab>
        <Tab>{tabs[1]}</Tab>
        <Tab>{tabs[2]}</Tab>
        <svelte:fragment slot="content">
          <div class="flex flex-row">
            <div class="-ml-6 mr-2 flex h-10 items-center">
              <button
                class="z-10 opacity-50 hover:opacity-100"
                class:opacity-20={selectedPath == null}
                class:hover:opacity-20={selectedPath == null}
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
                    selected={selectedEmbedding}
                    name={selectedEmbedding}
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
                    disabled={selectedPath == null || isEmbeddingComputed || isIndexing}
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
    <Button
      disabled={selectedPath == null || !searchEnabled}
      on:click={() => search()}
      size="small"
    >
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
