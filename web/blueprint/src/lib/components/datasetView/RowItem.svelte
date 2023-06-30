<script lang="ts">
  import {serializePath, type LilacField, type LilacValueNode} from '$lilac';
  import RowItemMedia from './RowItemMedia.svelte';
  import RowItemMetadata from './RowItemMetadata.svelte';

  export let row: LilacValueNode;
  export let mediaFields: LilacField[];

  export let visibleFields: LilacField[];
</script>

<div class="mx-4 mb-10 rounded border-x border-b border-neutral-200 shadow-md">
  <div class="flex h-full w-full flex-row">
    {#if mediaFields.length > 0}
      <div class="w-2/3">
        {#each mediaFields as mediaField, i (serializePath(mediaField.path))}
          <div class:border-b={i < mediaFields.length - 1} class="border-gray-100">
            <RowItemMedia {row} path={mediaField.path} field={mediaField} />
          </div>
        {/each}
      </div>
    {/if}
    <div class="h-full w-1/3 bg-neutral-100">
      <RowItemMetadata {row} {visibleFields} />
    </div>
  </div>
</div>
