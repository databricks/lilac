<script lang="ts">
  import {Tag} from 'carbon-components-svelte';
  import CloseOutline from 'carbon-icons-svelte/lib/CloseOutline.svelte';
  import {createEventDispatcher} from 'svelte';

  const dispatch = createEventDispatcher();
</script>

<Tag {...$$restProps} on:click>
  <span class="flex gap-x-1">
    <button
      class="opacity-50 hover:opacity-100"
      on:click|stopPropagation={() => dispatch('remove')}
    >
      <CloseOutline />
    </button>
    <slot />
  </span>
</Tag>
