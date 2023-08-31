<script lang="ts">
  import {queryDatasets} from '$lib/queries/langsmithQueries';
  import {ComboBox, TextInput} from 'carbon-components-svelte';

  export let value: string | undefined;
  export let invalid: boolean;
  export let invalidText: string;

  $: datasetsQuery = queryDatasets();
  $: items = $datasetsQuery.data?.map(s => ({
    id: s,
    text: s
  }));
</script>

{#if items}
  <ComboBox
    on:select={e => (value = e.detail.selectedId)}
    on:clear={() => (value = undefined)}
    {invalid}
    {invalidText}
    warn={items.length === 0}
    warnText={'No datasets found'}
    {items}
  />
{:else}
  <TextInput bind:value {invalid} {invalidText} labelText="Dataset" />
{/if}
