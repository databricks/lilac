<script lang="ts">
  import {querySelectRows} from '$lib/queries/datasetQueries';
  import {getDatasetContext} from '$lib/stores/datasetStore';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {UUID_COLUMN, isSignalField, petals, type LilacField, type LilacSchema} from '$lilac';
  import {
    ComposedModal,
    ModalBody,
    ModalFooter,
    ModalHeader,
    SkeletonText
  } from 'carbon-components-svelte';
  import {createEventDispatcher} from 'svelte';
  import DownloadFieldList from './DownloadFieldList.svelte';

  export let open = false;
  export let schema: LilacSchema;

  const dispatch = createEventDispatcher();

  const datasetViewStore = getDatasetViewContext();
  const datasetStore = getDatasetContext();

  $: ({sourceFields, enrichedFields} = getFields(schema));

  let checkedSourceFields: LilacField[] = [];
  let checkedEnrichedFields: LilacField[] = [];

  $: downloadFields = [...checkedSourceFields, ...checkedEnrichedFields];

  $: previewRows = querySelectRows($datasetViewStore.namespace, $datasetViewStore.datasetName, {
    columns: downloadFields.map(x => x.path),
    limit: 3,
    combine_columns: false
  });

  $: console.log($previewRows.data);

  function getFields(schema: LilacSchema | undefined) {
    if (schema == null) {
      return {sourceFields: null, enrichedFields: null};
    }
    const petalFields = petals(schema).filter(
      field => ['string_span', 'embedding'].indexOf(field.dtype!) === -1
    );
    const sourceFields = petalFields.filter(
      f => !isSignalField(f, schema) && f.path.at(-1) !== UUID_COLUMN
    );
    const enrichedFields = petalFields.filter(f => isSignalField(f, schema));
    return {sourceFields, enrichedFields};
  }

  async function submit() {
    const namespace = $datasetViewStore.namespace;
    const datasetName = $datasetViewStore.datasetName;
    const options = $datasetViewStore.queryOptions;
    options.columns = $datasetStore.visibleFields?.map(x => x.path);
    const url =
      `/api/v1/datasets/${namespace}/${datasetName}/select_rows_download` +
      `?url_safe_options=${encodeURIComponent(JSON.stringify(options))}`;
    const link = document.createElement('a');
    link.download = `${namespace}_${datasetName}.json`;
    link.href = url;
    document.body.appendChild(link);
    link.click();
    link.remove();
  }

  function close() {
    open = false;
    dispatch('close');
  }
</script>

<ComposedModal {open} on:submit={submit} on:close={() => (open = false)}>
  <ModalHeader title="Download data" />
  <ModalBody hasForm>
    <section>
      {#if downloadFields.length === 0}
        <p class="text-gray-600">
          No fields selected. Please select at least one field to download.
        </p>
      {/if}
    </section>
    <section>
      <h4>Select source fields</h4>
      {#if sourceFields == null}
        <SkeletonText />
      {:else}
        <DownloadFieldList fields={sourceFields} bind:checkedFields={checkedSourceFields} />
      {/if}
    </section>
    {#if enrichedFields == null || enrichedFields.length > 0}
      <section>
        <h4>Select enriched fields</h4>
        {#if enrichedFields == null}
          <SkeletonText />
        {:else}
          <DownloadFieldList fields={enrichedFields} bind:checkedFields={checkedEnrichedFields} />
        {/if}
      </section>
    {/if}
    <section>
      <h4>Download preview</h4>
    </section>
  </ModalBody>
  <ModalFooter
    primaryButtonText="Download"
    primaryButtonDisabled={downloadFields.length === 0}
    secondaryButtonText="Cancel"
    on:click:button--secondary={close}
  />
</ComposedModal>

<style lang="postcss">
  h4 {
    @apply mb-2 mt-6;
  }
</style>
