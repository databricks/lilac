<script lang="ts">
  import {page} from '$app/stores';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import type {LilacSchemaField} from '$lilac';
  import {OverflowMenuItem} from 'carbon-components-svelte';
  import {Command, triggerCommand} from '../commands/Commands.svelte';

  export let field: LilacSchemaField;
  const datasetViewStore = getDatasetViewContext();
</script>

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

<OverflowMenuItem text="Sort by" on:click={() => datasetViewStore.addSortBy(field.path)} />
