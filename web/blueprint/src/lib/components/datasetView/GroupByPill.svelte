<script lang="ts">
  import {queryDatasetSchema} from '$lib/queries/datasetQueries';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {getDisplayPath, shortPath} from '$lib/view_utils';
  import {childFields, isNumeric, serializePath, type LilacField} from '$lilac';
  import type {
    DropdownItem,
    DropdownItemId
  } from 'carbon-components-svelte/types/Dropdown/Dropdown.svelte';
  import {Folder} from 'carbon-icons-svelte';
  import DropdownPill from '../common/DropdownPill.svelte';

  const datasetViewStore = getDatasetViewContext();
  let open = false;
  $: selectedId = $datasetViewStore.groupBy ? serializePath($datasetViewStore.groupBy.path) : null;
  $: selectedPath = $datasetViewStore.groupBy?.path;
  $: schema = queryDatasetSchema($datasetViewStore.namespace, $datasetViewStore.datasetName);

  $: categoricalFields = $schema.data
    ? childFields($schema.data).filter(
        f =>
          f.dtype != null &&
          (f.categorical || !isNumeric(f.dtype)) &&
          f.dtype.type !== 'string_span' &&
          f.dtype.type !== 'embedding'
      )
    : null;

  interface GroupByItem extends DropdownItem {
    field: LilacField;
  }

  function makeItems(categoricalFields: LilacField[] | null, open: boolean): GroupByItem[] {
    if (categoricalFields == null) {
      return [];
    }
    return categoricalFields.map(f => ({
      id: serializePath(f.path),
      text: open ? getDisplayPath(f.path) : shortPath(f.path),
      field: f
    }));
  }
  $: items = makeItems(categoricalFields, open);

  function selectItem(
    e: CustomEvent<{
      selectedId: DropdownItemId;
      selectedItem: DropdownItem;
    }>
  ) {
    if (e.detail.selectedId == null) {
      datasetViewStore.setGroupBy(null, null);
      return;
    }
    const groupByItem = e.detail.selectedItem as GroupByItem;
    datasetViewStore.setGroupBy(groupByItem.field.path, null);
    selectedId = e.detail.selectedId;
  }
</script>

<DropdownPill
  title="Group by"
  {items}
  bind:open
  on:select={selectItem}
  {selectedId}
  tooltip={selectedPath ? `Grouping by ${getDisplayPath(selectedPath)}` : null}
  let:item
>
  <div slot="icon"><Folder title="Group by" /></div>
  {@const groupByItem = items?.find(x => x === item)}
  {#if groupByItem}
    <div class="flex items-center justify-between gap-x-1">
      <span title={groupByItem.text} class="truncate text-sm">{groupByItem.text}</span>
    </div>
  {/if}
</DropdownPill>
