<script lang="ts">
  import {getDatasetViewContext} from '$lib/store/datasetViewStore';
  import {
    isConceptScoreSignal,
    isSignalTransform,
    pathIsEqual,
    type Column,
    type Path
  } from '$lilac';
  import {Checkbox, Tag} from 'carbon-components-svelte';
  import ContextMenu from '../contextMenu/ContextMenu.svelte';
  import SchemaFieldMenu from '../contextMenu/SchemaFieldMenu.svelte';

  export let column: Column;
  export let indent = 0;

  const datasetViewStore = getDatasetViewContext();

  $: path =
    column.transform &&
    isSignalTransform(column.transform) &&
    isConceptScoreSignal(column.transform.signal)
      ? [
          ...(column.feature.slice(0, -1) as Path),
          `${column.transform.signal.namespace}/${column.transform.signal.concept_name}`
        ]
      : [];

  $: isVisible = $datasetViewStore.visibleColumns.some(p => pathIsEqual(p, path));
  $: transform = column.transform;
</script>

<div
  class="flex w-full flex-row items-center border-b border-solid border-gray-200 py-2 hover:bg-gray-100"
>
  <div class="w-6">
    <Checkbox
      labelText="Show"
      hideLabel
      selected={isVisible}
      on:check={ev => {
        if (ev.detail) {
          datasetViewStore.addVisibleColumn(path);
        } else {
          datasetViewStore.removeVisibleColumn(path);
        }
      }}
    />
  </div>
  <div class="w-6" style:margin-left={indent * 24 + 'px'} />
  <div class="grow truncate whitespace-nowrap text-gray-900">
    {#if transform && isSignalTransform(transform)}
      {transform.signal.signal_name}
      {#if isConceptScoreSignal(transform.signal)}
        ({transform.signal.concept_name})
      {/if}
    {:else}
      Unknown signal
    {/if}
  </div>

  <div>
    <Tag type="green">Preview</Tag>
  </div>
  <div class="w-24 pr-2 text-right" />
  <div>
    <ContextMenu>
      <SchemaFieldMenu {column} />
    </ContextMenu>
  </div>
</div>
