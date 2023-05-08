<script lang="ts">
  import { page } from '$app/stores';
  import { isSignalField, type LilacSchemaField } from '$lilac';
  import { OverflowMenuItem } from 'carbon-components-svelte';
  import { Command, triggerCommand } from '../commands/Commands.svelte';

  export let field: LilacSchemaField;
</script>

{#if isSignalField(field)}
  <!-- <OverflowMenuItem text="Manage credentials" /> -->
{:else}
  <OverflowMenuItem
    text="Add Signal"
    on:click={() =>
      triggerCommand({
        command: Command.ComputeSignal,
        namespace: $page.params.namespace,
        datasetName: $page.params.datasetName,
        path: field.path
      })}
  />
{/if}
