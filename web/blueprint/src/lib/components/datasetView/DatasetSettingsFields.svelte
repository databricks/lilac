<script lang="ts">
  import {queryDatasetSchema, querySettings} from '$lib/queries/datasetQueries';
  import {queryEmbeddings} from '$lib/queries/signalQueries';
  import {getSettingsContext} from '$lib/stores/settingsStore';
  import {
    ROWID,
    isSignalField,
    pathIsEqual,
    petals,
    type DatasetSettings,
    type LilacField
  } from '$lilac';
  import {Select, SelectItem, SelectSkeleton, SkeletonText} from 'carbon-components-svelte';
  import DownloadFieldList from './DownloadFieldList.svelte';

  export let namespace: string;
  export let datasetName: string;
  export let settings: DatasetSettings | undefined = undefined;

  $: schema = queryDatasetSchema(namespace, datasetName);
  const embeddings = queryEmbeddings();

  $: currentSettings = querySettings(namespace, datasetName);

  const appSettings = getSettingsContext();

  let selectedMediaFields: LilacField[] | null = null;
  let markdownMediaFields: LilacField[] | null = null;
  let preferredEmbedding: string | undefined = $appSettings.embedding;

  $: mediaFields =
    $schema.data != null
      ? petals($schema.data).filter(
          f => f.dtype === 'string' && !pathIsEqual(f.path, [ROWID]) && !isSignalField(f)
        )
      : null;

  $: {
    if ($currentSettings.isFetching) {
      selectedMediaFields = null;
      markdownMediaFields = null;
    }
  }
  $: {
    if (
      selectedMediaFields == null &&
      mediaFields != null &&
      $currentSettings.data != null &&
      !$currentSettings.isFetching
    ) {
      const mediaPathsFromSettings = ($currentSettings.data.ui?.media_paths || []).map(p =>
        Array.isArray(p) ? p : [p]
      );
      selectedMediaFields = mediaFields.filter(f =>
        mediaPathsFromSettings.some(path => pathIsEqual(f.path, path))
      );
    }
  }

  $: {
    if (
      markdownMediaFields == null &&
      mediaFields != null &&
      $currentSettings.data != null &&
      !$currentSettings.isFetching
    ) {
      const mardownPathsFromSettings = ($currentSettings.data?.ui?.markdown_paths || []).map(p =>
        Array.isArray(p) ? p : [p]
      );
      markdownMediaFields = mediaFields.filter(f =>
        mardownPathsFromSettings.some(path => pathIsEqual(f.path, path))
      );
    }
  }

  $: {
    if (selectedMediaFields != null) {
      settings = {
        ui: {
          media_paths: selectedMediaFields.map(f => f.path),
          markdown_paths: markdownMediaFields?.map(f => f.path)
        },
        preferred_embedding: preferredEmbedding
      };
    }
  }

  function embeddingChanged(e: Event) {
    const embedding = (e.target as HTMLSelectElement).value;
    preferredEmbedding = embedding;
    if (preferredEmbedding === '') {
      preferredEmbedding = undefined;
    }
  }
</script>

{#if $currentSettings.isFetching}
  <SkeletonText />
{:else}
  <div class="flex flex-col gap-y-6">
    <section class="flex flex-col gap-y-1">
      <div class="text-lg text-gray-700">Media fields</div>
      <div class="text-sm text-gray-500">
        Media fields are text fields that are rendered large in the dataset viewer. They are the
        fields on which you can compute signals, embeddings, search, and label.
      </div>
      {#if selectedMediaFields != null && mediaFields != null}
        <DownloadFieldList fields={mediaFields} bind:checkedFields={selectedMediaFields} />
      {:else}
        <SelectSkeleton />
      {/if}
    </section>

    <section class="flex flex-col gap-y-1">
      <div class="text-lg text-gray-700">Preferred embedding</div>
      <div class="text-sm text-gray-500">
        This embedding will be used by default when indexing and querying the data.
      </div>
      <div class="w-60">
        {#if $embeddings.isFetching}
          <SelectSkeleton />
        {:else}
          <Select
            selected={$currentSettings.data?.preferred_embedding || undefined}
            on:change={embeddingChanged}
          >
            <SelectItem value={undefined} text="None" />
            {#each $embeddings.data || [] as emdField}
              <SelectItem value={emdField.name} />
            {/each}
          </Select>
        {/if}
      </div>
    </section>

    <section class="flex flex-col gap-y-1">
      <div class="text-lg text-gray-700">Render media as markdown</div>
      <div class="text-sm text-gray-500">
        These media fields will be rendered as markdown in the dataset viewer.
      </div>
      {#if selectedMediaFields != null && markdownMediaFields != null}
        <DownloadFieldList fields={selectedMediaFields} bind:checkedFields={markdownMediaFields} />
      {:else}
        <SelectSkeleton />
      {/if}
    </section>
  </div>
{/if}
