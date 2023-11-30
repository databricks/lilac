<script lang="ts">
  import {querySelectRowsSchema} from '$lib/queries/datasetQueries';
  import {
    getDatasetViewContext,
    getSelectRowsSchemaOptions,
    type DatasetViewState
  } from '$lib/stores/datasetViewStore';
  import {getDisplayPath, shortPath} from '$lib/view_utils';
  import {
    ROWID,
    deserializePath,
    pathIsEqual,
    petals,
    serializePath,
    type LilacSchema,
    type Path,
    type SearchResultInfo,
    type SortResult
  } from '$lilac';
  import type {
    DropdownItem,
    DropdownItemId
  } from 'carbon-components-svelte/types/Dropdown/Dropdown.svelte';
  import {SortAscending, SortDescending} from 'carbon-icons-svelte';
  import DropdownPill from '../common/DropdownPill.svelte';
  import {hoverTooltip} from '../common/HoverTooltip';

  let datasetViewStore = getDatasetViewContext();
  $: selectRowsSchema = querySelectRowsSchema(
    $datasetViewStore.namespace,
    $datasetViewStore.datasetName,
    getSelectRowsSchemaOptions($datasetViewStore)
  );

  let open = false;

  function getSort(viewState: DatasetViewState): SortResult | null {
    // Explicit user selection of sort.
    if (viewState.query.sort_by && viewState.query.sort_by.length > 0) {
      return {
        path: deserializePath(viewState.query.sort_by[0]),
        order: viewState.query.sort_order || 'DESC'
      };
    }
    // Implicit sort from select rows schema.
    const sort = ($selectRowsSchema?.data?.sorts || [])[0];
    if (sort == null || pathIsEqual(sort.path, [ROWID])) {
      return null;
    }
    return sort;
  }

  $: sort = getSort($datasetViewStore);
  let pathToSearchResult: {[path: string]: SearchResultInfo} = {};
  $: {
    for (const search of $selectRowsSchema?.data?.search_results || []) {
      pathToSearchResult[serializePath(search.result_path)] = search;
    }
  }

  interface SortByItem extends DropdownItem {
    path: Path;
  }

  $: selectedId = sort?.path && serializePath(sort.path);

  function makeItems(schema: LilacSchema, open: boolean): SortByItem[] {
    return petals(schema)
      .filter(f => f.dtype?.type != 'embedding' && f.dtype?.type != 'string_span')
      .map(field => {
        return {
          id: serializePath(field.path),
          path: field.path,
          text: open ? getDisplayPath(field.path) : shortPath(field.path),
          disabled: false
        };
      });
  }
  $: items = $selectRowsSchema.data && makeItems($selectRowsSchema.data.schema, open);

  const selectSort = (
    ev: CustomEvent<{
      selectedId: DropdownItemId;
      selectedItem: DropdownItem;
    }>
  ) => {
    if (ev.detail.selectedId == null) {
      datasetViewStore.clearSorts();
      return;
    }
    const sortItem = ev.detail.selectedItem as SortByItem;
    datasetViewStore.setSortBy(sortItem.path);
    selectedId = ev.detail.selectedId;
  };
  const toggleSortOrder = () => {
    // Set the sort given by the select rows schema explicitly.
    if (sort != null) {
      datasetViewStore.setSortBy(sort.path);
    }
    datasetViewStore.setSortOrder(sort?.order === 'ASC' ? 'DESC' : 'ASC');
  };
</script>

<div class="sort-container flex flex-row items-center gap-x-1 md:w-fit">
  <DropdownPill bind:open title="Sort" on:select={selectSort} {selectedId} {items} let:item>
    <div slot="icon">
      <button
        use:hoverTooltip={{
          text:
            sort?.order === 'ASC'
              ? 'Sorted ascending. Toggle to switch to descending.'
              : 'Sorted descending. Toggle to switch to ascending.'
        }}
        class="px-1 py-2"
        disabled={sort == null}
        on:click={toggleSortOrder}
      >
        {#if sort?.order === 'ASC'}
          <SortAscending />
        {:else}
          <SortDescending />
        {/if}
      </button>
    </div>

    {@const sortItem = items?.find(x => x === item)}
    {#if sortItem}
      <div title={sortItem.text} class="truncate text-sm">{sortItem.text}</div>
    {/if}
  </DropdownPill>
</div>
