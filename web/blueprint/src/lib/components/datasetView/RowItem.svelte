<script lang="ts">
  import {getDatasetContext} from '$lib/stores/datasetStore';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {getVisibleFields} from '$lib/view_utils';
  import {serializePath, type LilacField, type LilacValueNode} from '$lilac';
  import ItemMedia from './ItemMedia.svelte';
  import ItemMetadata from './ItemMetadata.svelte';

  export let row: LilacValueNode;
  export let mediaFields: LilacField[];

  const datasetStore = getDatasetContext();
  const datasetViewStore = getDatasetViewContext();

  const MIN_METADATA_HEIGHT_PX = 320;
  let mediaHeight = 0;

  $: selectRowsSchema = $datasetStore.selectRowsSchema?.data;

  $: highlightedFields = getVisibleFields(
    $datasetViewStore.query,
    $datasetStore.selectRowsSchema?.data
  );
</script>

<div class="rounded border-x border-b border-neutral-200 shadow-md">
  <div class="flex h-full w-full flex-row">
    {#if mediaFields.length > 0}
      <div class="w-2/3 overflow-hidden" bind:clientHeight={mediaHeight}>
        {#each mediaFields as mediaField, i (serializePath(mediaField.path))}
          <div class:border-b={i < mediaFields.length - 1} class="border-gray-100">
            <ItemMedia {row} path={mediaField.path} field={mediaField} {highlightedFields} />
          </div>
        {/each}
      </div>
    {/if}
    <div class="flex h-full w-1/3 bg-neutral-100">
      <div class="sticky top-0 w-full self-start">
        <div
          style={`max-height: ${Math.max(MIN_METADATA_HEIGHT_PX, mediaHeight)}px`}
          class="overflow-y-auto py-2"
        >
          <ItemMetadata {row} {selectRowsSchema} />
        </div>
      </div>
    </div>
  </div>
</div>
