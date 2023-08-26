<script lang="ts">
  import {goto} from '$app/navigation';
  import {
    deleteDatasetMutation,
    querySettings,
    updateSettingsMutation
  } from '$lib/queries/datasetQueries';
  import {queryEmbeddings} from '$lib/queries/signalQueries';
  import {getSettingsContext} from '$lib/stores/settingsStore';
  import {datasetIdentifier} from '$lib/utils';
  import {
    ROWID,
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
    SkeletonText,
    TextInput
  } from 'carbon-components-svelte';
  import {TrashCan} from 'carbon-icons-svelte';
  import CommandSelectList from '../commands/selectors/CommandSelectList.svelte';
  import DownloadFieldList from './DownloadFieldList.svelte';

  export let namespace: string;
  export let name: string;

  export let open = false;
  export let schema: LilacSchema;

  const appSettings = getSettingsContext();
  const embeddings = queryEmbeddings();
  const updateSettings = updateSettingsMutation();

  $: settings = querySettings(namespace, name);
  $: identifier = datasetIdentifier(namespace, name);

  let settingsPage: 'fields' | 'administration' = 'fields';

  let selectedMediaFields: LilacField[] | null = null;
  let markdownMediaFields: LilacField[] | null = null;
  let preferredEmbedding: string | undefined = $appSettings.embedding;

  $: mediaFields = petals(schema).filter(
    f => f.dtype === 'string' && !pathIsEqual(f.path, [ROWID]) && !isSignalField(f)
  );

  $: {
    if (selectedMediaFields == null) {
      const mediaPathsFromSettings = $settings.data?.ui?.media_paths?.map(p =>
        Array.isArray(p) ? p : [p]
      );
      if (mediaPathsFromSettings != null) {
        selectedMediaFields = mediaFields.filter(f =>
          mediaPathsFromSettings.some(path => pathIsEqual(f.path, path))
        );
      }
    }
  }

  $: {
    if (markdownMediaFields == null) {
      const mardownPathsFromSettings = $settings.data?.ui?.markdown_paths;
      if (mardownPathsFromSettings != null) {
        markdownMediaFields = mediaFields.filter(f =>
          mardownPathsFromSettings.some(path => pathIsEqual(f.path, path))
        );
      }
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
        media_paths: selectedMediaFields.map(f => f.path),
        markdown_paths: markdownMediaFields?.map(f => f.path)
      },
      preferred_embedding: preferredEmbedding
    };
    $updateSettings.mutate([namespace, name, newSettings], {
      onSuccess: () => {
        open = false;
      }
    });
  }

  let deleteDatasetInputName = '';
  const deleteDataset = deleteDatasetMutation();
</script>

<ComposedModal {open} on:submit={submit} on:close={() => (open = false)}>
  <ModalHeader label="Changes" title="Dataset settings" />
  <ModalBody hasForm>
    <div class="flex flex-row">
      <div class="-ml-4 mr-4 w-96 grow-0">
        <CommandSelectList
          items={[
            {
              title: 'Fields',
              value: 'fields'
            },
            {title: 'Administration', value: 'administration'}
          ]}
          item={settingsPage}
          on:select={e => (settingsPage = e.detail)}
        />
      </div>
      <div class="flex w-full flex-col gap-y-6 rounded border border-gray-300 bg-white p-4">
        {#if settingsPage === 'fields'}
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
                  <DownloadFieldList
                    fields={mediaFields}
                    bind:checkedFields={selectedMediaFields}
                  />
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
                      selected={$settings.data?.preferred_embedding}
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
                <div class="text-lg text-gray-700">Render as markdown</div>
                {#if selectedMediaFields != null && markdownMediaFields != null}
                  <DownloadFieldList
                    fields={selectedMediaFields}
                    bind:checkedFields={markdownMediaFields}
                  />
                {/if}
              </section>
            </div>
          {/if}
        {:else if settingsPage === 'administration'}
          <div class="flex flex-col gap-y-6">
            <section class="flex flex-col gap-y-1">
              <div class="text-lg text-gray-700">Delete this dataset</div>
              <div class="mb-4 text-sm text-gray-500">
                <p class="mb-2">This action cannot be undone.</p>
                <p>
                  This will permanently delete the
                  <span class="font-bold">{identifier}</span> dataset and all its files. Please type
                  <span class="font-bold">{identifier}</span> to confirm.
                </p>
              </div>
              <TextInput
                bind:value={deleteDatasetInputName}
                invalid={deleteDatasetInputName != identifier}
              />
              <button
                class="flex cursor-pointer flex-row justify-between p-4 text-left hover:bg-gray-200"
                class:cursor-not-allowed={deleteDatasetInputName != identifier}
                disabled={deleteDatasetInputName != identifier}
                on:click={() =>
                  $deleteDataset.mutate([namespace, name], {onSuccess: () => goto('/')})}
              >
                I understand, delete this dataset
                <TrashCan /></button
              >
            </section>
          </div>
        {/if}
      </div>
    </div></ModalBody
  >
  <ModalFooter
    primaryButtonText="Save"
    secondaryButtonText="Cancel"
    on:click:button--secondary={close}
  />
</ComposedModal>
