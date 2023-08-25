<script lang="ts">
  import {queryConcepts} from '$lib/queries/conceptQueries';

  import {computeSignalMutation, querySettings} from '$lib/queries/datasetQueries';
  import {queryAuthInfo} from '$lib/queries/serverQueries';
  import {queryEmbeddings} from '$lib/queries/signalQueries';
  import {getDatasetContext} from '$lib/stores/datasetStore';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {getSettingsContext} from '$lib/stores/settingsStore';
  import {
    conceptDisplayName,
    displayPath,
    getComputedEmbeddings,
    getSearchEmbedding,
    getSearchPath,
    getSearches,
    getSortedConcepts,
    shortFieldName
  } from '$lib/view_utils';
  import {
    childFields,
    deserializePath,
    getSignalInfo,
    isNumeric,
    pathIncludes,
    serializePath,
    type LilacSchema,
    type Op,
    type Path,
    type SignalInfoWithTypedSchema,
    type StatsResult,
    type UnaryFilter
  } from '$lilac';
  import {Button, ComboBox, InlineLoading, Select, SelectItem, Tag} from 'carbon-components-svelte';
  import {Add, Checkmark, Chip, SearchAdvanced} from 'carbon-icons-svelte';
  import {Command, triggerCommand} from '../commands/Commands.svelte';
  import {hoverTooltip} from '../common/HoverTooltip';

  const datasetViewStore = getDatasetViewContext();
  const datasetStore = getDatasetContext();
  const appSettings = getSettingsContext();
  $: datasetSettings = querySettings($datasetViewStore.namespace, $datasetViewStore.datasetName);

  $: namespace = $datasetViewStore.namespace;
  $: datasetName = $datasetViewStore.datasetName;

  $: searchPath = getSearchPath($datasetViewStore, $datasetStore);

  $: searches = getSearches($datasetViewStore, searchPath);

  function getFieldSearchItems(
    stats: StatsResult[] | null,
    schema: LilacSchema | null,
    embeddings: SignalInfoWithTypedSchema[] | undefined
  ): SearchItem[] {
    if (schema == null || stats == null || searchPath == null) {
      return [];
    }
    const allFields = schema ? childFields(schema) : [];
    const items: SearchItem[] = [];
    for (const field of allFields) {
      if (field.dtype == null) {
        // Ignore non-pedals.
        continue;
      }
      if (field.dtype === 'embedding' || field.dtype === 'binary') {
        // Ignore special dtypes.
        continue;
      }
      if (!pathIncludes(field.path, searchPath)) {
        // Ignore any fields unrelated to the current search path.
        continue;
      }
      const signal = getSignalInfo(field);
      if (signal?.signal_name === 'concept_score') {
        // Ignore any concept scores since they are handled seperately via preview.
        continue;
      }
      const isEmbedding = embeddings?.some(e => e.name === signal?.signal_name);
      if (isEmbedding) {
        // Ignore any embeddings since they are special "index" fields.
        continue;
      }
      const shortName = shortFieldName(field.path);
      const text = displayPath(field.path.slice(searchPath.length));
      // Suggest sorting for numeric fields.
      if (isNumeric(field.dtype)) {
        items.push({
          id: {type: 'field', path: field.path, sort: 'DESC', isSignal: signal != null} as FieldId,
          text,
          description: `Sort descending by ${shortName}`
        });
        continue;
      }

      // Suggest "exists" for signal string fields such as PII.
      if (field.dtype === 'string' || field.dtype === 'string_span') {
        if (signal == null) {
          // Skip filtering source fields by EXISTS.
          continue;
        }
        items.push({
          id: {type: 'field', path: field.path, op: 'exists', isSignal: signal != null} as FieldId,
          text,
          description: `Find documents with ${shortName}`
        });
        continue;
      }
    }
    return items;
  }

  $: fieldSearchItems = getFieldSearchItems(
    $datasetStore.stats,
    $datasetStore.schema,
    $embeddings.data
  );

  const signalMutation = computeSignalMutation();

  // Only show the visible string fields in the dropdown.
  $: visibleStringPaths = ($datasetStore.visibleFields || [])
    .filter(f => f.dtype === 'string')
    .map(f => serializePath(f.path));

  // Get the embeddings.
  const embeddings = queryEmbeddings();

  $: selectedEmbedding = getSearchEmbedding(
    $appSettings,
    $datasetSettings.data,
    $datasetViewStore,
    $datasetStore,
    searchPath,
    ($embeddings.data || []).map(e => e.name)
  );

  // Populate existing embeddings for the selected field.
  $: existingEmbeddings = getComputedEmbeddings($datasetStore, searchPath);

  $: isEmbeddingComputed =
    existingEmbeddings != null && !!existingEmbeddings.includes(selectedEmbedding || '');

  const indexingKey = (path: Path | null, embedding: string | null) =>
    `${serializePath(path || '')}_${embedding}`;
  let isWaitingForIndexing: {[key: string]: boolean} = {};
  $: isIndexing =
    !isEmbeddingComputed && isWaitingForIndexing[indexingKey(searchPath, selectedEmbedding)];

  $: placeholderText = isEmbeddingComputed
    ? 'Search by keyword, field or concept.'
    : 'Search by keyword or field. Compute embedding to enable concept search.';

  const concepts = queryConcepts();
  const authInfo = queryAuthInfo();
  $: userId = $authInfo.data?.user?.id;

  $: namespaceConcepts = getSortedConcepts($concepts.data || [], userId);
  interface ConceptId {
    type: 'concept';
    namespace: string;
    name: string;
  }
  interface FieldId {
    type: 'field';
    path: Path;
    isSignal: boolean;
    op?: Op;
    sort?: 'ASC' | 'DESC';
  }
  interface SearchItem {
    id: ConceptId | FieldId | 'new-concept' | 'keyword-search' | 'semantic-search';
    text: string;
    description?: string;
  }
  let searchItems: SearchItem[] = [];

  let searchText = '';
  let newConceptItem: SearchItem;
  $: newConceptItem = {
    id: 'new-concept',
    text: searchText,
    disabled: !isEmbeddingComputed
  };
  $: keywordSearchItem = {
    id: 'keyword-search',
    text: searchText
  } as SearchItem;
  $: semanticSearchItem = {
    id: 'semantic-search',
    text: searchText,
    disabled: !isEmbeddingComputed
  } as SearchItem;
  $: searchItems = $concepts?.data
    ? [
        ...(searchText != '' ? [keywordSearchItem] : []),
        ...(searchText != '' && selectedEmbedding ? [semanticSearchItem] : []),
        newConceptItem,
        ...fieldSearchItems,
        ...namespaceConcepts.flatMap(namespaceConcept =>
          namespaceConcept.concepts.map(c => ({
            id: {namespace: c.namespace, name: c.name, type: 'concept'} as ConceptId,
            text: conceptDisplayName(c.namespace, c.name, $authInfo.data),
            description: c.description,
            disabled:
              !isEmbeddingComputed ||
              searches.some(
                s =>
                  s.type === 'concept' &&
                  s.concept_namespace === c.namespace &&
                  s.concept_name === c.name
              )
          }))
        )
      ]
    : [];

  const selectEmbedding = (e: Event) => {
    selectedEmbedding = (e.target as HTMLInputElement).value;
    datasetViewStore.setSearchEmbedding((e.target as HTMLInputElement).value);
  };
  const computeEmbedding = () => {
    if (selectedEmbedding == null) return;
    isWaitingForIndexing[indexingKey(searchPath, selectedEmbedding)] = true;
    $signalMutation.mutate([
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
  const searchConcept = (namespace: string, name: string) => {
    if (searchPath == null || selectedEmbedding == null) return;
    datasetViewStore.addSearch({
      path: searchPath,
      type: 'concept',
      concept_namespace: namespace,
      concept_name: name,
      embedding: selectedEmbedding
    });
    conceptComboBox.clear();
  };

  const selectSearchItem = (
    e: CustomEvent<{
      selectedId: SearchItem['id'];
      selectedItem: SearchItem;
    }>
  ) => {
    if (searchPath == null) return;
    if (e.detail.selectedId === 'new-concept') {
      if (searchText === newConceptItem.id) searchText = '';
      const conceptSplit = searchText.split('/', 2);
      let conceptNamespace = '';
      let conceptName = '';
      if (conceptSplit.length === 2) {
        [conceptNamespace, conceptName] = conceptSplit;
      } else {
        [conceptName] = conceptSplit;
      }
      triggerCommand({
        command: Command.CreateConcept,
        namespace: conceptNamespace,
        conceptName,
        dataset: {namespace, name: datasetName},
        path: searchPath,
        onCreate: e => searchConcept(e.detail.namespace, e.detail.name)
      });
    } else if (e.detail.selectedId === 'keyword-search') {
      if (searchText == '') {
        return;
      }
      datasetViewStore.addSearch({
        path: searchPath,
        type: 'keyword',
        query: searchText
      });
    } else if (e.detail.selectedId == 'semantic-search') {
      if (searchText == '' || selectedEmbedding == null) {
        return;
      }
      datasetViewStore.addSearch({
        path: searchPath,
        type: 'semantic',
        query: searchText,
        embedding: selectedEmbedding
      });
    } else if (e.detail.selectedId.type === 'concept') {
      searchConcept(e.detail.selectedId.namespace, e.detail.selectedId.name);
    } else if (e.detail.selectedId.type === 'field') {
      const searchItem = e.detail.selectedId as FieldId;
      if (searchItem.sort != null) {
        datasetViewStore.setSortBy(searchItem.path);
        datasetViewStore.setSortOrder(searchItem.sort);
      } else if (searchItem.op != null) {
        datasetViewStore.addFilter({
          path: searchItem.path,
          op: searchItem.op
        } as UnaryFilter);
      } else {
        throw new Error(`Unknown search type ${e.detail.selectedId}`);
      }
    } else {
      throw new Error(`Unknown search type ${e.detail.selectedId}`);
    }
    conceptComboBox.clear();
  };

  const selectField = (e: Event) => {
    datasetViewStore.setSearchPath((e.target as HTMLInputElement).value);
  };
</script>

<div class="border-1 flex w-full flex-row items-center">
  <div class="compute-embedding mr-1" class:compute-embedding-indexing={isIndexing}>
    <Button
      disabled={isEmbeddingComputed || isIndexing}
      iconDescription="Compute embedding index. This may be expensive."
      on:click={() => {
        computeEmbedding();
      }}
      icon={isEmbeddingComputed ? Checkmark : isIndexing ? InlineLoading : Chip}
    />
  </div>

  <!-- Search boxes -->
  <div class="search-container flex w-full flex-grow flex-row">
    <div class="w-full">
      <div class="flex flex-row">
        <!-- Concept input -->
        <div class="flex w-full flex-row items-start justify-items-start">
          <div class="flex-grow">
            <ComboBox
              size="xl"
              bind:this={conceptComboBox}
              items={searchItems}
              bind:value={searchText}
              on:select={selectSearchItem}
              shouldFilterItem={(item, value) =>
                item.text.toLowerCase().includes(value.toLowerCase()) || item.id === 'new-concept'}
              placeholder={placeholderText}
              let:item={it}
            >
              {@const item = searchItems.find(p => p.id === it.id)}
              {@const isSignal =
                item != null &&
                typeof item.id === 'object' &&
                item.id.type === 'field' &&
                item.id.isSignal}
              {@const isConcept =
                item != null && typeof item.id === 'object' && item.id.type === 'concept'}
              {#if item == null}
                <div />
              {:else if item.id === 'new-concept'}
                <div class="new-concept flex flex-row items-center justify-items-center">
                  <Tag><Add /></Tag>
                  <div class="ml-2">
                    New concept{searchText != '' ? ':' : ''}
                    {searchText}
                  </div>
                </div>
              {:else if item.id === 'keyword-search'}
                <div class="new-keyword flex flex-row items-center justify-items-center">
                  <Tag><SearchAdvanced /></Tag>
                  <div class="ml-2">
                    Keyword search:
                    {searchText}
                  </div>
                </div>
              {:else if item.id === 'semantic-search'}
                <div class="new-keyword flex flex-row items-center justify-items-center">
                  <Tag><SearchAdvanced /></Tag>
                  <div class="ml-2">
                    Semantic search:
                    {searchText}
                  </div>
                </div>
              {:else}
                <div class="flex justify-between gap-x-8" class:isSignal class:isConcept>
                  <div>{item.text}</div>
                  {#if item.description}
                    <div class="truncate text-xs text-gray-500">{item.description}</div>
                  {/if}
                </div>
              {/if}
            </ComboBox>
          </div>
        </div>
      </div>
    </div>
  </div>
  <div class="mx-1" use:hoverTooltip={{text: 'Select the field to search over.'}}>
    {#key visibleStringPaths}
      <Select
        size="xl"
        class="field-select w-48"
        selected={searchPath ? serializePath(searchPath) : ''}
        on:change={selectField}
        disabled={visibleStringPaths.length === 0}
        warn={visibleStringPaths.length === 0}
      >
        {#each visibleStringPaths as field}
          <SelectItem value={serializePath(field)} text={serializePath(field)} />
        {/each}
      </Select>
    {/key}
  </div>
  <div class="embedding-select flex flex-row">
    <div class="w-32" use:hoverTooltip={{text: 'Select the embedding to use.'}}>
      <Select
        size="xl"
        on:change={selectEmbedding}
        selected={selectedEmbedding || ''}
        name={selectedEmbedding || ''}
      >
        {#each $embeddings.data || [] as embedding}
          <SelectItem value={embedding.name} text={embedding.name} />
        {/each}
      </Select>
    </div>
  </div>
</div>

<style lang="postcss">
  :global(.bx--form__helper-text) {
    padding: 0 0 0 1rem;
  }
  :global(.compute-embedding .bx--btn) {
    @apply h-12;
  }
  :global(.compute-embedding-indexing .bx--btn.bx--btn--disabled) {
    @apply text-transparent;
  }
  :global(.embedding-select .bx--select, .field-select .bx--select) {
    @apply flex-row;
  }
  :global(.new-concept .bx--tag, .new-keyword .bx--tag) {
    @apply w-6 min-w-0 px-0;
  }
  :global(.new-concept, .new-keyword) {
    @apply h-full;
  }

  /* Style the combobox item's parent div with a background color depending on type of search. */
  :global(.bx--list-box__menu-item:not(.bx--list-box__menu-item--highlighted):has(.isSignal)) {
    @apply bg-blue-50;
  }
  :global(.bx--list-box__menu-item:not(.bx--list-box__menu-item--highlighted):has(.isConcept)) {
    @apply bg-emerald-100;
  }
</style>
