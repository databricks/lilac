<script lang="ts">
  import type {LilacSchema, LilacValueNode, Path} from '$lilac';
  import RowItemValue from './RowItemValue.svelte';

  export let row: LilacValueNode;
  export let schema: LilacSchema;

  export let visiblePaths: Path[];
</script>

<div class="mb-4 flex flex-col gap-y-4 border-b border-gray-300 p-4">
  {#each visiblePaths as path (path.join('.'))}
    <RowItemValue {row} {path} {schema} />
  {/each}
</div>
