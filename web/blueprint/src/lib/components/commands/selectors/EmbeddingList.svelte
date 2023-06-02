<script lang="ts">
  import {queryEmbeddings} from '$lib/queries/signalQueries';
  import type {SignalInfoWithTypedSchema} from '$lilac';
  import CommandSelectList from './CommandSelectList.svelte';

  export let embedding: SignalInfoWithTypedSchema | undefined = undefined;

  const embeddings = queryEmbeddings();
  $: {
    if ($embeddings.isSuccess && !embedding) {
      embedding = $embeddings.data?.[0];
    }
  }
</script>

{#if $embeddings.isSuccess}
  <CommandSelectList
    items={$embeddings.data.map(emb => ({
      title: emb.json_schema.title || 'Unnamed embedding',
      value: emb
    }))}
    item={embedding}
    on:select={e => (embedding = e.detail)}
  />
{:else if $embeddings.isLoading}
  <CommandSelectList skeleton />
{/if}
