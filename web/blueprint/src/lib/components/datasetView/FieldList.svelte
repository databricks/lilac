<script lang="ts">
  import {DTYPE_TO_ICON} from '$lib/view_utils';
  import {
    PATH_WILDCARD,
    isLabelField,
    isSignalField,
    pathIsEqual,
    serializePath,
    type LilacField
  } from '$lilac';
  import {Checkbox} from 'carbon-components-svelte';

  export let fields: LilacField[];
  export let checkedFields: LilacField[];

  function checkboxClicked(field: LilacField, event: Event) {
    const checked = (event.target as HTMLInputElement).checked;
    if (checked) {
      checkedFields.push(field);
      checkedFields = checkedFields;
    } else {
      checkedFields = checkedFields.filter(f => !pathIsEqual(f.path, field.path));
    }
  }
</script>

{#each fields as field}
  {@const isSignal = isSignalField(field)}
  {@const isLabel = isLabelField(field)}
  <div class="flex items-center">
    <div class="mr-2">
      <Checkbox
        hideLabel
        checked={checkedFields.find(f => pathIsEqual(f.path, field.path)) != null}
        on:change={e => checkboxClicked(field, e)}
      />
    </div>
    <div class="flex w-10">
      <div
        class="inline-flex items-center rounded-md p-0.5"
        class:bg-blue-200={isSignal}
        class:bg-teal-100={isLabel}
      >
        {#if field.dtype}
          <svelte:component this={DTYPE_TO_ICON[field.dtype]} title={field.dtype} />
        {:else}
          <span class="font-mono">{'{}'}</span>
        {/if}
        {#if field.path.indexOf(PATH_WILDCARD) >= 0}[]{/if}
      </div>
    </div>
    <div class="flex-grow">{serializePath(field.path)}</div>
  </div>
{/each}
