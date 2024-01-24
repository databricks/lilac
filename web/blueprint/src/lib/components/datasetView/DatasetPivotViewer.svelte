<script lang="ts">
  import {
    DATASETS_TAG,
    queryDatasetSchema,
    querySelectRows,
    querySelectRowsSchema
  } from '$lib/queries/datasetQueries';
  import {createApiQuery} from '$lib/queries/queryUtils';
  import {
    getDatasetViewContext,
    getSelectRowsOptions,
    getSelectRowsSchemaOptions
  } from '$lib/stores/datasetViewStore';
  import {datasetLink} from '$lib/utils';
  import {getDisplayPath, getSearchHighlighting} from '$lib/view_utils';
  import {
    DatasetsService,
    ROWID,
    childFields,
    deserializePath,
    isSignalField,
    serializePath,
    type Path,
    type PivotResult
  } from '$lilac';
  import {SkeletonText, TextInput} from 'carbon-components-svelte';
  import type {
    DropdownItem,
    DropdownItemId
  } from 'carbon-components-svelte/types/Dropdown/Dropdown.svelte';
  import {Close, Search} from 'carbon-icons-svelte';
  import DropdownPill from '../common/DropdownPill.svelte';
  import {hoverTooltip} from '../common/HoverTooltip';
  import DatasetPivotResult, {type OuterPivot} from './DatasetPivotResult.svelte';

  let outerLeafPath: Path | undefined = undefined;
  let innerLeafPath: Path | undefined = undefined;

  const store = getDatasetViewContext();
  $: schema = queryDatasetSchema($store.namespace, $store.datasetName);
  $: selectRowsSchema = querySelectRowsSchema(
    $store.namespace,
    $store.datasetName,
    getSelectRowsSchemaOptions($store, $schema.data)
  );

  $: fields = $selectRowsSchema.data?.schema
    ? childFields($selectRowsSchema.data.schema).filter(
        f => !isSignalField(f) && f.dtype != null && f.path[0] !== ROWID
      )
    : null;

  $: selectOptions = getSelectRowsOptions($store, $selectRowsSchema.data?.schema);
  $: rowsQuery = querySelectRows(
    $store.namespace,
    $store.datasetName,
    {...selectOptions, columns: [ROWID], limit: 1},
    $selectRowsSchema.data?.schema
  );
  $: numRowsInQuery = $rowsQuery.data?.total_num_rows;

  $: pivotQueryFn = createApiQuery(DatasetsService.pivot, DATASETS_TAG, {
    enabled: outerLeafPath != null && innerLeafPath != null
  });
  $: pivotQuery = pivotQueryFn($store.namespace, $store.datasetName, {
    outer_path: outerLeafPath!,
    inner_path: innerLeafPath!,
    filters: selectOptions.filters
  });

  // The search text after a user presses the search button or enter.
  $: searchText = $store.pivot?.searchText;

  function getGroups(
    pivotTable: PivotResult | undefined,
    searchQuery: string | undefined
  ): OuterPivot[] | undefined {
    if (pivotTable == null) return undefined;
    searchQuery = searchQuery?.trim().toLowerCase();
    const groups = pivotTable.outer_groups.map(outerGroup => ({
      value: outerGroup.value,
      count: outerGroup.count,
      percentage: getPercentage(outerGroup.count),
      textHighlights: getSearchHighlighting(outerGroup.value, searchText),
      inner: outerGroup.inner
        .filter(x => searchQuery == null || x[0].toLowerCase().includes(searchQuery))
        .map(([innerValue, innerCount]) => ({
          value: innerValue,
          count: innerCount,
          textHighlights: getSearchHighlighting(innerValue, searchText)
        }))
    }));
    // Filter out groups with no inner groups and no match on the search query.
    return groups.filter(
      group =>
        group.inner.length > 0 ||
        (searchQuery != null && group.value?.toLowerCase().includes(searchQuery))
    );
  }

  $: groups = getGroups($pivotQuery?.data, $store.pivot?.searchText);

  function getPercentage(count: number) {
    if (numRowsInQuery == null) return '';
    return ((count / numRowsInQuery) * 100).toFixed(2);
  }

  $: {
    // Auto-select the first field.
    if (fields != null && fields.length > 0 && outerLeafPath == null) {
      if ($store.pivot?.outerPath != null) {
        outerLeafPath = $store.pivot.outerPath;
      } else {
        outerLeafPath = fields[0].path;
      }
      if ($store.pivot?.innerPath != null) {
        innerLeafPath = $store.pivot.innerPath;
      } else {
        innerLeafPath = fields[1].path;
      }
    }
  }

  $: dropdownFields = fields?.map(field => ({
    id: serializePath(field.path),
    text: getDisplayPath(field.path)
  }));

  function selectInnerPath(
    e: CustomEvent<{
      selectedId: DropdownItemId;
      selectedItem: DropdownItem;
    }>
  ) {
    innerLeafPath = e.detail.selectedId != null ? deserializePath(e.detail.selectedId) : undefined;
    $store.pivot = {...$store.pivot, innerPath: innerLeafPath};
  }
  function selectOuterPath(
    e: CustomEvent<{
      selectedId: DropdownItemId;
      selectedItem: DropdownItem;
    }>
  ) {
    outerLeafPath = e.detail.selectedId != null ? deserializePath(e.detail.selectedId) : undefined;
    $store.pivot = {...$store.pivot, outerPath: outerLeafPath};
  }

  // The bound input text from the search box.
  let inputSearchText: string | undefined = undefined;
  function searchInput(e: CustomEvent<string | number | null>) {
    inputSearchText = e.detail?.toString();
  }

  function search() {
    $store.pivot = {...$store.pivot, searchText: inputSearchText};
  }

  function clearSearch() {
    inputSearchText = undefined;
    search();
  }
</script>

<div class="flex h-full flex-col">
  <div class="mb-8 flex h-16 w-full flex-row justify-between justify-items-center gap-x-4">
    <div class="ml-8 mt-4 flex w-96 items-center gap-x-2">
      <Search />
      <TextInput
        value={searchText}
        on:input={searchInput}
        placeholder="Search all categories and titles"
        on:change={search}
        size="xl"
      />
      <div use:hoverTooltip={{text: 'Clear search query'}}>
        <button on:click={clearSearch}><Close /></button>
      </div>
    </div>
    <div class="mr-8 flex flex-row gap-x-4 py-2 pr-4">
      <div class="flex flex-col gap-y-2">
        <div>Explore</div>
        <DropdownPill
          title="Explore"
          items={dropdownFields}
          direction="left"
          on:select={selectInnerPath}
          selectedId={innerLeafPath && serializePath(innerLeafPath)}
          tooltip={innerLeafPath ? `Grouping by ${getDisplayPath(innerLeafPath)}` : null}
          let:item
        >
          {@const slotItem = dropdownFields?.find(x => x === item)}
          {#if slotItem}
            <div class="flex items-center justify-between gap-x-1">
              <span title={slotItem.text} class="truncate text-sm">{slotItem.text}</span>
            </div>
          {/if}
        </DropdownPill>
      </div>
      <div class="flex flex-col gap-y-2">
        <div>Grouped by</div>
        <DropdownPill
          title="Grouped by"
          items={dropdownFields}
          direction="left"
          on:select={selectOuterPath}
          selectedId={outerLeafPath && serializePath(outerLeafPath)}
          tooltip={outerLeafPath ? `Grouped by ${getDisplayPath(outerLeafPath)}` : null}
          let:item
        >
          {@const slotItem = dropdownFields?.find(x => x === item)}
          {#if slotItem}
            <div class="flex items-center justify-between gap-x-1">
              <span title={slotItem.text} class="truncate text-sm">{slotItem.text}</span>
            </div>
          {/if}
        </DropdownPill>
      </div>
    </div>
  </div>

  <div class="flex flex-row overflow-y-scroll px-8">
    {#if innerLeafPath == null}
      <div class="mx-20 mt-8 w-full text-lg text-gray-600">Select a field to explore.</div>
    {:else if outerLeafPath == null}
      <div class="mx-20 mt-8 w-full text-lg text-gray-600">Select a field to group by.</div>
    {:else if groups == null || numRowsInQuery == null}
      <SkeletonText />
    {:else}
      <div class="flex w-full flex-col gap-y-10">
        {#each groups as group}
          {@const groupLink = datasetLink($store.namespace, $store.datasetName, {
            ...$store,
            viewPivot: false,
            pivot: undefined,
            query: {
              ...$store.query
            },
            groupBy: outerLeafPath ? {path: outerLeafPath, value: group.value} : undefined
          })}

          <div class="flex w-full flex-row">
            <div class="mb-4 flex w-48 flex-col items-center justify-between gap-y-4 p-6">
              <div
                class="mx-2 h-16 whitespace-break-spaces py-0.5 text-center text-2xl leading-7 tracking-tight"
              >
                {#each group.textHighlights as highlight}
                  {#if highlight.isBold}<span class="font-bold">{highlight.text}</span>
                  {:else}<span>{highlight.text}</span>{/if}
                {/each}
              </div>
              <div class="flex w-full flex-col items-center font-light">
                <span class="ml-2 text-xl text-neutral-800">
                  {group.percentage}%
                </span>
                <span class="ml-2 text-neutral-500">
                  {group.count.toLocaleString()} rows
                </span>
              </div>
              <a class="flex flex-row" href={groupLink}>
                <button class="border border-neutral-300">Explore</button></a
              >
            </div>

            {#if outerLeafPath && innerLeafPath && numRowsInQuery}
              <DatasetPivotResult
                filter={group.value == null
                  ? {path: outerLeafPath, op: 'not_exists'}
                  : {path: outerLeafPath, op: 'equals', value: group.value}}
                {group}
                path={innerLeafPath}
                {numRowsInQuery}
              />
            {/if}
          </div>
        {:else}
          <div class="mx-20 mt-8 w-full text-lg text-gray-600">No results.</div>
        {/each}
      </div>
    {/if}
  </div>
</div>
