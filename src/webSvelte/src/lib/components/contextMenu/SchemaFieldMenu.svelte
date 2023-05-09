<script lang="ts">
  import {page} from '$app/stores';
  import {getDatasetViewContext} from '$lib/store/datasetViewStore';
  import {isSignalTransform, type Column, type LilacSchemaField, type Path} from '$lilac';
  import {OverflowMenuItem} from 'carbon-components-svelte';
  import {Command, triggerCommand} from '../commands/Commands.svelte';

  export let field: LilacSchemaField | undefined = undefined;
  export let column: Column | undefined = undefined;

  // Have to cast to Path because column.feature is (string|number)[]
  let columnPath = column?.feature as Path | undefined;

  const datsetViewStore = getDatasetViewContext();
</script>

{#if field}
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

{#if column}
  <OverflowMenuItem
    text="Remove"
    on:click={() => column && datsetViewStore.removeExtraColumn(column)}
  />
  {#if isSignalTransform(column.transform)}
    {@const signal = column.transform.signal}
    <OverflowMenuItem
      text="Compute"
      on:click={() =>
        triggerCommand({
          command: Command.ComputeSignal,
          namespace: $page.params.namespace,
          datasetName: $page.params.datasetName,
          path: columnPath,
          signalName: signal.signal_name
        })}
    />
  {/if}
{/if}
