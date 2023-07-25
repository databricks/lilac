<script lang="ts">
  import {querySettings, updateSettingsMutation} from '$lib/queries/datasetQueries';
  import {queryEmbeddings} from '$lib/queries/signalQueries';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {getSettingsContext} from '$lib/stores/settingsStore';
  import {
    UUID_COLUMN,
    isSignalField,
    pathIsEqual,
    petals,
    type DatasetSettings,
    type LilacField,
    type LilacSchema
  } from '$lilac';
  import {
    ComposedModal,
    ModalBody,
    ModalFooter,
    ModalHeader,
    Select,
    SelectItem,
    SelectSkeleton,
    SkeletonText
  } from 'carbon-components-svelte';
  import DownloadFieldList from './DownloadFieldList.svelte';

  export let open = false;
  export let schema: LilacSchema;

  const datasetViewStore = getDatasetViewContext();
  const appSettings = getSettingsContext();
  const embeddings = queryEmbeddings();
  const updateSettings = updateSettingsMutation();

  $: settings = querySettings($datasetViewStore.namespace, $datasetViewStore.datasetName);

  let selectedMediaFields: LilacField[] | null = null;
  let preferredEmbedding: string | undefined = $appSettings.embedding;

  $: mediaFields = petals(schema).filter(
    f => f.dtype === 'string' && !pathIsEqual(f.path, [UUID_COLUMN]) && !isSignalField(f, schema)
  );

  $: {
    if (selectedMediaFields == null) {
      const selectedMediaPaths = $settings.data?.ui?.media_paths || [];
      selectedMediaFields = mediaFields.filter(f =>
        selectedMediaPaths.some(path => pathIsEqual(f.path, path))
      );
    }
  }

  function embeddingChanged(e: Event) {
    const embedding = (e.target as HTMLSelectElement).value;
    preferredEmbedding = embedding;
    if (preferredEmbedding === '') {
      preferredEmbedding = undefined;
    }
  }

  function submit() {
    if (selectedMediaFields == null) return;
    const newSettings: DatasetSettings = {
      ui: {
        media_paths: selectedMediaFields.map(f => f.path)
      },
      preferred_embedding: preferredEmbedding
    };
    $updateSettings.mutate(
      [$datasetViewStore.namespace, $datasetViewStore.datasetName, newSettings],
      {
        onSuccess: () => {
          open = false;
        }
      }
    );
  }
</script>

<ComposedModal {open} on:submit={submit} on:close={() => (open = false)}>
  <ModalHeader label="Changes" title="Dataset settings" />
  <ModalBody hasForm>
    {#if $settings.isFetching}
      <SkeletonText />
    {:else}
      <div class="flex flex-col gap-y-6">
        <section class="flex flex-col gap-y-1">
          <div class="text-lg text-gray-700">Media fields</div>
          <div class="text-sm text-gray-500">
            These fields will be presented differently from the rest of the metadata fields.
          </div>
          {#if selectedMediaFields != null}
            <DownloadFieldList fields={mediaFields} bind:checkedFields={selectedMediaFields} />
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
              <Select selected={$settings.data?.preferred_embedding} on:change={embeddingChanged}>
                <SelectItem value={undefined} text="None" />
                {#each $embeddings.data || [] as emdField}
                  <SelectItem value={emdField.name} />
                {/each}
              </Select>
            {/if}
          </div>
        </section>
      </div>
    {/if}
  </ModalBody>
  <ModalFooter primaryButtonText="Save" />
</ComposedModal>
