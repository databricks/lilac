<script lang="ts">
  import {getDatasetContext, type DatasetState} from '$lib/stores/datasetStore';
  import {getDatasetViewContext, type DatasetViewState} from '$lib/stores/datasetViewStore';
  import {displayPath, shortPath} from '$lib/view_utils';
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
  import DropPill from '../common/DropPill.svelte';
  import {hoverTooltip} from '../common/HoverTooltip';

  let datasetViewStore = getDatasetViewContext();
  let datasetStore = getDatasetContext();
  let open = false;

  function getSort(state: DatasetState, viewState: DatasetViewState): SortResult | null {
    // Explicit user selection of sort.
    if (viewState.query.sort_by && viewState.query.sort_by.length > 0) {
      return {
        path: deserializePath(viewState.query.sort_by[0]),
        order: viewState.query.sort_order || 'DESC'
      };
    }
    // Implicit sort from select rows schema.
    const sort = (state.selectRowsSchema?.data?.sorts || [])[0];
    if (sort == null || pathIsEqual(sort.path, [ROWID])) {
      return null;
    }
    return sort;
  }

  $: sort = getSort($datasetStore, $datasetViewStore);
  let pathToSearchResult: {[path: string]: SearchResultInfo} = {};
  $: {
    for (const search of $datasetStore.selectRowsSchema?.data?.search_results || []) {
      pathToSearchResult[serializePath(search.result_path)] = search;
    }
  }

  interface SortByItem extends DropdownItem {
    path: Path;
  }

  $: selectedId = sort?.path && serializePath(sort.path);

  $: schema = $datasetStore?.selectRowsSchema?.data?.schema;

  function makeItems(schema: LilacSchema, open: boolean): SortByItem[] {
    return petals(schema)
      .filter(f => f.dtype != 'embedding' && f.dtype != 'string_span')
      .map(field => {
        return {
          id: serializePath(field.path),
          path: field.path,
          text: open ? displayPath(field.path) : shortPath(field.path),
          disabled: false
        };
      });
  }
  $: items = schema && makeItems(schema, open);

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
  <DropPill bind:open title="Sort" on:select={selectSort} {selectedId} {items} let:item>
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
  </DropPill>
</div>
