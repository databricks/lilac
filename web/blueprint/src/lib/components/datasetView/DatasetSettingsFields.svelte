<script lang="ts">
  import {queryDatasetSchema, querySettings} from '$lib/queries/datasetQueries';
  import {queryEmbeddings} from '$lib/queries/signalQueries';
  import {getSettingsContext} from '$lib/stores/settingsStore';
  import {DTYPE_TO_ICON} from '$lib/view_utils';
  import {
    PATH_WILDCARD,
    ROWID,
    isLabelField,
    isSignalField,
    pathIsEqual,
    petals,
    serializePath,
    type DatasetSettings,
    type LilacField
  } from '$lilac';
  import {Select, SelectItem, SelectSkeleton, SkeletonText, Toggle} from 'carbon-components-svelte';
  import {Add, ArrowDown, ArrowUp, Close, Document, Table} from 'carbon-icons-svelte';
  import ButtonDropdown from '../ButtonDropdown.svelte';
  import {hoverTooltip} from '../common/HoverTooltip';
  import Chip from './Chip.svelte';

  export let namespace: string;
  export let datasetName: string;
  export let settings: DatasetSettings | undefined = undefined;

  $: schema = queryDatasetSchema(namespace, datasetName);
  const embeddings = queryEmbeddings();

  $: settingsQuery = querySettings(namespace, datasetName);

  $: {
    if (settings == null && !$settingsQuery.isFetching) {
      settings = JSON.parse(JSON.stringify($settingsQuery.data));
      selectedMediaFields = null;
      markdownMediaFields = null;
    }
  }

  $: viewType = settings?.ui?.view_type || 'scroll';

  const appSettings = getSettingsContext();

  let selectedMediaFields: LilacField[] | null = null;
  let markdownMediaFields: LilacField[] | null = null;
  let preferredEmbedding: string | undefined = $appSettings.embedding;
  $: mediaFieldOptions =
    $schema.data != null
      ? petals($schema.data).filter(
          f =>
            f.dtype?.type === 'string' &&
            !pathIsEqual(f.path, [ROWID]) &&
            !isSignalField(f) &&
            !isLabelField(f)
        )
      : null;
  interface MediaFieldComboBoxItem {
    id: LilacField;
    text: string;
  }
  $: mediaFieldOptionsItems =
    mediaFieldOptions != null
      ? mediaFieldOptions
          .filter(f => !selectedMediaFields?.includes(f))
          .map(f => {
            const serializedPath = serializePath(f.path);
            return {id: f, text: serializedPath};
          })
      : null;
  function selectMediaField(e: CustomEvent<MediaFieldComboBoxItem>) {
    const mediaField = e.detail.id;
    if (selectedMediaFields == null || selectedMediaFields.includes(mediaField)) return;
    selectedMediaFields = [...selectedMediaFields, mediaField];
  }
  function removeMediaField(mediaField: LilacField) {
    if (selectedMediaFields == null) return;
    selectedMediaFields = selectedMediaFields?.filter(f => f !== mediaField);
  }
  function moveMediaFieldUp(mediaField: LilacField) {
    if (selectedMediaFields == null || settings?.ui == null) return;
    const index = selectedMediaFields.indexOf(mediaField);
    if (index <= 0) return;
    selectedMediaFields = [
      ...selectedMediaFields.slice(0, index - 1),
      mediaField,
      selectedMediaFields[index - 1],
      ...selectedMediaFields.slice(index + 1)
    ];
  }
  function moveMediaFieldDown(mediaField: LilacField) {
    if (selectedMediaFields == null || settings?.ui == null) return;
    const index = selectedMediaFields.indexOf(mediaField);
    if (index < 0 || index >= selectedMediaFields.length - 1) return;
    selectedMediaFields = [
      ...selectedMediaFields.slice(0, index),
      selectedMediaFields[index + 1],
      mediaField,
      ...selectedMediaFields.slice(index + 2)
    ];
  }
  // Markdown.
  function isMarkdownRendered(field: LilacField) {
    return markdownMediaFields?.includes(field);
  }
  function markdownToggle(e: CustomEvent<{toggled: boolean}>, field: LilacField) {
    if (e.detail.toggled) {
      addMarkdownField(field);
    } else {
      removeMarkdownField(field);
    }
  }
  function addMarkdownField(field: LilacField) {
    if (markdownMediaFields == null || markdownMediaFields.includes(field)) return;
    markdownMediaFields = [...markdownMediaFields, field];
  }
  function removeMarkdownField(field: LilacField) {
    if (markdownMediaFields == null) return;
    markdownMediaFields = markdownMediaFields.filter(f => f !== field);
  }

  $: {
    if ($settingsQuery.isFetching) {
      selectedMediaFields = null;
      markdownMediaFields = null;
    }
  }
  $: {
    if (
      selectedMediaFields == null &&
      mediaFieldOptions != null &&
      $settingsQuery.data?.ui?.media_paths != null &&
      !$settingsQuery.isFetching
    ) {
      const mediaPathsFromSettings = $settingsQuery.data.ui.media_paths.map(p =>
        Array.isArray(p) ? p : [p]
      );
      selectedMediaFields = mediaPathsFromSettings.flatMap(path => {
        const field = mediaFieldOptions!.find(f => pathIsEqual(f.path, path));
        if (field == null) {
          return [];
        }
        return [field];
      });
    }
  }

  $: {
    if (
      markdownMediaFields == null &&
      mediaFieldOptions != null &&
      $settingsQuery.data?.ui?.markdown_paths != null
    ) {
      const mardownPathsFromSettings = $settingsQuery.data.ui.markdown_paths.map(p =>
        Array.isArray(p) ? p : [p]
      );
      markdownMediaFields = mediaFieldOptions.filter(f =>
        mardownPathsFromSettings.some(path => pathIsEqual(f.path, path))
      );
    }
  }

  $: {
    if (settings?.ui != null) {
      settings.ui.media_paths = selectedMediaFields?.map(f => f.path);
      settings.ui.markdown_paths = markdownMediaFields?.map(f => f.path);
    }
  }

  $: {
    if (settings != null && settings.preferred_embedding == null) {
      settings.preferred_embedding = preferredEmbedding;
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

{#if $settingsQuery.isFetching}
  <SkeletonText />
{:else}
  <div class="flex flex-col gap-y-6">
    <section class="flex flex-col gap-y-4">
      <div class="text-lg text-gray-700">Media fields</div>
      <div class="text-sm text-gray-500">
        Media fields are text fields that are rendered large in the dataset viewer. They are the
        fields on which you can compute signals, embeddings, search, and label.
      </div>

      {#if selectedMediaFields != null && mediaFieldOptions != null}
        <div class="table border-spacing-1 gap-y-2">
          <div class="table-header-group items-center">
            <div class="table-row text-xs text-neutral-600">
              <div class="table-cell" />
              <div class="table-cell">Field</div>
              <div
                use:hoverTooltip={{text: 'Render media field with a markdown renderer.'}}
                class="table-cell"
              >
                Markdown
              </div>
              <div class="table-cell" />
            </div>
          </div>
          {#if mediaFieldOptions}
            <div class="table-row-group">
              {#each selectedMediaFields as mediaField, i}
                {@const isSignal = isSignalField(mediaField)}
                {@const isLabel = isLabelField(mediaField)}
                {@const moveUpDisabled = i === 0}
                {@const moveDownDisabled = i === selectedMediaFields.length - 1}
                <div class="table-row h-10">
                  <div
                    class="table-cell w-12 rounded-md p-0.5 align-middle"
                    class:bg-blue-200={isSignal}
                    class:bg-teal-100={isLabel}
                  >
                    {#if mediaField.dtype && mediaField.dtype.type !== 'map'}
                      <svelte:component
                        this={DTYPE_TO_ICON[mediaField.dtype.type]}
                        title={mediaField.dtype.type}
                      />
                    {:else}
                      <span class="font-mono" title={mediaField.dtype?.type}>{'{}'}</span>
                    {/if}
                    {#if mediaField.path.indexOf(PATH_WILDCARD) >= 0}[]{/if}
                  </div>
                  <div class="table-cell w-40 align-middle">
                    {serializePath(mediaField.path)}
                  </div>
                  <div class="table-cell w-8 align-middle">
                    <Toggle
                      class="mx-auto w-8"
                      size="sm"
                      hideLabel={true}
                      labelA=""
                      labelB=""
                      toggled={isMarkdownRendered(mediaField)}
                      on:toggle={e => markdownToggle(e, mediaField)}
                    />
                  </div>
                  <div class="table-cell">
                    <div class="flex flex-row gap-x-1">
                      <div
                        class="ml-auto align-middle"
                        use:hoverTooltip={{text: 'Move media field up'}}
                      >
                        <button
                          disabled={moveUpDisabled}
                          class:opacity-50={moveUpDisabled}
                          on:click={() => moveMediaFieldUp(mediaField)}
                        >
                          <ArrowUp size={16} />
                        </button>
                      </div>
                      <div class="align-middle" use:hoverTooltip={{text: 'Move media field down'}}>
                        <button
                          disabled={moveDownDisabled}
                          class:opacity-50={moveDownDisabled}
                          on:click={() => moveMediaFieldDown(mediaField)}
                        >
                          <ArrowDown size={16} />
                        </button>
                      </div>
                      <div class="align-middle" use:hoverTooltip={{text: 'Remove media field'}}>
                        <button on:click={() => removeMediaField(mediaField)}>
                          <Close size={16} />
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              {/each}
            </div>
          {/if}
        </div>
        <div class="h-12">
          {#if mediaFieldOptionsItems}
            <ButtonDropdown
              buttonOutline
              disabled={mediaFieldOptionsItems.length === 0}
              buttonIcon={Add}
              items={mediaFieldOptionsItems}
              buttonText="Add media field"
              comboBoxPlaceholder="Add media field"
              on:select={selectMediaField}
            />
          {/if}
        </div>
      {:else}
        <SelectSkeleton />
      {/if}
    </section>

    <section class="flex flex-col gap-y-1">
      <div class="text-lg text-gray-700">View type</div>
      <div class="flex gap-x-2">
        <Chip
          icon={Table}
          label="Scroll"
          active={viewType == 'scroll'}
          tooltip="Infinite scroll with snippets"
          on:click={() => {
            if (settings?.ui != null) {
              settings.ui.view_type = 'scroll';
            }
          }}
        />
        <Chip
          icon={Document}
          label="Single Item"
          active={viewType == 'single_item'}
          tooltip="Individual item"
          on:click={() => {
            if (settings?.ui != null) {
              settings.ui.view_type = 'single_item';
            }
          }}
        />
      </div>
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
            selected={settings?.preferred_embedding || undefined}
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
  </div>
{/if}
