<script lang="ts">
  import {useListHFDatasetsQuery} from '$lib/store/apiHuggingface';
  import {TextInput} from 'carbon-components-svelte';

  export let value: string;
  export let invalid: boolean;
  export let invalidText: string;

  const datasets = useListHFDatasetsQuery();

  $: datasetExists = $datasets.data?.includes(value);
</script>

<TextInput
  bind:value
  {invalid}
  {invalidText}
  warn={!datasetExists}
  warnText={"Dataset doesn't exist"}
/>
