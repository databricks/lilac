<script lang="ts">
  import {queryDatasetSchema} from '$lib/queries/datasetQueries';
  import {queryEmbeddings} from '$lib/queries/signalQueries';
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
  export let newSettings: DatasetSettings;

  $: schema = queryDatasetSchema(namespace, datasetName);
  const embeddings = queryEmbeddings();

  $: viewType = newSettings?.ui?.view_type || 'single_item';

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
          .filter(f => !newSettings.ui?.media_paths?.includes(f.path))
          .map(f => {
            const serializedPath = serializePath(f.path);
            return {id: f, text: serializedPath};
          })
      : null;
  function selectMediaField(e: CustomEvent<MediaFieldComboBoxItem>) {
    const field = e.detail.id;
    if (newSettings.ui == null) {
      newSettings.ui = {};
    }
    if (newSettings.ui.media_paths == null) {
      newSettings.ui.media_paths = [];
    }
    const existingPath = newSettings.ui.media_paths.find(p => pathIsEqual(p, field.path));
    if (existingPath != null) return;
    newSettings.ui.media_paths = [...newSettings.ui.media_paths, field.path];
  }
  function removeMediaField(field: LilacField) {
    if (newSettings.ui?.media_paths == null) return;
    newSettings.ui.media_paths = newSettings.ui.media_paths.filter(
      p => !pathIsEqual(p, field.path)
    );
  }
  function moveMediaFieldUp(mediaField: LilacField) {
    if (newSettings.ui?.media_paths == null) return;
    const index = newSettings.ui.media_paths.findIndex(p => pathIsEqual(p, mediaField.path));
    if (index <= 0) return;
    newSettings.ui.media_paths = [
      ...newSettings.ui.media_paths.slice(0, index - 1),
      mediaField.path,
      newSettings.ui.media_paths[index - 1],
      ...newSettings.ui.media_paths.slice(index + 1)
    ];
  }
  function moveMediaFieldDown(mediaField: LilacField) {
    if (newSettings.ui?.media_paths == null) return;
    const index = newSettings.ui.media_paths.findIndex(p => pathIsEqual(p, mediaField.path));
    if (index < 0 || index >= newSettings.ui.media_paths.length - 1) return;
    newSettings.ui.media_paths = [
      ...newSettings.ui.media_paths.slice(0, index),
      newSettings.ui.media_paths[index + 1],
      mediaField.path,
      ...newSettings.ui.media_paths.slice(index + 2)
    ];
  }
  // Markdown.
  function isMarkdownRendered(field: LilacField) {
    return newSettings.ui?.markdown_paths?.find(p => pathIsEqual(p, field.path)) != null;
  }
  function markdownToggle(e: CustomEvent<{toggled: boolean}>, field: LilacField) {
    if (e.detail.toggled) {
      addMarkdownField(field);
    } else {
      removeMarkdownField(field);
    }
  }
  function addMarkdownField(field: LilacField) {
    if (newSettings.ui == null) {
      newSettings.ui = {};
    }
    if (newSettings.ui.markdown_paths == null) {
      newSettings.ui.markdown_paths = [];
    }
    const existingPath = newSettings.ui.markdown_paths.find(p => pathIsEqual(p, field.path));
    if (existingPath != null) return;
    newSettings.ui.markdown_paths = [...newSettings.ui.markdown_paths, field.path];
  }
  function removeMarkdownField(field: LilacField) {
    if (newSettings.ui == null) {
      return;
    }
    if (newSettings.ui.markdown_paths == null) {
      return;
    }
    newSettings.ui.markdown_paths = newSettings.ui.markdown_paths.filter(
      p => !pathIsEqual(p, field.path)
    );
  }

  function embeddingChanged(e: Event) {
    const embedding = (e.target as HTMLSelectElement).value;
    newSettings.preferred_embedding = embedding === '' ? undefined : embedding;
  }
</script>

{#if newSettings == null || $schema.data == null}
  <SkeletonText />
{:else}
  <div class="flex flex-col gap-y-6">
    <section class="flex flex-col gap-y-4">
      <div class="text-lg text-gray-700">Media fields</div>
      <div class="text-sm text-gray-500">
        Media fields are text fields that are rendered large in the dataset viewer. They are the
        fields on which you can compute signals, embeddings, search, and label.
      </div>

      {#if newSettings.ui?.media_paths != null && mediaFieldOptions != null}
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
              {#each newSettings.ui.media_paths as mediaPath, i}
                {@const mediaField = mediaFieldOptions.find(f => pathIsEqual(f.path, mediaPath))}
                {#if mediaField}
                  {@const isSignal = isSignalField(mediaField)}
                  {@const isLabel = isLabelField(mediaField)}
                  {@const moveUpDisabled = i === 0}
                  {@const moveDownDisabled = i === newSettings.ui.media_paths.length - 1}
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
                        <div
                          class="align-middle"
                          use:hoverTooltip={{text: 'Move media field down'}}
                        >
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
                {/if}
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
              hoist={false}
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
            if (newSettings?.ui != null) {
              newSettings.ui.view_type = 'scroll';
            }
          }}
        />
        <Chip
          icon={Document}
          label="Single Item"
          active={viewType == 'single_item'}
          tooltip="Individual item"
          on:click={() => {
            if (newSettings?.ui != null) {
              newSettings.ui.view_type = 'single_item';
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
            selected={newSettings?.preferred_embedding || undefined}
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
