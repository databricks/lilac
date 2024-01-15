<script lang="ts">
  import {ChevronLeft, ChevronRight} from 'carbon-icons-svelte';

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  type T = any;

  export let pageSize: number;
  export let items: T[] = [];

  let currentPage = 0;

  $: prevPageDisabled = currentPage === 0;
  $: nextPageDisabled = (currentPage + 1) * pageSize >= items.length;

  $: itemsVisible = items.slice(currentPage * pageSize, (currentPage + 1) * pageSize);

  function showNextPage() {
    if (nextPageDisabled) return;
    currentPage += 1;
  }
  function showPrevPage() {
    if (prevPageDisabled) return;
    currentPage -= 1;
  }

  $: pages = Array.from({length: Math.ceil(items.length / pageSize)});
</script>

<div class="flex w-full flex-col">
  <div class="flex w-full flex-row">
    <div class="flex flex-shrink items-center">
      <button
        class:invisible={prevPageDisabled}
        class:opacity-50={prevPageDisabled}
        class="mx-1"
        on:click={() => showPrevPage()}><ChevronLeft /></button
      >
    </div>

    <div class="flex h-full grow flex-row gap-x-2">
      {#each itemsVisible as item}
        <div style={`width: ${100 / pageSize}%`} class="h-full">
          <slot name="item" {item} />
        </div>
      {/each}
    </div>

    <div class="flex flex-shrink items-center">
      <button
        class:invisible={nextPageDisabled}
        class:opacity-50={nextPageDisabled}
        class="mx-1"
        on:click={() => showNextPage()}><ChevronRight /></button
      >
    </div>
  </div>
  <div class="mx-auto px-16">
    <div class="mt-4 flex flex-row flex-wrap items-center justify-center gap-x-2 gap-y-1">
      {#if pages.length > 1}
        {#each pages as _, i}
          {@const isCurrentPage = i === currentPage}
          {@const sizePx = isCurrentPage ? 10 : 8}
          <button
            class="mx-0.5 rounded-full p-0"
            style={`width: ${sizePx}px; height: ${sizePx}px;`}
            class:bg-blue-300={isCurrentPage}
            class:outline-blue-400={isCurrentPage}
            class:outline={isCurrentPage}
            class:bg-neutral-300={!isCurrentPage}
            on:click={() => (currentPage = i)}
          />
        {/each}
      {/if}
    </div>
  </div>
</div>
