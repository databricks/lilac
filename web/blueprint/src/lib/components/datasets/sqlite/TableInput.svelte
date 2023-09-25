<script lang="ts">
  import {queryTables} from '$lib/queries/sqliteQueries';
  import {ComboBox, TextInput} from 'carbon-components-svelte';

  export let value: string | undefined;
  export let invalid: boolean;
  export let invalidText: string;
  export let rootValue: {db_file?: string};

  $: dbFile = rootValue.db_file;

  $: tablesQuery = dbFile != null && dbFile !== '' ? queryTables(dbFile) : null;
  $: items = $tablesQuery?.data?.map(s => ({
    id: s,
    text: s
  }));
</script>

{#if items}
  <ComboBox
    on:select={e => (value = e.detail.selectedId)}
    on:clear={() => (value = undefined)}
    {invalid}
    invalidText={items.length === 0 ? `No tables found in ${dbFile}` : invalidText}
    {items}
  />
{:else}
  <TextInput bind:value {invalid} {invalidText} />
{/if}
