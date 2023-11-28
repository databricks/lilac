<script context="module" lang="ts">
  export interface NavigationLinkItem {
    name: string;
    link: string;
    isSelected: boolean;
  }
</script>

<script lang="ts">
  import {goto} from '$app/navigation';

  import {ChevronDown, ChevronUp} from 'carbon-icons-svelte';

  export let expanded = false;
  export let indentLevel = 0;
  export let linkItems: NavigationLinkItem[] = [];
  // When true, renders the content of below without an expandable. We use this when there are no
  // tags, to avoid branching logic upstream.
  export let renderBelowOnly = false;

  // Padding multiplier for indent level, in rem.
  const INDENT_LEVEL_PADDING_REM = 0.4;
  // Adds a little extra padding to the left.
  const INDENT_LEVEL_PADDING_OFFSET_REM = 1;

  function indentLevelToPadding(indentLevel: number): number {
    return indentLevel * INDENT_LEVEL_PADDING_REM + INDENT_LEVEL_PADDING_OFFSET_REM;
  }

  $: indentPadding = indentLevelToPadding(indentLevel);
  $: linkPadding = indentLevelToPadding(indentLevel + 1);
</script>

{#if !renderBelowOnly}
  <div class="relative flex w-full flex-col rounded-xl">
    <button
      class="w-full flex-grow py-1 text-left hover:bg-gray-200"
      style={`padding-left: ${indentPadding}rem;`}
      on:click={() => (expanded = !expanded)}
    >
      <div class="flex w-full items-center justify-between gap-x-3">
        <slot name="above" />
        {#if expanded}
          <ChevronUp />
        {:else}
          <ChevronDown />
        {/if}
      </div>
    </button>
    {#if expanded}
      <div class="mt-1">
        <slot name="below" />
        {#if linkItems.length > 0}
          {#each linkItems as linkItem}
            <div
              class={`flex w-full rounded ${!linkItem.isSelected ? 'hover:bg-gray-100' : ''}
          `}
              style={`padding-left: ${linkPadding}rem;`}
              class:bg-neutral-100={linkItem.isSelected}
            >
              <a
                href={linkItem.link}
                on:click={() => goto(linkItem.link)}
                class:text-black={linkItem.isSelected}
                class:font-semibold={linkItem.isSelected}
                class="w-full truncate px-1 py-1 text-xs text-black"
              >
                {linkItem.name}
              </a>
            </div>
          {/each}
        {/if}
      </div>
    {/if}
  </div>
{:else}
  <div class="mt-1"><slot name="below" /></div>
{/if}
