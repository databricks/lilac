<script context="module" lang="ts">
  export interface NavigationTagGroup<T = unknown> {
    tag: string;
    groups: NavigationGroupItem<T>[];
  }
  export interface NavigationGroupItem<T = unknown> {
    group: string;
    items: NavigationItem<T>[];
  }
  export interface NavigationItem<T = unknown> {
    name: string;
    link: string;
    isSelected: boolean;
    item: T;
  }
</script>

<script lang="ts">
  import {goto} from '$app/navigation';

  import {SkeletonText, Tag} from 'carbon-components-svelte';

  import {ChevronDown, ChevronUp} from 'carbon-icons-svelte';
  import {slide} from 'svelte/transition';

  export let title: string;
  export let isFetching: boolean;
  export let tagGroups: NavigationTagGroup[];
  export let expanded = true;
</script>

<div class="my-1 w-full px-1">
  <button
    class="w-full py-2 pl-4 pr-2 text-left hover:bg-gray-200"
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

  {#if expanded}
    <div transition:slide>
      {#if isFetching}
        <SkeletonText />
      {:else}
        <div class="mt-1">
          {#each tagGroups as { tag, groups }}
            {#if tag != ''}
              <div
                class="flex flex-row justify-between pl-3
            text-sm opacity-80"
              >
                <div class="py-1 text-xs">
                  <Tag type="purple" size="sm">{tag}</Tag>
                </div>
              </div>
            {/if}
            {#each groups as { group, items }}
              <div
                class="flex flex-row justify-between pl-7
                  text-sm opacity-80"
              >
                <div class="py-1 text-xs">
                  {group}
                </div>
              </div>
              {#each items as item}
                <div
                  class={`flex w-full ${!item.isSelected ? 'hover:bg-gray-100' : ''}`}
                  class:bg-neutral-100={item.isSelected}
                >
                  <a
                    href={item.link}
                    on:click={() => goto(item.link)}
                    class:text-black={item.isSelected}
                    class:font-semibold={item.isSelected}
                    class="w-full truncate py-1 pl-9 text-xs text-black"
                  >
                    {item.name}
                  </a>
                </div>
              {/each}
            {/each}
          {/each}
        </div>
      {/if}
    </div>
  {/if}
  <div class="flex w-full flex-row items-center whitespace-pre py-1 pl-2 text-xs text-black">
    <slot name="add" />
  </div>
</div>
