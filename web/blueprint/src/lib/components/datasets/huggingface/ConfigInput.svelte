<script lang="ts">
  import {queryHFDatasetExists, queryHFSplits} from '$lib/queries/huggingfaceQueries';
  import {ComboBox, TextInput} from 'carbon-components-svelte';

  export let value: string | undefined;
  export let invalid: boolean;
  export let invalidText: string;
  export let rootValue: {dataset_name: string; config_name?: string};

  $: datasetName = rootValue['dataset_name'];
  $: datasetExistsQuery = queryHFDatasetExists(datasetName);
  $: datasetExists = $datasetExistsQuery.data === true;
  $: configsQuery = datasetExists ? queryHFSplits(datasetName) : undefined;
  $: configs = $configsQuery?.data ? new Set($configsQuery.data.map(c => c.config)) : undefined;
  $: items = configs ? [...configs].map(c => ({id: c, text: c})) : undefined;
</script>

{#if items && datasetExists}
  <ComboBox
    value={value || ''}
    on:select={e => (value = e.detail.selectedItem?.id)}
    on:clear={() => (value = undefined)}
    {invalid}
    {invalidText}
    warn={!datasetExists}
    warnText={"Dataset doesn't exist"}
    placeholder="(optional)"
    {items}
  />
{:else}
  <TextInput bind:value {invalid} {invalidText} placeholder="(optional)" />
{/if}
