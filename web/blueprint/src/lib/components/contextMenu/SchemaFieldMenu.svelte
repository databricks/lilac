<script lang="ts">
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {
    isFilterableField,
    isSignalField,
    isSortableField,
    type LilacField,
    type LilacSchema
  } from '$lilac';
  import {OverflowMenuItem} from 'carbon-components-svelte';
  import {Command, triggerCommand} from '../commands/Commands.svelte';

  export let field: LilacField;
  export let schema: LilacSchema;
  const datasetViewStore = getDatasetViewContext();
</script>

<OverflowMenuItem
  text="Sort by"
  disabled={!isSortableField(field)}
  on:click={() => datasetViewStore.addSortBy(field.path)}
/>
<OverflowMenuItem
  text="Filter"
  disabled={!isFilterableField(field)}
  on:click={() =>
    triggerCommand({
      command: Command.EditFilter,
      namespace: $datasetViewStore.namespace,
      datasetName: $datasetViewStore.datasetName,
      path: field.path
    })}
/>
<OverflowMenuItem
  text="Compute embedding"
  disabled={isSignalField(field, schema)}
  on:click={() =>
    triggerCommand({
      command: Command.ComputeEmbedding,
      namespace: $datasetViewStore.namespace,
      datasetName: $datasetViewStore.datasetName,
      path: field?.path
    })}
/>
<OverflowMenuItem
  text="Preview signal"
  disabled={isSignalField(field, schema)}
  on:click={() =>
    triggerCommand({
      command: Command.PreviewConcept,
      namespace: $datasetViewStore.namespace,
      datasetName: $datasetViewStore.datasetName,
      path: field?.path
    })}
/>
<OverflowMenuItem
  text="Compute signal"
  disabled={isSignalField(field, schema)}
  on:click={() =>
    triggerCommand({
      command: Command.ComputeSignal,
      namespace: $datasetViewStore.namespace,
      datasetName: $datasetViewStore.datasetName,
      path: field?.path
    })}
/>

<style lang="postcss">
  :global(ul.bx--overflow-menu-options) {
    @apply w-44;
  }
</style>
