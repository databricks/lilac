<script context="module" lang="ts">
  export interface NavigationGroupItem {
    group: string;
    items: NavigationItem[];
  }
  export interface NavigationItem {
    name: string;
    link: string;
    isSelected: boolean;
  }
</script>

<script lang="ts">
  import {SkeletonText} from 'carbon-components-svelte';

  import {ChevronDown, ChevronUp} from 'carbon-icons-svelte';

  export let title: string;
  export let isLoading: boolean;
  export let groups: NavigationGroupItem[];
  export let expanded = true;
</script>

<div class="my-1 w-full">
  <button
    class="w-full px-4 py-2 text-left hover:bg-gray-200"
    on:click={() => (expanded = !expanded)}
  >
    <div class="flex items-center justify-between">
      <div class="text-sm font-medium">{title}</div>
      {#if expanded}
        <ChevronUp />
      {:else}
        <ChevronDown />
      {/if}
    </div>
  </button>

  <div class={!expanded ? `invisible h-0` : ''}>
    {#if isLoading}
      <SkeletonText />
    {:else}
      {#each groups as { group, items }}
        <div
          class="flex flex-row justify-between border-b border-gray-200 pl-6
                  text-sm opacity-80"
        >
          <div class="py-1 text-xs">
            {group}
          </div>
        </div>
        {#each items as item}
          <div
            class={`flex w-full flex-row justify-between border-b border-gray-200 ${
              !item.isSelected ? 'hover:bg-gray-100' : ''
            }`}
            class:bg-neutral-100={item.isSelected}
          >
            <a
              href={item.link}
              class:text-black={item.isSelected}
              class:font-semibold={item.isSelected}
              class="flex w-full flex-row items-center whitespace-pre py-1 pl-8 pr-4 text-xs text-black"
            >
              <span>{item.name}</span>
            </a>
          </div>
        {/each}
      {/each}
    {/if}
  </div>
  <div class="flex w-full flex-row items-center whitespace-pre py-1 pl-2 text-xs text-black">
    <slot name="add" />
  </div>
</div>
