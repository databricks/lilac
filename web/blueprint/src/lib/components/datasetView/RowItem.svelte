<script lang="ts">
  import {serializePath, type LilacField, type LilacValueNode} from '$lilac';
  import RowItemMedia from './RowItemMedia.svelte';
  import RowItemMetadata from './RowItemMetadata.svelte';

  export let row: LilacValueNode;
  export let mediaFields: LilacField[];

  export let visibleFields: LilacField[];
</script>

<div class="border-b border-gray-300 py-2">
  <div class="flex flex-row justify-between">
    {#if mediaFields.length > 0}
      <div>
        {#each mediaFields as mediaField, i (serializePath(mediaField.path))}
          <div class:border-b={i < mediaFields.length - 1} class="m-4 border-gray-100">
            <RowItemMedia {row} path={mediaField.path} field={mediaField} />
          </div>
        {/each}
      </div>
    {/if}
    <div>
      <RowItemMetadata {row} {mediaFields} {visibleFields} />
    </div>
  </div>
</div>
