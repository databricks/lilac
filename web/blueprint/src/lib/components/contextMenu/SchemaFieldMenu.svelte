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

{#if isSortableField(field)}
  <OverflowMenuItem text="Sort by" on:click={() => datasetViewStore.addSortBy(field.path)} />
{/if}
{#if isFilterableField(field)}
  <OverflowMenuItem
    text="Filter"
    on:click={() =>
      triggerCommand({
        command: Command.EditFilter,
        namespace: $datasetViewStore.namespace,
        datasetName: $datasetViewStore.datasetName,
        path: field.path
      })}
  />
{/if}
{#if !isSignalField(field, schema)}
  <OverflowMenuItem
    text="Compute embedding"
    on:click={() =>
      triggerCommand({
        command: Command.ComputeEmbedding,
        namespace: $datasetViewStore.namespace,
        datasetName: $datasetViewStore.datasetName,
        path: field?.path
      })}
  />
{/if}
{#if !isSignalField(field, schema)}
  <OverflowMenuItem
    text="Preview signal"
    on:click={() =>
      triggerCommand({
        command: Command.PreviewConcept,
        namespace: $datasetViewStore.namespace,
        datasetName: $datasetViewStore.datasetName,
        path: field?.path
      })}
  />
{/if}
{#if !isSignalField(field, schema)}
  <OverflowMenuItem
    text="Compute signal"
    on:click={() =>
      triggerCommand({
        command: Command.ComputeSignal,
        namespace: $datasetViewStore.namespace,
        datasetName: $datasetViewStore.datasetName,
        path: field?.path
      })}
  />
{/if}

<style lang="postcss">
  :global(ul.bx--overflow-menu-options) {
    @apply w-44;
  }
</style>
