<script lang="ts">
  import {
    addLabelsMutation,
    queryDatasetSchema,
    queryRowMetadata,
    querySelectRowsSchema,
    querySettings,
    removeLabelsMutation
  } from '$lib/queries/datasetQueries';
  import {queryAuthInfo} from '$lib/queries/serverQueries';
  import {
    getDatasetViewContext,
    getSelectRowsOptions,
    getSelectRowsSchemaOptions
  } from '$lib/stores/datasetViewStore';
  import {getNotificationsContext} from '$lib/stores/notificationsStore';
  import {SIDEBAR_TRANSITION_TIME_MS} from '$lib/view_utils';
  import {
    formatValue,
    getRowLabels,
    getSchemaLabels,
    serializePath,
    type AddLabelsOptions,
    type LilacField,
    type RemoveLabelsOptions
  } from '$lilac';
  import {SkeletonText} from 'carbon-components-svelte';
  import {ChevronLeft, ChevronRight, Tag} from 'carbon-icons-svelte';
  import {slide} from 'svelte/transition';
  import EditLabel from './EditLabel.svelte';
  import ItemMedia from './ItemMedia.svelte';
  import ItemMetadata from './ItemMetadata.svelte';
  import LabelPill from './LabelPill.svelte';

  export let rowId: string;
  export let mediaFields: LilacField[];
  export let highlightedFields: LilacField[];
  // The counting index of this row item.
  export let index: number | undefined;
  export let totalNumRows: number | undefined;
  export let updateSequentialRowId: ((direction: 'previous' | 'next') => void) | undefined =
    undefined;

  const datasetViewStore = getDatasetViewContext();
  const notificationStore = getNotificationsContext();

  $: namespace = $datasetViewStore.namespace;
  $: datasetName = $datasetViewStore.datasetName;

  const authInfo = queryAuthInfo();
  $: canEditLabels = $authInfo.data?.access.dataset.edit_labels;

  const MIN_METADATA_HEIGHT_PX = 165;
  let labelsInProgress = new Set<string>();
  let mediaHeight = 0;

  $: schema = queryDatasetSchema(namespace, datasetName);
  $: selectRowsSchema = querySelectRowsSchema(
    namespace,
    datasetName,
    getSelectRowsSchemaOptions($datasetViewStore)
  );
  $: removeLabels = $schema.data != null ? removeLabelsMutation($schema.data) : null;

  $: selectOptions = getSelectRowsOptions($datasetViewStore);
  $: rowQuery =
    $selectRowsSchema.data != null && !$selectRowsSchema.isFetching
      ? queryRowMetadata(
          namespace,
          datasetName,
          rowId,
          selectOptions,
          $selectRowsSchema.data.schema
        )
      : null;
  $: row = $rowQuery != null && !$rowQuery.isFetching ? $rowQuery?.data : null;
  $: rowLabels = row != null ? getRowLabels(row) : [];
  $: disableLabels = !canEditLabels;

  $: schemaLabels = $schema.data && getSchemaLabels($schema.data);
  $: addLabels = $schema.data != null ? addLabelsMutation($schema.data) : null;

  $: isStale = $rowQuery?.isStale;
  $: {
    if (!isStale) {
      labelsInProgress = new Set();
    }
  }

  $: settings = querySettings($datasetViewStore.namespace, $datasetViewStore.datasetName);
  $: viewType = $settings.data?.ui?.view_type || 'single_item';

  function addLabel(label: string) {
    const addLabelsOptions: AddLabelsOptions = {
      row_ids: [rowId],
      label_name: label
    };
    labelsInProgress.add(label);
    labelsInProgress = labelsInProgress;
    $addLabels!.mutate([namespace, datasetName, addLabelsOptions], {
      onSuccess: numRows => {
        const message =
          addLabelsOptions.row_ids != null
            ? `Document id: ${addLabelsOptions.row_ids}`
            : `${numRows.toLocaleString()} rows labeled`;

        notificationStore.addNotification({
          kind: 'success',
          title: `Added label "${addLabelsOptions.label_name}"`,
          message
        });
      }
    });
  }

  function removeLabel(label: string) {
    const body: RemoveLabelsOptions = {
      label_name: label,
      row_ids: [rowId]
    };
    labelsInProgress.add(label);
    labelsInProgress = labelsInProgress;

    $removeLabels!.mutate([namespace, datasetName, body], {
      onSuccess: () => {
        notificationStore.addNotification({
          kind: 'success',
          title: `Removed label "${body.label_name}"`,
          message: `Document id: ${rowId}`
        });
      }
    });
  }
</script>

<div class="flex w-full flex-col rounded border border-neutral-300 md:flex-row">
  <div
    class={`flex flex-col  ${!$datasetViewStore.showMetadataPanel ? 'grow ' : 'w-2/3'}`}
    bind:clientHeight={mediaHeight}
  >
    <div
      class="flex flex-row justify-between rounded-t border-b border-neutral-300 bg-violet-100 py-2"
    >
      <!-- Left arrow -->
      <div class="w-1/3">
        <!-- left 1/3 container. -->
        {#if updateSequentialRowId != null}
          <div class="flex-0">
            {#if rowId != null && index != null}
              <button
                class:invisible={index === 0}
                on:click={() =>
                  updateSequentialRowId != null ? updateSequentialRowId('previous') : null}
              >
                <ChevronLeft title="Previous item" size={24} />
              </button>
            {/if}
          </div>
        {/if}
      </div>
      <div class="w-1/3 flex-col items-center justify-items-center self-center justify-self-center">
        <div class="items-center justify-items-center truncate text-center text-lg">
          <span class="inline-flex">
            {#if index != null && index >= 0}
              {index + 1}
            {:else}
              <SkeletonText lines={1} class="!w-10" />
            {/if}
          </span>

          <span class="inline-flex text-gray-500 opacity-90">
            of
            {#if totalNumRows != null}
              {formatValue(totalNumRows)}
            {:else}
              <SkeletonText lines={1} class="!w-20" />
            {/if}
          </span>
        </div>
      </div>
      <div class="flex w-1/3 flex-row">
        <!-- Right 1/3 -->
        <div
          class="flex w-full flex-row items-center justify-end gap-x-2 gap-y-2 pr-2"
          class:opacity-50={disableLabels}
        >
          {#each schemaLabels || [] as label}
            <div class:opacity-50={labelsInProgress.has(label)}>
              <LabelPill
                {label}
                disabled={labelsInProgress.has(label)}
                active={rowLabels.includes(label)}
                on:click={() => {
                  if (rowLabels.includes(label)) {
                    removeLabel(label);
                  } else {
                    addLabel(label);
                  }
                }}
              />
            </div>
          {/each}
          <div class="relative mr-8 h-8">
            <EditLabel icon={Tag} labelsQuery={{row_ids: [rowId]}} hideLabels={rowLabels} />
          </div>
          {#if updateSequentialRowId != null && totalNumRows != null}
            <div class="flex-0">
              {#if index != null && index < totalNumRows - 1}
                <button
                  on:click={() =>
                    updateSequentialRowId != null ? updateSequentialRowId('next') : null}
                >
                  <ChevronRight title="Next item" size={24} />
                </button>
              {/if}
            </div>
          {/if}
        </div>
      </div>
    </div>
    {#if mediaFields.length > 0}
      {#each mediaFields as mediaField, i (serializePath(mediaField.path))}
        <div
          class:border-b={i < mediaFields.length - 1}
          class:pb-2={i < mediaFields.length - 1}
          class="flex h-full w-full flex-col border-neutral-200"
        >
          <ItemMedia mediaPath={mediaField.path} {row} field={mediaField} {highlightedFields} />
        </div>
      {/each}
    {/if}
    <!-- <div class="absolute right-0 top-0">
      <button
        class="mr-1 mt-1 opacity-60 hover:bg-gray-200"
        use:hoverTooltip={{
          text: $datasetViewStore.showMetadataPanel ? 'Close metadata' : 'Open metadata'
        }}
        on:click={() =>
          ($datasetViewStore.showMetadataPanel = !$datasetViewStore.showMetadataPanel)}
      >
        {#if $datasetViewStore.showMetadataPanel}
          <SidePanelOpen />
        {:else}
          <SidePanelClose />
        {/if}</button
      >
    </div> -->
  </div>
  {#if $datasetViewStore.showMetadataPanel}
    <div
      class="flex h-full bg-neutral-100 md:w-1/3"
      transition:slide={{axis: 'x', duration: SIDEBAR_TRANSITION_TIME_MS}}
    >
      <div class="sticky top-0 w-full self-start">
        <div
          style={`max-height: ${Math.max(MIN_METADATA_HEIGHT_PX, mediaHeight)}px`}
          class="overflow-y-auto"
        >
          <ItemMetadata {row} selectRowsSchema={$selectRowsSchema.data} {highlightedFields} />
        </div>
      </div>
    </div>
  {/if}
</div>
