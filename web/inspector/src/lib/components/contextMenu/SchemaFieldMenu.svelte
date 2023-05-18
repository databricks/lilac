<script lang="ts">
  import {page} from '$app/stores';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {
    isFilterableField,
    isSignalField,
    isSortableField,
    type LilacSchema,
    type LilacSchemaField
  } from '$lilac';
  import {OverflowMenuItem} from 'carbon-components-svelte';
  import {Command, triggerCommand} from '../commands/Commands.svelte';

  export let field: LilacSchemaField;
  export let schema: LilacSchema;
  const datasetViewStore = getDatasetViewContext();
</script>

<OverflowMenuItem
  text="Sort by"
  disabled={!isSortableField(field)}
  on:click={() => datasetViewStore.addSortBy(field.alias || field.path)}
/>
<OverflowMenuItem
  text="Filter"
  disabled={!isFilterableField(field)}
  on:click={() =>
    triggerCommand({
      command: Command.EditFilter,
      namespace: $page.params.namespace,
      datasetName: $page.params.datasetName,
      path: field.path
    })}
/>

<OverflowMenuItem
  text="Preview signal"
  disabled={isSignalField(field, schema)}
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
  disabled={isSignalField(field, schema)}
  on:click={() =>
    triggerCommand({
      command: Command.ComputeSignal,
      namespace: $page.params.namespace,
      datasetName: $page.params.datasetName,
      path: field?.path
    })}
/>
