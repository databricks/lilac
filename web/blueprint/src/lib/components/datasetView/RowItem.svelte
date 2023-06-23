<script lang="ts">
  import {serializePath, type LilacField, type LilacValueNode} from '$lilac';
  import RowItemMedia from './RowItemMedia.svelte';
  import RowItemMetadata from './RowItemMetadata.svelte';

  export let row: LilacValueNode;
  export let mediaFields: LilacField[];

  export let visibleFields: LilacField[];
</script>

<div class="w-full pb-2">
  <div class="flex w-full flex-row">
    {#if mediaFields.length > 0}
      <div class="w-2/3">
        {#each mediaFields as mediaField, i (serializePath(mediaField.path))}
          <div class:border-b={i < mediaFields.length - 1} class=" border-gray-100">
            <RowItemMedia {row} path={mediaField.path} field={mediaField} />
          </div>
        {/each}
      </div>
    {/if}
    <div class="sticky top-0 w-1/3 self-start">
      <RowItemMetadata {row} {visibleFields} />
    </div>
  </div>
</div>
