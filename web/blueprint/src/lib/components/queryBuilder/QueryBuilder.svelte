<script lang="ts">
  import equal from 'deep-equal';

  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {Button} from 'carbon-components-svelte';

  const datasetViewStore = getDatasetViewContext();
  $: options = $datasetViewStore.query;
  $: formattedOptions = options ? JSON.stringify(options, null, 2) : '';

  $: editedSchema = formattedOptions;

  let isValid = true;
  $: {
    try {
      JSON.parse(editedSchema);
      isValid = true;
    } catch (e) {
      isValid = false;
    }
  }

  $: isChanged = isValid && !equal(JSON.parse(editedSchema), options);

  function apply() {
    $datasetViewStore.query = JSON.parse(editedSchema);
  }
</script>

<pre
  class="whitespace-pre bg-gray-50 p-4 font-mono"
  contenteditable
  bind:innerText={editedSchema}
  class:outline-red-500={!isValid}>
{formattedOptions}
</pre>
{#if !isValid}
  <span class="text-red-500">Invalid query</span>
{:else if isChanged}
  <Button on:click={apply}>Apply</Button>
{/if}
