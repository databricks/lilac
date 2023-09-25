<script lang="ts">
  import {Tag} from 'carbon-components-svelte';
  import type {TagProps} from 'carbon-components-svelte/types/Tag/Tag.svelte';
  import CloseOutline from 'carbon-icons-svelte/lib/CloseOutline.svelte';
  import {createEventDispatcher} from 'svelte';
  import {hoverTooltip} from './HoverTooltip';

  const dispatch = createEventDispatcher();
  export let type: TagProps['type'];
  export let removeDisabled = false;
  export let removeDisabledHelperText: string | undefined = undefined;
  export let closeHelperText: string | undefined = undefined;
  export let clickHelperText: string | undefined = undefined;
</script>

<Tag {type} {...$$restProps} on:click>
  <div class="removable-tag flex items-center gap-x-1">
    <button
      disabled={removeDisabled}
      use:hoverTooltip={{text: removeDisabled ? removeDisabledHelperText : closeHelperText}}
      class="p-0 opacity-50 hover:opacity-100"
      on:click|stopPropagation={() => dispatch('remove')}
    >
      <CloseOutline />
    </button>
    <span use:hoverTooltip={{text: clickHelperText}} class="truncate"><slot /></span>
  </div>
</Tag>

<style lang="postcss">
  :global(.removable-tag) {
    max-width: 12rem;
  }
</style>
