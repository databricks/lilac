<script lang="ts">
  import {serializePath, type LilacField} from '$lilac';
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
    <div class="mr-4">
      <Checkbox
        labelText="Download"
        hideLabel
        checked={checkedFields.indexOf(field) >= 0}
        on:change={e => checkboxClicked(field, e)}
      />
    </div>
    <div class="flex-grow">{serializePath(field.path)}</div>
  </div>
{/each}
