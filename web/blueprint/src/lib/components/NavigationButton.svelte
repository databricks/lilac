<script lang="ts">
  import {Button} from 'carbon-components-svelte';
  import type {CarbonIcon} from 'carbon-icons-svelte';

  export let href: string;
  export let title: string;
  export let icon: typeof CarbonIcon;
</script>

<div class="nav-item-container">
  <Button kind="ghost" {href}>
    <div class="flex w-12 flex-col items-center">
      <div class="p-2"><svelte:component this={icon} /></div>
      <div class="nav-icon-text">{title}</div>
    </div>
  </Button>
</div>

<style lang="postcss">
  .nav-item-container {
    @apply mb-2 flex flex-col items-center;
  }
  :global(.nav-item-container .bx--btn) {
    @apply w-full;
  }
  :global(.nav-item-container svg) {
    margin: auto !important;
  }
  .nav-icon-text {
    @apply text-xs font-light;
  }
</style>
