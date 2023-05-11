<script lang="ts">
  import {queryHFDatasets} from '$lib/queries/huggingfaceQueries';
  import {TextInput} from 'carbon-components-svelte';

  export let value: string;
  export let invalid: boolean;
  export let invalidText: string;

  const datasets = queryHFDatasets();

  $: datasetExists = $datasets.data?.includes(value);
</script>

<TextInput
  bind:value
  {invalid}
  {invalidText}
  warn={!datasetExists}
  warnText={"Dataset doesn't exist"}
/>
