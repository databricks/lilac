<script lang="ts">
  import {deleteSignalMutation} from '$lib/queries/datasetQueries';
  import {queryUserAcls} from '$lib/queries/serverQueries';
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
  import {hoverTooltip} from '../common/HoverTooltip';

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

  const userAcls = queryUserAcls();
  $: canComputeSignals = $userAcls.data?.dataset.compute_signals;
  $: canDeleteSignals = $userAcls.data?.dataset.delete_signals;

  function deleteSignalClicked() {
    $deleteSignal.mutate([namespace, datasetName, {signal_path: field.path}], {
      onSuccess: () => {
        deleteSignalOpen = false;
        // Clear any state that referred to the signal.
        datasetViewStore.deleteSignal(field.path);
      }
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
      <div
        class="w-full"
        use:hoverTooltip={{
          text: !canComputeSignals
            ? 'User does not have access to compute embeddings over this dataset.'
            : ''
        }}
      >
        <OverflowMenuItem
          disabled={!canComputeSignals}
          text="Compute embedding"
          on:click={() =>
            triggerCommand({
              command: Command.ComputeEmbedding,
              namespace,
              datasetName,
              path: field?.path
            })}
        />
      </div>
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
      <div
        class="w-full"
        use:hoverTooltip={{
          text: !canComputeSignals
            ? 'User does not have access to compute signals over this dataset.'
            : ''
        }}
      >
        <OverflowMenuItem
          text="Compute signal"
          disabled={!canComputeSignals}
          on:click={() =>
            triggerCommand({
              command: Command.ComputeSignal,
              namespace,
              datasetName,
              path: field?.path
            })}
        />
      </div>
    {/if}
    {#if isSignalRoot}
      <div
        class="w-full"
        use:hoverTooltip={{
          text: !canDeleteSignals
            ? 'User does not have access to delete signals for this dataset.'
            : ''
        }}
      >
        <OverflowMenuItem
          disabled={!canDeleteSignals}
          text="Delete signal"
          on:click={() => (deleteSignalOpen = true)}
        />
      </div>
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
