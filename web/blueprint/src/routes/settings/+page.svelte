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

<Page>
  <div class="lilac-page flex p-8">
    <div class="flex flex-col gap-y-6">
      <section class="flex flex-col gap-y-1">
        <div class="text-lg text-gray-700">Settings</div>
        <div class="mb-4 text-sm text-gray-500">
          Changes will apply to all datasets for your session. These settings are not saved
          server-side.
        </div>
        <div class="w-60">
          {#if $embeddings.isFetching}
            <SelectSkeleton />
          {:else}
            <Select
              labelText="Preferred embedding"
              selected={$settings.embedding}
              on:change={embeddingChanged}
            >
              {#each $embeddings.data || [] as emdField}
                <SelectItem value={emdField.name} />
              {/each}
            </Select>
          {/if}
        </div>
      </section>
    </div>
  </div>
</Page>
