<script lang="ts">
  import { LILAC_COLUMN, type Path } from '$lilac/schema';
  import ContextMenuItem from './ContextMenuItem.svelte';

  // export let field: Field;
  export let path: Path;

  let isAnnotation = path[0] === LILAC_COLUMN;
</script>

{#if isAnnotation}
  <ContextMenuItem title="Add Signal" />
  <ContextMenuItem title="Delete" />
{:else}
  <ContextMenuItem title="Add Signal" />
{/if}
