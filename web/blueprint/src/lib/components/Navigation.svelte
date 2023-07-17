<script lang="ts">
  import {goto} from '$app/navigation';
  import {Button} from 'carbon-components-svelte';
  import {DataBase, Home, Light, Settings} from 'carbon-icons-svelte';
</script>

<div class="flex w-full flex-col items-center pt-2">
  <div class="nav-item-container">
    <Button
      icon={Home}
      kind="ghost"
      expressive
      iconDescription="Home"
      tooltipAlignment={'start'}
      on:click={() => goto('/')}
    />
    <div class="nav-icon-text">Home</div>
  </div>
  <div class="nav-item-container">
    <Button
      icon={Light}
      kind="ghost"
      expressive
      iconDescription="Concepts"
      tooltipAlignment={'start'}
      on:click={() => goto('/concepts')}
    />
    <div class="nav-icon-text">Concepts</div>
  </div>
  <div class="nav-item-container">
    <Button
      icon={DataBase}
      kind="ghost"
      expressive
      iconDescription="Datasets"
      tooltipAlignment={'start'}
      on:click={() => goto('/datasets')}
    />
    <div class="nav-icon-text">Datasets</div>
  </div>
  <div class="nav-item-container">
    <Button
      icon={Settings}
      kind="ghost"
      expressive
      iconDescription="Datasets"
      tooltipAlignment={'start'}
      on:click={() => goto('/settings')}
    />
    <div class="nav-icon-text">Settings</div>
  </div>
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
