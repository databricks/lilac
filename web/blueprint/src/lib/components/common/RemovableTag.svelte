<script lang="ts">
  import {Tag} from 'carbon-components-svelte';
  import type {TagProps} from 'carbon-components-svelte/types/Tag/Tag.svelte';
  import CloseOutline from 'carbon-icons-svelte/lib/CloseOutline.svelte';
  import {createEventDispatcher} from 'svelte';

  const dispatch = createEventDispatcher();
  export let type: TagProps['type'];
</script>

<Tag {type} {...$$restProps} on:click>
  <div class="removable-tag flex items-center gap-x-1">
    <button
      class="opacity-50 hover:opacity-100"
      on:click|stopPropagation={() => dispatch('remove')}
    >
      <CloseOutline />
    </button>
    <span class="truncate"><slot /></span>
  </div>
</Tag>

<style lang="postcss">
  :global(.removable-tag) {
    max-width: 8rem;
  }
</style>
