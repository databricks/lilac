<script lang="ts">
  import {queryHFDatasetExists, queryHFSplits} from '$lib/queries/huggingfaceQueries';
  import {ComboBox, TextInput} from 'carbon-components-svelte';

  export let value: string;
  export let invalid: boolean;
  export let invalidText: string;
  export let rootValue: {dataset_name: string};

  $: datasetName = rootValue['dataset_name'];
  $: datasetExistsQuery = queryHFDatasetExists(datasetName);
  $: datasetExists = $datasetExistsQuery.data === true;
  $: splits = datasetExists ? queryHFSplits(datasetName) : undefined;
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
    placeholder="(optional)"
    items={$splits?.data?.map(s => ({id: s.split, text: s.split})) || []}
  />
{:else}
  <TextInput bind:value {invalid} {invalidText} labelText="Split" placeholder="(optional)" />
{/if}
