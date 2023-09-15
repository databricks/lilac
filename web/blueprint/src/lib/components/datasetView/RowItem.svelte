<script lang="ts">
  import {getDatasetContext} from '$lib/stores/datasetStore';
  import {serializePath, type LilacField, type LilacValueNode} from '$lilac';
  import ItemMedia from './ItemMedia.svelte';
  import ItemMetadata from './ItemMetadata.svelte';

  export let row: LilacValueNode;
  export let mediaFields: LilacField[];
  export let highlightedFields: LilacField[];

  const datasetStore = getDatasetContext();

  const MIN_METADATA_HEIGHT_PX = 320;
  let mediaHeight = 0;

  $: selectRowsSchema = $datasetStore.selectRowsSchema?.data;
</script>

<div class="rounded border border-neutral-300">
  <div class="flex h-full w-full flex-col md:flex-row">
    {#if mediaFields.length > 0}
      <div class="md:w-2/3" bind:clientHeight={mediaHeight}>
        {#each mediaFields as mediaField, i (serializePath(mediaField.path))}
          <div class:border-b={i < mediaFields.length - 1} class="border-neutral-200">
            <ItemMedia {row} path={mediaField.path} field={mediaField} {highlightedFields} />
          </div>
        {/each}
      </div>
    {/if}
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
  </div>
</div>
