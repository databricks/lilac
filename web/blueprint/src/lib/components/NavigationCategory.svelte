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
    page: AppPage;
    identifier: string;
    isSelected: boolean;
    item: T;
  }
</script>

<script lang="ts">
  import {SkeletonText} from 'carbon-components-svelte';

  import {getNavigationContext} from '$lib/stores/navigationStore';
  import type {AppPage} from '$lib/stores/urlHashStore';
  import {ChevronDown, ChevronUp} from 'carbon-icons-svelte';
  import {slide} from 'svelte/transition';
  import NavigationExpandable from './NavigationExpandable.svelte';

  export let title: string;
  export let key: string;
  export let isFetching: boolean;
  export let tagGroups: NavigationTagGroup[];
  const navigationStore = getNavigationContext();

  $: expanded = $navigationStore.expanded[key] != null ? $navigationStore.expanded[key] : true;

  function toggleCategoryExpanded() {
    navigationStore.toggleExpanded(key);
  }

  $: hasTags = tagGroups.some(({tag}) => tag != '');
</script>

<div class="my-1 w-full px-1">
  <button
    class="w-full py-2 pl-4 pr-2 text-left hover:bg-gray-200"
    on:click={toggleCategoryExpanded}
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
            <div class="my-1">
              <NavigationExpandable
                key={`${key}.${tag}`}
                indentLevel={1}
                renderBelowOnly={!hasTags}
              >
                <div slot="above">
                  {#if hasTags}
                    <div class="flex flex-row justify-between text-sm opacity-80">
                      <div class="text-xs">
                        <span
                          class="-ml-2 rounded-lg px-2 py-0.5 text-xs"
                          class:bg-purple-200={tag != ''}
                          class:bg-gray-100={tag == ''}
                        >
                          {tag || 'No tag'}
                        </span>
                      </div>
                    </div>
                  {/if}
                </div>
                <div slot="below">
                  {#each groups as { group, items }}
                    <div class="mt-1">
                      <NavigationExpandable
                        key={`${key}.${tag}.${group}`}
                        indentLevel={hasTags ? 2 : 1}
                        linkItems={items}
                      >
                        <div slot="above" class="text-xs">{group}</div>
                      </NavigationExpandable>
                    </div>
                  {/each}
                </div>
              </NavigationExpandable>
            </div>
          {/each}
        </div>
      {/if}
    </div>
  {/if}
  <div class="flex w-full flex-row items-center whitespace-pre py-1 pl-2 text-xs text-black">
    <slot name="add" />
  </div>
</div>
