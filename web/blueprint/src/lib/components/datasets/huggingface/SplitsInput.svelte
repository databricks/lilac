<script lang="ts">
  import {queryHFDatasetExists, queryHFSplits} from '$lib/queries/huggingfaceQueries';
  import {ComboBox, TextInput} from 'carbon-components-svelte';

  export let value: string | undefined;
  export let invalid: boolean;
  export let invalidText: string;
  export let rootValue: {dataset_name: string; config_name?: string};

  $: datasetName = rootValue['dataset_name'];
  $: configName = rootValue['config_name'];
  $: datasetExistsQuery = queryHFDatasetExists(datasetName);
  $: datasetExists = $datasetExistsQuery.data === true;
  $: splits = datasetExists ? queryHFSplits(datasetName, configName) : undefined;
  $: items = $splits?.data?.map(s => ({
    id: `${s.config}/${s.split}`,
    text: `${s.config}/${s.split}`
  }));
</script>

{#if (items && datasetExists) || $datasetExistsQuery.isError}
  <ComboBox
    on:select={e => (value = e.detail.selectedId.split('/')[1])}
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
