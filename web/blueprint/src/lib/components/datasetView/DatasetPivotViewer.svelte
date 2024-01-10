<script lang="ts">
  import {
    querySelectGroups,
    querySelectRows,
    querySelectRowsSchema
  } from '$lib/queries/datasetQueries';
  import {
    getDatasetViewContext,
    getSelectRowsOptions,
    getSelectRowsSchemaOptions
  } from '$lib/stores/datasetViewStore';
  import {datasetLink} from '$lib/utils';
  import {getDisplayPath, getSearchHighlighting} from '$lib/view_utils';
  import {
    ROWID,
    childFields,
    deserializePath,
    isSignalField,
    serializePath,
    type Path
  } from '$lilac';
  import {Search, SkeletonText} from 'carbon-components-svelte';
  import type {
    DropdownItem,
    DropdownItemId
  } from 'carbon-components-svelte/types/Dropdown/Dropdown.svelte';
  import DropdownPill from '../common/DropdownPill.svelte';
  import DatasetPivotResult from './DatasetPivotResult.svelte';

  let outerLeafPath: Path | undefined = undefined; // = ['source'];
  let innerLeafPath: Path | undefined = undefined; // ['prompt_cluster', 'topic'];

  const store = getDatasetViewContext();

  $: selectRowsSchema = querySelectRowsSchema(
    $store.namespace,
    $store.datasetName,
    getSelectRowsSchemaOptions($store)
  );

  $: fields = $selectRowsSchema.data?.schema
    ? childFields($selectRowsSchema.data.schema).filter(
        f => !isSignalField(f) && f.dtype != null && f.path[0] !== ROWID
      )
    : null;

  $: selectOptions = getSelectRowsOptions($store);
  $: rowsQuery = querySelectRows(
    $store.namespace,
    $store.datasetName,
    {...selectOptions, columns: [ROWID], limit: 1},
    $selectRowsSchema.data?.schema
  );
  $: numRowsInQuery = $rowsQuery.data?.total_num_rows;

  // Get the total count for the dataset.
  $: outerCountQuery =
    outerLeafPath != null
      ? querySelectGroups($store.namespace, $store.datasetName, {
          leaf_path: outerLeafPath,
          filters: selectOptions.filters,
          // Explicitly set the limit to null to get all the groups, not just the top 100.
          limit: null
        })
      : null;
  $: outerCounts = ($outerCountQuery?.data?.counts || []).map(([name, count]) => ({
    name,
    count
  }));

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
    innerLeafPath = deserializePath(e.detail.selectedId);
    $store.pivot = {...$store.pivot, innerPath: innerLeafPath};
  }
  function selectOuterPath(
    e: CustomEvent<{
      selectedId: DropdownItemId;
      selectedItem: DropdownItem;
    }>
  ) {
    outerLeafPath = deserializePath(e.detail.selectedId);
    $store.pivot = {...$store.pivot, outerPath: outerLeafPath};
  }

  // We use a loadIndex to load the inner viewers serially so we don't overwhelm the server.
  let loadIndex = 0;
  let groupCounts: number[] = [];

  // The bound input text from the search box.
  let inputSearchText: string | undefined = undefined;
  function searchInput(e: Event) {
    const value = (e.target as HTMLInputElement).value;
    inputSearchText = value != null ? value : undefined;
  }

  // The search text after a user presses the search button or enter.
  $: searchText = $store.pivot?.searchText;
  function search() {
    groupCounts = [];
    searchText = inputSearchText != null ? inputSearchText : undefined;
    $store.pivot = {...$store.pivot, searchText};
  }

  function clearSearch() {
    inputSearchText = undefined;
    search();
  }
</script>

<div class="flex h-full flex-col">
  <div class="mb-8 flex h-16 w-full flex-row justify-between justify-items-center gap-x-4">
    <div class="ml-16 mt-4 w-96">
      <Search
        value={searchText}
        on:input={searchInput}
        placeholder={`Search`}
        labelText={'text text'}
        on:change={search}
        on:clear={clearSearch}
      />
    </div>
    <div class="mx-16 flex flex-row gap-x-4 py-2">
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

  <div class="flex flex-row overflow-y-scroll">
    {#if $outerCountQuery == null || $outerCountQuery.isFetching || outerLeafPath == null}
      <SkeletonText />
    {:else}
      <div class="flex w-full flex-col">
        {#each outerCounts as outerCount, i}
          {@const groupLink = datasetLink($store.namespace, $store.datasetName, {
            ...$store,
            viewPivot: false,
            pivot: undefined,
            query: {
              ...$store.query
            },
            groupBy: {path: outerLeafPath, value: outerCount.name}
          })}
          {@const percentage = getPercentage(outerCount.count)}
          {@const textHighlights = getSearchHighlighting(outerCount.name, searchText)}
          {@const shouldShow =
            (groupCounts[i] != null && groupCounts[i] > 0) || textHighlights.some(x => x.isBold)}
          <div class="flex w-full flex-col" class:mb-4={shouldShow} class:px-4={shouldShow}>
            <div class="text-preview-overlay sticky top-0 z-50 mx-11" class:hidden={!shouldShow}>
              <div class="absolute left-0 top-0 z-10 h-full w-full bg-white" />
              <div
                class="absolute left-0 top-0 z-10 h-full w-full bg-blue-100"
                style={`width: ${percentage}%`}
              />
              <div
                class="relative left-0 top-0 z-50 py-2 leading-none tracking-tight text-gray-900"
              >
                <span class="mx-2 text-2xl">
                  {#each textHighlights as highlight}
                    {#if highlight.isBold}
                      <span class="font-bold">{highlight.text}</span>
                    {:else}
                      <span>{highlight.text}</span>
                    {/if}
                  {/each}
                  <a class="inline-block" href={groupLink}>
                    <svg
                      class="ms-2 h-3 w-3 rtl:rotate-[270deg]"
                      aria-hidden="true"
                      xmlns="http://www.w3.org/2000/svg"
                      fill="none"
                      viewBox="0 0 18 18"
                    >
                      <path
                        stroke="currentColor"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        stroke-width="2"
                        d="M15 11v4.833A1.166 1.166 0 0 1 13.833 17H2.167A1.167 1.167 0 0 1 1 15.833V4.167A1.166 1.166 0 0 1 2.167 3h4.618m4.447-2H17v5.768M9.111 8.889l7.778-7.778"
                      />
                    </svg>
                  </a>
                </span>
                <span class="ml-2 text-lg">({percentage}%)</span>
              </div>
            </div>
            <div>
              {#if innerLeafPath && innerLeafPath.length > 0}
                <DatasetPivotResult
                  shouldLoad={loadIndex >= i}
                  on:load={({detail}) => {
                    // Serially load in the order of results on the page so we don't overwhelm the
                    // server.
                    loadIndex = i + 1;
                    groupCounts[i] = detail.count;
                  }}
                  filter={outerCount.name == null
                    ? {path: outerLeafPath, op: 'not_exists'}
                    : {path: outerLeafPath, op: 'equals', value: outerCount.name}}
                  path={innerLeafPath}
                  parentValue={outerCount.name}
                  {numRowsInQuery}
                  {searchText}
                />
              {/if}
            </div>
          </div>
        {/each}
      </div>
    {/if}
  </div>
</div>
