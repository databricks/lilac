<script lang="ts">
  import {page} from '$app/stores';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {isSignalField, type LilacSchema, type LilacSchemaField} from '$lilac';
  import {OverflowMenuItem} from 'carbon-components-svelte';
  import {Command, triggerCommand} from '../commands/Commands.svelte';

  export let field: LilacSchemaField;
  export let schema: LilacSchema;
  const datasetViewStore = getDatasetViewContext();
</script>

{#if !isSignalField(field, schema)}
  <OverflowMenuItem
    text="Preview signal"
    on:click={() =>
      triggerCommand({
        command: Command.PreviewConcept,
        namespace: $page.params.namespace,
        datasetName: $page.params.datasetName,
        path: field?.path
      })}
  />
  <OverflowMenuItem
    text="Compute signal"
    on:click={() =>
      triggerCommand({
        command: Command.ComputeSignal,
        namespace: $page.params.namespace,
        datasetName: $page.params.datasetName,
        path: field?.path
      })}
  />
{/if}

{#if field.dtype}
  <OverflowMenuItem
    text="Sort by"
    on:click={() => datasetViewStore.addSortBy(field.alias || field.path)}
  />
  <OverflowMenuItem
    text="Filter"
    on:click={() =>
      triggerCommand({
        command: Command.EditFilter,
        namespace: $page.params.namespace,
        datasetName: $page.params.datasetName,
        path: field.path
      })}
  />
{/if}
