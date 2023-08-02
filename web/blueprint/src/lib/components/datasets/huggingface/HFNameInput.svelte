<script lang="ts">
  import {queryHFDatasetExists} from '$lib/queries/huggingfaceQueries';
  import {TextInput} from 'carbon-components-svelte';

  export let value: string;
  export let invalid: boolean;
  export let invalidText: string;

  $: datasetExistsQuery = queryHFDatasetExists(value);
  $: datasetExists = $datasetExistsQuery.data === true;
</script>

<TextInput
  bind:value
  {invalid}
  {invalidText}
  warn={!datasetExists}
  warnText={"Dataset doesn't exist"}
/>
