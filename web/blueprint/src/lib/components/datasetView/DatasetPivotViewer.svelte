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
  $: groups = ($outerCountQuery?.data?.counts || []).map(([name, count], i) => {
    const textHighlights = getSearchHighlighting(name, searchText);
    const hasMatchingSearch = textHighlights.some(x => x.isBold);
    return {
      name,
      count,
      percentage: getPercentage(count),
      textHighlights,
      hasMatchingSearch
    };
  });

  $: noResults =
    groupCounts.length === groups.length &&
    groupCounts.every(count => count === 0) &&
    !groups.some(group => group.hasMatchingSearch);

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
    loadIndex = 0;
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
        {#each groups as group, i}
          {@const groupLink = datasetLink($store.namespace, $store.datasetName, {
            ...$store,
            viewPivot: false,
            pivot: undefined,
            query: {
              ...$store.query
            },
            groupBy: {path: outerLeafPath, value: group.name}
          })}

          {@const shouldShow =
            (groupCounts[i] != null && groupCounts[i] > 0) || group.hasMatchingSearch}
          <div
            class="flex w-full flex-row"
            class:mb-4={shouldShow}
            class:px-4={shouldShow}
            class:mb-10={shouldShow}
          >
            <div
              class="mx-11 flex w-48 flex-col items-center justify-center gap-y-4 py-1"
              class:hidden={!shouldShow}
            >
              <div class="mx-2 whitespace-break-spaces text-center text-2xl">
                {#each group.textHighlights as highlight}
                  {#if highlight.isBold}<span class="font-bold">{highlight.text}</span>
                  {:else}<span>{highlight.text}</span>{/if}
                {/each}
              </div>
              <div class="flex flex-col font-light">
                <span class="ml-2 text-xl text-neutral-800">
                  {group.percentage}%
                </span>
                <span class="ml-2 text-neutral-500">
                  {group.count} rows
                </span>
              </div>
              <div class="">
                <a class="flex flex-row" href={groupLink}>
                  Explore
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
              </div>
            </div>

            {#if innerLeafPath && innerLeafPath.length > 0}
              {#key searchText}
                <DatasetPivotResult
                  shouldLoad={loadIndex >= i}
                  on:load={({detail}) => {
                    // Serially load in the order of results on the page so we don't overwhelm the
                    // server.
                    loadIndex = i + 1;
                    groupCounts[i] = detail.count;
                    groupCounts = groupCounts;
                  }}
                  filter={group.name == null
                    ? {path: outerLeafPath, op: 'not_exists'}
                    : {path: outerLeafPath, op: 'equals', value: group.name}}
                  path={innerLeafPath}
                  parentValue={group.name}
                  {numRowsInQuery}
                  searchText={//
                  // When the parent matches the text, we don't pass the search
                  // text to the child for filtering so it shows all results.
                  !group.hasMatchingSearch ? searchText : undefined}
                />
              {/key}
            {/if}
          </div>
        {/each}
      </div>
    {/if}
    {#if noResults}
      <div class="mx-20 mt-8 w-full text-lg text-gray-600">No results.</div>
    {/if}
  </div>
</div>
