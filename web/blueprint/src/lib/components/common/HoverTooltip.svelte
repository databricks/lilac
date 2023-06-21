<script lang="ts">
  import {Tooltip} from 'carbon-components-svelte';

  let isHovered = false;
</script>

<div
  on:mouseenter={() => (isHovered = true)}
  on:mouseleave={() => (isHovered = false)}
  class="hover-tooltip"
>
  <Tooltip {...$$restProps} open={isHovered}><slot /></Tooltip>
</div>

<style lang="postcss">
  :global(.hover-tooltip .bx--tooltip) {
    @apply top-4 w-fit bg-slate-50 text-black;
  }
  :global(.hover-tooltip .bx--tooltip__caret) {
    @apply hidden;
  }
  :global(.hover-tooltip div) {
    @apply cursor-auto;
  }
</style>
