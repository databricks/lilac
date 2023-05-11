<script lang="ts">
  import {useGetHFSplitsQuery, useListHFDatasetsQuery} from '$lib/store/apiHuggingface';
  import {ComboBox, TextInput} from 'carbon-components-svelte';

  export let value: string;
  export let invalid: boolean;
  export let invalidText: string;
  export let rootValue: {dataset_name: string};

  $: datasetName = rootValue['dataset_name'];
  const datasets = useListHFDatasetsQuery();
  $: datasetExists = $datasets.data?.includes(datasetName);
  $: splits = datasetExists ? useGetHFSplitsQuery(datasetName) : undefined;
</script>

{#if $splits?.data && datasetExists}
  <ComboBox
    value={value || ''}
    on:select={e => (value = e.detail.selectedItem?.id)}
    {invalid}
    {invalidText}
    warn={!datasetExists}
    warnText={"Dataset doesn't exist"}
    titleText="Split"
    items={$splits?.data?.map(s => ({id: s.split, text: s.split})) || []}
  />
{:else}
  <TextInput bind:value {invalid} {invalidText} labelText="Split" />
{/if}
