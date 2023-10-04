<!-- A combination of a dropdown and filter-like pill -->
<script lang="ts">
  import {Dropdown, DropdownSkeleton} from 'carbon-components-svelte';
  import type {
    DropdownItem,
    DropdownItemId
  } from 'carbon-components-svelte/types/Dropdown/Dropdown.svelte';
  import {createEventDispatcher} from 'svelte';
  import {hoverTooltip} from './HoverTooltip';

  export let title: string;
  export let selectedId: string | null | undefined = null;
  export let items: DropdownItem[] | null | undefined = null;
  export let tooltip: string | null | undefined = undefined;

  const dispatch = createEventDispatcher();
  export let open = false;
  const NONE_ID = '__none__';

  $: dropdownItems = [{id: NONE_ID, text: open ? 'None' : title}, ...(items || [])];

  function selectItem(
    e: CustomEvent<{
      selectedId: DropdownItemId;
      selectedItem: DropdownItem;
    }>
  ) {
    selectedId = e.detail.selectedId == NONE_ID ? null : e.detail.selectedId;
    dispatch('select', {selectedId, selectedItem: e.detail.selectedItem});
  }
</script>

<div
  class="drop-pill flex items-center px-2"
  class:active={selectedId != null}
  use:hoverTooltip={!open && tooltip ? {text: tooltip} : {text: ''}}
>
  <slot name="icon" />
  {#if items}
    <Dropdown
      bind:open
      size="sm"
      type="inline"
      selectedId={selectedId != null ? selectedId : NONE_ID}
      items={dropdownItems}
      let:item
      on:select={selectItem}
    >
      {#if item.id === NONE_ID}
        <div class="flex items-center justify-between gap-x-1">None</div>
      {:else}
        <slot {item} />
      {/if}
    </Dropdown>
  {:else}
    <DropdownSkeleton inline />
  {/if}
</div>

<style lang="postcss">
  .active {
    @apply rounded-lg bg-neutral-100 outline outline-1 outline-neutral-400;
  }
  :global(.drop-pill .bx--list-box__menu) {
    max-height: 26rem !important;
    width: unset;
    right: unset;
  }
  :global(.drop-pill .bx--dropdown) {
    @apply !max-w-xs;
  }
  :global(.drop-pill .bx--dropdown__wrapper--inline) {
    @apply !gap-0;
  }
  :global(.drop-pill .bx--list-box__menu-item__option) {
    @apply pr-0;
  }
  :global(.drop-pill .bx--list-box__menu-icon) {
    position: unset;
  }
  :global(.drop-pill .bx--list-box__field) {
    @apply !pr-0;
  }
</style>
