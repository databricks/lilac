<script lang="ts">
  import {SkeletonText, Tag} from 'carbon-components-svelte';
  import type {TagProps} from 'carbon-components-svelte/types/Tag/Tag.svelte';

  export let skeleton = false;
  export let items: {
    title: string;
    value: unknown;
    tag?: {value: string; type?: TagProps['type']};
  }[] = [];
  export let defaultItem: unknown = undefined;
  export let item: unknown = undefined;

  $: {
    if (!item && defaultItem) {
      item = defaultItem;
    }
  }
</script>

{#if skeleton}
  <SkeletonText lines={3} />
{:else}
  <div class="flex flex-col" role="list">
    {#each items as _item}
      <button
        data-active={item === _item.value}
        on:click={() => (item = _item.value)}
        class="flex items-center justify-between"
      >
        {_item.title}
        {#if _item.tag} <Tag size="sm" type={_item.tag.type}>{_item.tag.value}</Tag> {/if}
      </button>
    {/each}
  </div>
{/if}

<style lang="postcss">
  button {
    @apply w-full px-4 py-2 text-left text-gray-800;
  }

  button:hover {
    @apply bg-gray-200 text-black;
  }

  button[data-active='true'] {
    @apply bg-gray-300 text-black;
  }

  :global(.bx--tag) {
    margin: 0;
  }
</style>
