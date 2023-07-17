<script lang="ts">
  /**
   * The component for a page, including a header with slots for subtext, center, and right.
   */
  import TaskStatus from './TaskStatus.svelte';

  export let title: string;
</script>

<div class="flex h-full w-full flex-col">
  <!-- Header -->
  <div
    class="flex flex-row items-center justify-between justify-items-center gap-x-12 border-b border-gray-200 px-4 py-2"
  >
    <div class="mr-4 flex flex-row items-center">
      <a class="text-xl normal-case" href="/"
        >Lilac
        <span>{title}</span></a
      >
      <div class="mt-1 pl-4">
        <slot name="header-subtext" />
      </div>
    </div>
    <div class="flex-grow flex-row items-center justify-center">
      <slot name="header-center" />
    </div>
    <div class="flex flex-row items-center gap-x-2">
      <slot name="header-right" />
      <TaskStatus />
    </div>
  </div>

  <!-- Body -->
  <div class="flex h-full w-full overflow-hidden">
    <slot />
  </div>
</div>
