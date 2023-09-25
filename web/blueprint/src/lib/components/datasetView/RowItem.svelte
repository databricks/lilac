<script lang="ts">
  import {queryRowMetadata as queryRow, removeLabelsMutation} from '$lib/queries/datasetQueries';
  import {queryAuthInfo} from '$lib/queries/serverQueries';
  import {getDatasetContext} from '$lib/stores/datasetStore';
  import {getDatasetViewContext, getSelectRowsOptions} from '$lib/stores/datasetViewStore';
  import {getNotificationsContext} from '$lib/stores/notificationsStore';
  import {getRowLabels, serializePath, type LilacField, type RemoveLabelsOptions} from '$lilac';
  import {SkeletonText} from 'carbon-components-svelte';
  import RemovableTag from '../common/RemovableTag.svelte';
  import AddLabel from './AddLabel.svelte';
  import ItemMedia from './ItemMedia.svelte';
  import ItemMetadata from './ItemMetadata.svelte';

  export let rowId: string;
  export let mediaFields: LilacField[];
  export let highlightedFields: LilacField[];

  const datasetStore = getDatasetContext();
  const datasetViewStore = getDatasetViewContext();
  const notificationStore = getNotificationsContext();

  $: namespace = $datasetViewStore.namespace;
  $: datasetName = $datasetViewStore.datasetName;

  const authInfo = queryAuthInfo();
  $: canEditLabels = $authInfo.data?.access.dataset.edit_labels;

  const MIN_METADATA_HEIGHT_PX = 320;
  let mediaHeight = 0;

  const removeLabels =
    $datasetStore.schema != null ? removeLabelsMutation($datasetStore.schema) : null;

  $: selectRowsSchema = $datasetStore.selectRowsSchema?.data;

  $: selectOptions = getSelectRowsOptions($datasetViewStore);
  $: rowQuery =
    selectRowsSchema != null
      ? queryRow(namespace, datasetName, rowId, selectOptions, selectRowsSchema.schema)
      : null;
  $: row = $rowQuery?.data != null ? $rowQuery.data : null;
  $: rowLabels = row != null ? getRowLabels(row) : [];

  const removeLabel = (label: string) => {
    const body: RemoveLabelsOptions = {
      label_name: label,
      row_ids: [rowId]
    };
    $removeLabels!.mutate([namespace, datasetName, body], {
      onSuccess: () => {
        notificationStore.addNotification({
          kind: 'success',
          title: `Removed label "${body.label_name}"`,
          message: `Document id: ${rowId}`
        });
      }
    });
  };
</script>

<div class="flex flex-col rounded border border-neutral-300 md:flex-row">
  {#if row == null || $rowQuery?.isFetching}
    <SkeletonText lines={4} paragraph class="w-full" />
  {:else}
    <div class="flex flex-col gap-y-1 p-4 md:w-2/3" bind:clientHeight={mediaHeight}>
      <div class="flex flex-wrap gap-x-2 gap-y-2">
        {#each rowLabels as label}
          <RemovableTag
            type="cool-gray"
            class="hover:cursor-pointer"
            removeDisabled={!canEditLabels}
            removeDisabledHelperText="You do not have access to remove labels."
            closeHelperText={`Remove label "${label}"`}
            clickHelperText={`View documents with label "${label}"`}
            on:click={() =>
              datasetViewStore.addFilter({
                path: [label, 'label'],
                op: 'equals',
                value: 'true'
              })}
            on:remove={() => removeLabel(label)}
          >
            {label}
          </RemovableTag>
        {/each}
        <div class="relative h-8">
          <AddLabel addLabelsQuery={{row_ids: [rowId]}} hideLabels={rowLabels} />
        </div>
      </div>
      {#if mediaFields.length > 0}
        {#each mediaFields as mediaField, i (serializePath(mediaField.path))}
          <div
            class:border-b={i < mediaFields.length - 1}
            class:pb-2={i < mediaFields.length - 1}
            class="flex h-full w-full flex-col border-neutral-200"
          >
            <ItemMedia {row} path={mediaField.path} field={mediaField} {highlightedFields} />
          </div>
        {/each}
      {/if}
    </div>
    <div class="flex h-full bg-neutral-100 md:w-1/3">
      <div class="sticky top-0 w-full self-start">
        <div
          style={`max-height: ${Math.max(MIN_METADATA_HEIGHT_PX, mediaHeight)}px`}
          class="overflow-y-auto py-2"
        >
          <ItemMetadata {row} {selectRowsSchema} {highlightedFields} />
        </div>
      </div>
    </div>
  {/if}
</div>
