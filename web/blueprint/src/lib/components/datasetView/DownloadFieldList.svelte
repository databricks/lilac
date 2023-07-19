<script lang="ts">
  import {DTYPE_TO_ICON} from '$lib/view_utils';
  import {PATH_WILDCARD, serializePath, type LilacField} from '$lilac';
  import {Checkbox} from 'carbon-components-svelte';

  export let fields: LilacField[];
  export let checkedFields: LilacField[] = [];

  function checkboxClicked(field: LilacField, event: Event) {
    const checked = (event.target as HTMLInputElement).checked;
    if (checked) {
      checkedFields.push(field);
      checkedFields = checkedFields;
    } else {
      checkedFields = checkedFields.filter(f => f !== field);
    }
  }
</script>

{#each fields as field}
  <div class="flex items-center">
    <div class="mr-2">
      <Checkbox
        labelText="Download"
        hideLabel
        checked={checkedFields.indexOf(field) >= 0}
        on:change={e => checkboxClicked(field, e)}
      />
    </div>
    <div class="flex w-10">
      <div class="inline-flex items-center rounded-md bg-blue-200 p-0.5">
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
