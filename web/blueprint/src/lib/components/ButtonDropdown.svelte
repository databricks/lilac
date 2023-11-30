<script lang="ts">
  import {ComboBox, InlineLoading} from 'carbon-components-svelte';
  import type {ComboBoxItem} from 'carbon-components-svelte/types/ComboBox/ComboBox.svelte';
  import type {CarbonIcon} from 'carbon-icons-svelte';
  import {createEventDispatcher} from 'svelte';
  import {hoistElement} from './common/Hoist';
  import {hoverTooltip} from './common/HoverTooltip';
  import {clickOutside} from './common/clickOutside';

  export let items: ComboBoxItem[];
  export let buttonIcon: typeof CarbonIcon;
  export let buttonText = '';
  export let buttonOutline = false;
  export let comboBoxText = '';
  export let comboBoxPlaceholder = '';
  export let shouldFilterItem: ((item: ComboBoxItem, value: string) => boolean) | undefined =
    undefined;
  export let isLoading = false;
  export let helperText = '';
  export let disabled = false;
  export let disabledMessage = '';
  export let redText = false;
  export let hoist = false;

  const dispatch = createEventDispatcher();

  let comboBox: ComboBox;

  let dropdownOpen = false;
  function openDropdown() {
    dropdownOpen = true;
    requestAnimationFrame(() => {
      // comboBox.clear({focus: true}) does not open the combo box automatically, so we
      // programmatically set it.
      comboBox.$set({open: true});
    });
  }

  function selectItem(
    e: CustomEvent<{
      selectedItem: ComboBoxItem;
    }>
  ) {
    dispatch('select', e.detail.selectedItem);
    comboBox.clear();
    dropdownOpen = false;
  }
</script>

<div class="relative z-50 h-8">
  <div
    use:hoverTooltip={{
      text: disabled ? disabledMessage : ''
    }}
  >
    <button
      {disabled}
      class:opacity-30={disabled}
      class:text-red-600={redText}
      on:click={openDropdown}
      use:hoverTooltip={{text: helperText}}
      class:border={buttonOutline}
      class:border-gray-300={buttonOutline}
      class="flex items-center gap-x-2"
      class:hidden={dropdownOpen}
    >
      {#if isLoading}
        <InlineLoading />
      {/if}
      <svelte:component this={buttonIcon} />
      {buttonText}
    </button>
  </div>
  {#if dropdownOpen}
    <div
      class="z-50 w-60"
      class:absolute={hoist}
      class:hidden={!dropdownOpen}
      use:clickOutside={() => {
        comboBox.clear();
        dropdownOpen = false;
      }}
      use:hoistElement={{disable: !hoist}}
    >
      <ComboBox
        size="sm"
        open={dropdownOpen}
        bind:this={comboBox}
        {items}
        bind:value={comboBoxText}
        on:select={selectItem}
        shouldFilterItem={shouldFilterItem ? shouldFilterItem : undefined}
        placeholder={comboBoxPlaceholder}
        let:item={it}
      >
        {@const item = items.find(p => p.id === it.id)}
        {#if $$slots.item}
          <slot name="item" {item} inputText={comboBoxText} />
        {:else if item}
          <div class="flex justify-between gap-x-8">{item.text}</div>
        {/if}
      </ComboBox>
    </div>
  {/if}
</div>
