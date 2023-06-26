<script lang="ts">
  import {deleteSignalMutation} from '$lib/queries/datasetQueries';
  import {getDatasetContext} from '$lib/stores/datasetStore';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {isPreviewSignal} from '$lib/view_utils';
  import {
    isFilterableField,
    isSignalField,
    isSignalRootField,
    isSortableField,
    serializePath,
    type LilacField,
    type LilacSchema
  } from '$lilac';
  import {Modal, OverflowMenu, OverflowMenuItem} from 'carbon-components-svelte';
  import {InProgress} from 'carbon-icons-svelte';
  import {Command, triggerCommand} from '../commands/Commands.svelte';

  export let field: LilacField;
  export let schema: LilacSchema;

  let deleteSignalOpen = false;

  const datasetViewStore = getDatasetViewContext();

  $: namespace = $datasetViewStore.namespace;
  $: datasetName = $datasetViewStore.datasetName;

  const datasetStore = getDatasetContext();
  const deleteSignal = deleteSignalMutation();

  $: isSignal = isSignalField(field, schema);
  $: isSignalRoot = isSignalRootField(field);
  $: isPreview = isPreviewSignal($datasetStore.selectRowsSchema?.data || null, field.path);
  $: hasMenu =
    (isSortableField(field) || isFilterableField(field) || !isSignal || isSignalRoot) && !isPreview;

  function deleteSignalClicked() {
    $deleteSignal.mutate([namespace, datasetName, {signal_path: field.path}], {
      onSuccess: () => (deleteSignalOpen = false)
    });
  }
</script>

{#if hasMenu}
  <OverflowMenu light flipped>
    {#if isSortableField(field)}
      <OverflowMenuItem text="Sort by" on:click={() => datasetViewStore.addSortBy(field.path)} />
    {/if}
    {#if isFilterableField(field)}
      <OverflowMenuItem
        text="Filter"
        on:click={() =>
          triggerCommand({
            command: Command.EditFilter,
            namespace,
            datasetName,
            path: field.path
          })}
      />
    {/if}
    {#if !isSignal}
      <OverflowMenuItem
        text="Compute embedding"
        on:click={() =>
          triggerCommand({
            command: Command.ComputeEmbedding,
            namespace,
            datasetName,
            path: field?.path
          })}
      />
    {/if}
    {#if !isSignal}
      <OverflowMenuItem
        text="Preview signal"
        on:click={() =>
          triggerCommand({
            command: Command.PreviewConcept,
            namespace,
            datasetName,
            path: field?.path
          })}
      />
    {/if}
    {#if !isSignal}
      <OverflowMenuItem
        text="Compute signal"
        on:click={() =>
          triggerCommand({
            command: Command.ComputeSignal,
            namespace,
            datasetName,
            path: field?.path
          })}
      />
    {/if}
    {#if isSignalRoot}
      <OverflowMenuItem text="Delete signal" on:click={() => (deleteSignalOpen = true)} />
    {/if}
  </OverflowMenu>
{/if}

<Modal
  danger
  bind:open={deleteSignalOpen}
  modalHeading="Delete signal"
  primaryButtonText="Delete"
  primaryButtonIcon={$deleteSignal.isLoading ? InProgress : undefined}
  secondaryButtonText="Cancel"
  on:click:button--secondary={() => (deleteSignalOpen = false)}
  on:open
  on:close
  on:submit={deleteSignalClicked}
>
  <p class="!text-lg">Confirm deleting <code>{serializePath(field.path)}</code> ?</p>
  <p class="mt-2">This is a permanent action and cannot be undone.</p>
</Modal>

<style lang="postcss">
  :global(ul.bx--overflow-menu-options) {
    @apply w-44;
  }
</style>
