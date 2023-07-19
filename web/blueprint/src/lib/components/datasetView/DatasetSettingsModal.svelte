<script lang="ts">
  import {
    queryDatasetSchema,
    querySettings,
    updateSettingsMutation
  } from '$lib/queries/datasetQueries';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {petals, serializePath, type DatasetSettings} from '$lilac';
  import {
    ComposedModal,
    ModalBody,
    ModalFooter,
    ModalHeader,
    MultiSelect,
    SkeletonText
  } from 'carbon-components-svelte';
  import type {
    MultiSelectItem,
    MultiSelectItemId
  } from 'carbon-components-svelte/types/MultiSelect/MultiSelect.svelte';

  export let open = false;
  const datasetViewStore = getDatasetViewContext();

  $: settings = querySettings($datasetViewStore.namespace, $datasetViewStore.datasetName);
  $: updateSettings = updateSettingsMutation();

  $: schema = queryDatasetSchema($datasetViewStore.namespace, $datasetViewStore.datasetName);
  $: fields = petals($schema.data);

  $: fieldItems = fields.map(field => ({
    id: serializePath(field.path),
    text: serializePath(field.path)
  }));

  // Add the default media here if there is nothing.
  $: serverSelectedIds = fieldItems
    .filter(fieldItem =>
      ($settings.data?.ui?.media_paths || []).some(
        mediaPath => serializePath(mediaPath) === fieldItem.id
      )
    )
    .map(fieldItem => fieldItem.id);

  let selectedIds: MultiSelectItemId[] = [];
  function submit() {
    const newSettings: DatasetSettings = {
      ui: {
        media_paths: selectedIds.map(id => id.split('.'))
      }
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
  function select(
    e: CustomEvent<{
      selectedIds: MultiSelectItemId[];
      selected: MultiSelectItem[];
      unselected: MultiSelectItem[];
    }>
  ) {
    selectedIds = e.detail.selectedIds;
  }
</script>

<ComposedModal {open} on:submit={submit} on:close={() => (open = false)}>
  <ModalHeader label="Changes" title="Dataset settings" />
  <ModalBody hasForm>
    {#if $settings.isFetching}
      <SkeletonText />
    {:else}
      <div class="h-96">
        <MultiSelect
          on:select={select}
          titleText="Media fields"
          filterable
          items={fieldItems}
          selectedIds={serverSelectedIds}
          placeholder={'Select media fields'}
        />
      </div>
    {/if}
  </ModalBody>
  <ModalFooter primaryButtonText="Save" />
</ComposedModal>
