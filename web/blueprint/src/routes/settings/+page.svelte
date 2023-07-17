<script lang="ts">
  import Page from '$lib/components/Page.svelte';
  import {queryEmbeddings} from '$lib/queries/signalQueries';
  import {getSettingsContext} from '$lib/stores/settingsStore';
  import {Select, SelectItem, SelectSkeleton} from 'carbon-components-svelte';

  $: embeddings = queryEmbeddings();
  $: settings = getSettingsContext();

  function embeddingChanged(e: Event) {
    const embedding = (e.target as HTMLSelectElement).value;
    settings.setEmbedding(embedding);
  }
</script>

<Page title={'Settings'}>
  <div class="lilac-container">
    <div class="lilac-page flex">
      <div class="w-60">
        {#if $embeddings.isFetching}
          <SelectSkeleton />
        {:else}
          <Select
            labelText="Default embedding"
            selected={$settings.embedding}
            on:change={embeddingChanged}
          >
            {#each $embeddings.data || [] as emdField}
              <SelectItem value={emdField.name} />
            {/each}
          </Select>
        {/if}
      </div>
    </div>
  </div>
</Page>
