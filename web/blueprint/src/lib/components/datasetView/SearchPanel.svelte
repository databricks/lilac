<script lang="ts">
  import {queryConcepts} from '$lib/queries/conceptQueries';
  import {computeSignalColumnMutation} from '$lib/queries/datasetQueries';

  import {queryEmbeddings} from '$lib/queries/signalQueries';
  import {getDatasetContext} from '$lib/stores/datasetStore';
  import {SEARCH_TABS, getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {
    getComputedEmbeddings,
    getSearchEmbedding,
    getSearchPath,
    getSearches,
    getSort,
    getVisibleFields
  } from '$lib/view_utils';
  import {deserializePath, petals, serializePath, type SearchResultInfo} from '$lilac';
  import {
    Button,
    ComboBox,
    Dropdown,
    InlineLoading,
    Search,
    Select,
    SelectItem,
    Tab,
    TabContent,
    Tabs
  } from 'carbon-components-svelte';
  import {
    Checkmark,
    Chip,
    Close,
    SortAscending,
    SortDescending,
    SortRemove
  } from 'carbon-icons-svelte';

  let datasetViewStore = getDatasetViewContext();
  let datasetStore = getDatasetContext();

  $: namespace = $datasetViewStore.namespace;
  $: datasetName = $datasetViewStore.datasetName;

  $: selectedTab = $datasetViewStore.searchTab;
  $: selectedTabIndex = Object.values(SEARCH_TABS).findIndex(v => v === selectedTab);

  $: searchPath = getSearchPath($datasetViewStore, $datasetStore);

  let keywordSearchText: string;
  // Semantic search.
  let semanticSearchText: string;

  $: searches = getSearches($datasetViewStore, searchPath);

  const computeSignalMutation = computeSignalColumnMutation();

  // Only show the visible string fields in the dropdown.
  $: visibleStringPaths = getVisibleFields($datasetViewStore, $datasetStore, null, 'string').map(
    f => f.path
  );

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

  const concepts = queryConcepts();
  interface ConceptId {
    namespace: string;
    name: string;
  }
  interface ConceptSelectItem {
    id: ConceptId;
    text: string;
  }
  let conceptSelectItems: ConceptSelectItem[] = [];

  $: conceptSelectItems = $concepts?.data
    ? $concepts.data.map(c => ({
        id: {namespace: c.namespace, name: c.name},
        text: `${c.namespace}/${c.name}`,
        disabled: searches.some(
          s =>
            s.query.type === 'concept' &&
            s.query.concept_namespace === c.namespace &&
            s.query.concept_name === c.name
        )
      }))
    : [];

  // Sorts.
  $: sort = getSort($datasetStore);
  let pathToSearchResult: {[path: string]: SearchResultInfo} = {};
  $: {
    for (const search of $datasetStore?.selectRowsSchema?.search_results || []) {
      pathToSearchResult[serializePath(search.result_path)] = search;
    }
  }

  // Server sort response.
  $: sortById = sort?.path ? serializePath(sort.path) : null;
  // Explicit user selection of sort.
  $: selectedSortBy = $datasetViewStore.queryOptions.sort_by;

  $: sortItems =
    $datasetStore?.selectRowsSchema?.data_schema != null
      ? [
          {id: null, text: 'None', disabled: selectedSortBy == null && sortById != null},
          ...petals($datasetStore.selectRowsSchema.schema).map(field => {
            const pathStr = serializePath(field.path);
            const search = pathToSearchResult[pathStr];
            return {
              id: pathStr,
              text: search?.alias != null ? search.alias : pathStr
            };
          })
        ]
      : [];

  const search = () => {
    if (searchPath == null) {
      return;
    }
    if (selectedTab === 'Keyword') {
      if (keywordSearchText == '') {
        return;
      }
      datasetViewStore.addSearch({
        path: [serializePath(searchPath)],
        query: {
          type: 'keyword',
          search: keywordSearchText
        }
      });
      keywordSearchText = '';
    } else if (selectedTab === 'Semantic') {
      if (selectedEmbedding == null || semanticSearchText == '') {
        return;
      }
      datasetViewStore.addSearch({
        path: [serializePath(searchPath)],
        query: {
          type: 'semantic',
          search: semanticSearchText,
          embedding: selectedEmbedding
        }
      });
      semanticSearchText = '';
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

  let conceptComboBox: ComboBox;
  const selectConcept = (
    e: CustomEvent<{
      selectedId: ConceptId;
      selectedItem: ConceptSelectItem;
    }>
  ) => {
    if (searchPath == null || selectedEmbedding == null) return;
    datasetViewStore.addSearch({
      path: [serializePath(searchPath)],
      query: {
        type: 'concept',
        concept_namespace: e.detail.selectedId.namespace,
        concept_name: e.detail.selectedId.name,
        embedding: selectedEmbedding
      }
    });
    conceptComboBox.clear();
  };

  const selectField = (e: Event) => {
    datasetViewStore.setSearchPath((e.target as HTMLInputElement).value);
  };
  const selectTab = (e: {detail: number}) => {
    datasetViewStore.setSearchTab(SEARCH_TABS[e.detail]);
  };
  const selectSort = (e: {detail: {selectedId: string}}) => {
    if (e.detail.selectedId == null) {
      datasetViewStore.setSortBy(null);
      return;
    }
    const alias = pathToSearchResult[e.detail.selectedId]?.alias;
    if (alias != null) {
      datasetViewStore.setSortBy([alias]);
    } else {
      datasetViewStore.setSortBy(deserializePath(e.detail.selectedId));
    }
  };
  const clearSorts = () => {
    datasetViewStore.clearSorts();
  };
  const toggleSortOrder = () => {
    // Set the sort given by the select rows schema explicitly.
    if (sort != null) {
      if (sort.alias != null) {
        datasetViewStore.setSortBy([sort?.alias]);
      } else {
        datasetViewStore.setSortBy(sort.path);
      }
    }
    datasetViewStore.setSortOrder(sort?.order === 'ASC' ? 'DESC' : 'ASC');
  };
</script>

<div class="mx-4 my-2 flex h-24 flex-row items-start">
  <div class="mr-8 mt-4">
    <!-- Field select -->
    <Select
      class="field-select w-32"
      selected={searchPath ? serializePath(searchPath) : ''}
      on:change={selectField}
      labelText={'Search field'}
      disabled={visibleStringPaths.length === 0}
      warn={visibleStringPaths.length === 0}
      warnText={visibleStringPaths.length === 0 ? 'Select a field' : undefined}
    >
      {#each visibleStringPaths as field}
        <SelectItem value={serializePath(field)} text={serializePath(field)} />
      {/each}
    </Select>
  </div>
  <!-- Search boxes -->
  <div class="search-container flex w-full flex-grow flex-row">
    <div class="w-full">
      <Tabs class="flex flex-row" selected={selectedTabIndex} on:change={selectTab}>
        <Tab>{SEARCH_TABS[0]}</Tab>
        <Tab>{SEARCH_TABS[1]}</Tab>
        <Tab>{SEARCH_TABS[2]}</Tab>
        <svelte:fragment slot="content">
          <div class="flex flex-row">
            <!-- Keyword input -->
            <TabContent class="w-full">
              <Search
                placeholder="Search by keywords"
                disabled={!keywordSearchEnabled}
                bind:value={keywordSearchText}
                on:keydown={e => (e.key == 'Enter' ? search() : null)}
              />
            </TabContent>

            <!-- Semantic input -->
            <TabContent class="w-full">
              <div class="flex flex-row items-start justify-items-start">
                <div class="flex-grow">
                  <Search
                    placeholder={isEmbeddingComputed
                      ? 'Search by natural language'
                      : 'No index found. Please run the embedding index.'}
                    disabled={!semanticSearchEnabled}
                    bind:value={semanticSearchText}
                    on:keydown={e => (e.key == 'Enter' ? search() : null)}
                  />
                </div>
              </div>
            </TabContent>

            <!-- Concept input -->
            <TabContent class="w-full">
              <div class="flex w-full flex-row items-start justify-items-start">
                <div class="flex-grow">
                  <ComboBox
                    size="xl"
                    bind:this={conceptComboBox}
                    items={conceptSelectItems}
                    on:select={selectConcept}
                    shouldFilterItem={(item, value) =>
                      item.text.toLowerCase().includes(value.toLowerCase())}
                    placeholder="Search by concept"
                  />
                </div>
              </div>
            </TabContent>
            {#if selectedTab === 'Semantic' || selectedTab === 'Concepts'}
              <div class="embedding-select w-40">
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
              <div class="ml-2">
                <Button
                  class="w-24"
                  disabled={searchPath == null || isEmbeddingComputed || isIndexing}
                  on:click={() => {
                    computeEmbedding();
                  }}
                  icon={isEmbeddingComputed ? Checkmark : isIndexing ? InlineLoading : Chip}
                  >Index
                </Button>
              </div>
            {/if}
          </div>
        </svelte:fragment>
      </Tabs>
    </div>
  </div>

  {#if selectedTab === 'Keyword' || selectedTab === 'Semantic'}
    <div class="ml-2 mt-10 flex">
      <Button
        class="w-10"
        disabled={searchPath == null || !searchEnabled}
        on:click={() => search()}
      >
        Search
      </Button>
    </div>
  {/if}
  <div class="ml-8 mt-10 flex flex-row rounded">
    <div class="w-12">
      {#if selectedSortBy != null}
        <Button
          kind="ghost"
          icon={Close}
          expressive={true}
          on:click={clearSorts}
          disabled={sort == null}
          iconDescription={sort?.order === 'ASC'
            ? 'Sorted ascending. Toggle to switch to descending.'
            : 'Sorted descending. Toggle to switch to ascending.'}
        />
      {/if}
    </div>
    <Dropdown
      size="xl"
      class="w-32"
      selectedId={sortById}
      on:select={selectSort}
      items={sortItems}
      helperText={'Sort by'}
    />
    <div>
      <Button
        kind="ghost"
        expressive={true}
        icon={sort?.order == null
          ? SortRemove
          : sort?.order === 'ASC'
          ? SortAscending
          : SortDescending}
        on:click={toggleSortOrder}
        disabled={sort == null}
        iconDescription={sort?.order === 'ASC'
          ? 'Sorted ascending. Toggle to switch to descending.'
          : 'Sorted descending. Toggle to switch to ascending.'}
      />
    </div>
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
  :global(.embedding-select .bx--select-input) {
    @apply h-12;
  }
  :global(.field-select .bx--select-input) {
    @apply h-12;
  }
</style>
