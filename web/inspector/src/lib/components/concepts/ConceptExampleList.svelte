<script lang="ts">
  import type {Example} from '$lilac';

  export let data: Example[];
</script>

<div class="flex h-full w-full flex-col overflow-y-auto overflow-x-clip border border-gray-200">
  {#each data as row}
    <span class="break-all border-b border-gray-200 p-2">
      {row.text}
    </span>
  {/each}
</div>
