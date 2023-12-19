<script lang="ts">
  import {
    deleteSignalMutation,
    queryDatasetSchema,
    querySelectRowsSchema
  } from '$lib/queries/datasetQueries';
  import {queryAuthInfo} from '$lib/queries/serverQueries';
  import {getDatasetViewContext, getSelectRowsSchemaOptions} from '$lib/stores/datasetViewStore';
  import {getComputedEmbeddings, isPreviewSignal} from '$lib/view_utils';
  import {
    isFilterableField,
    isSignalField,
    isSignalRootField,
    isSortableField,
    serializePath,
    type LilacField
  } from '$lilac';
  import {Modal, OverflowMenu, OverflowMenuItem} from 'carbon-components-svelte';
  import {InProgress} from 'carbon-icons-svelte';
  import {Command, triggerCommand} from '../commands/Commands.svelte';
  import {hoverTooltip} from '../common/HoverTooltip';

  export let field: LilacField;

  let deleteSignalOpen = false;

  const datasetViewStore = getDatasetViewContext();

  $: namespace = $datasetViewStore.namespace;
  $: datasetName = $datasetViewStore.datasetName;

  $: schema = queryDatasetSchema(namespace, datasetName);
  $: selectRowsSchema = querySelectRowsSchema(
    namespace,
    datasetName,
    getSelectRowsSchemaOptions($datasetViewStore)
  );

  const deleteSignal = deleteSignalMutation();

  $: isSignal = isSignalField(field);
  $: isDeletable = isSignalRootField(field);

  $: computedEmbeddings = getComputedEmbeddings($schema.data, field.path);

  $: isPreview = isPreviewSignal($selectRowsSchema?.data || null, field.path);
  $: canComputeSignal = !isSignal && isSortableField(field) && !isPreview;
  $: hasMenu =
    !isPreview &&
    (isSortableField(field) || isFilterableField(field) || canComputeSignal || isDeletable);

  const authInfo = queryAuthInfo();
  $: canComputeSignals = $authInfo.data?.access.dataset.compute_signals;
  $: canDeleteSignals = $authInfo.data?.access.dataset.delete_signals;

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
    {#if canComputeSignal}
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
    {#if canComputeSignal}
      <div
        class="w-full"
        use:hoverTooltip={{
          text: !canComputeSignals
            ? 'User does not have access to compute concepts over this dataset.'
            : computedEmbeddings.length === 0
            ? 'No embeddings are computed for this field. Compute embeddings before using concepts.'
            : ''
        }}
      >
        <OverflowMenuItem
          text="Compute concept"
          disabled={!canComputeSignals || computedEmbeddings.length === 0}
          on:click={() =>
            triggerCommand({
              command: Command.ComputeConcept,
              namespace,
              datasetName,
              path: field?.path
            })}
        />
      </div>
    {/if}
    {#if canComputeSignal}
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
    {#if canComputeSignal}
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
    {#if isDeletable}
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
