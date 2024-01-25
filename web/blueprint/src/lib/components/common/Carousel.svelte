<script lang="ts">
  import {SkeletonText} from 'carbon-components-svelte';
  import {ChevronLeft, ChevronRight} from 'carbon-icons-svelte';
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  type T = any;

  export let pageSize: number;
  export let items: T[] | undefined = undefined;

  let currentPage = 0;

  $: prevPageDisabled = currentPage === 0;
  $: nextPageDisabled = items != null ? (currentPage + 1) * pageSize >= items.length : true;

  $: itemsVisible = items?.slice(currentPage * pageSize, (currentPage + 1) * pageSize);

  function showNextPage() {
    if (nextPageDisabled) return;
    currentPage += 1;
  }
  function showPrevPage() {
    if (prevPageDisabled) return;
    currentPage -= 1;
  }

  $: pages = items != null ? Array.from({length: Math.ceil(items.length / pageSize)}) : [];
</script>

<div class="flex w-full flex-col">
  <div class="flex w-full flex-row">
    <div class="flex h-full grow flex-row gap-x-2">
      {#if itemsVisible != null}
        {#each itemsVisible as item}
          <div style={`width: ${100 / pageSize}%`} class="h-full">
            <slot name="item" {item} />
          </div>
        {/each}
      {:else}
        {#each Array(pageSize) as _, index (index)}
          <div style={`width: ${100 / pageSize}%`} class="h-full">
            <SkeletonText class="w-full" paragraph />
          </div>
        {/each}
      {/if}
    </div>
  </div>
  <div class="mx-auto mt-2 flex flex-row items-center gap-x-4 px-16 font-light">
    <div>
      <button
        disabled={prevPageDisabled}
        class:opacity-20={prevPageDisabled}
        class="mx-1"
        on:click={() => showPrevPage()}
        ><ChevronLeft />
      </button>
    </div>
    <div class="w-16 text-center">
      {currentPage + 1} of {pages.length}
    </div>
    <div>
      <button
        disabled={nextPageDisabled}
        class:opacity-20={nextPageDisabled}
        class="mx-1"
        on:click={() => showNextPage()}
        ><ChevronRight />
      </button>
    </div>
  </div>
</div>
