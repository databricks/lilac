<script lang="ts">
  import {serializePath, type LilacField, type LilacValueNode} from '$lilac';
  import RowItemMedia from './RowItemMedia.svelte';
  import RowItemMetadata from './RowItemMetadata.svelte';

  export let row: LilacValueNode;
  export let mediaFields: LilacField[];

  export let visibleFields: LilacField[];
</script>

<div class="w-full border-b border-gray-300 py-2">
  <div class="flex w-full flex-row">
    {#if mediaFields.length > 0}
      <div class="w-2/3">
        {#each mediaFields as mediaField, i (serializePath(mediaField.path))}
          <div class:border-b={i < mediaFields.length - 1} class="m-4 border-gray-100">
            <RowItemMedia {row} path={mediaField.path} field={mediaField} />
          </div>
        {/each}
      </div>
    {/if}
    <div class="w-1/3">
      <RowItemMetadata {row} {visibleFields} />
    </div>
  </div>
</div>
