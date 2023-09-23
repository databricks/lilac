<script lang="ts">
  import {querySelectRows} from '$lib/queries/datasetQueries';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {
    childFields,
    isLabelField,
    isSignalField,
    isSignalRootField,
    petals,
    type LilacField,
    type LilacSchema
  } from '$lilac';
  import {
    ComposedModal,
    ModalBody,
    ModalFooter,
    ModalHeader,
    SkeletonText,
    TextArea
  } from 'carbon-components-svelte';
  import {createEventDispatcher} from 'svelte';
  import DownloadFieldList from './DownloadFieldList.svelte';

  export let open = false;
  export let schema: LilacSchema;

  const dispatch = createEventDispatcher();

  const datasetViewStore = getDatasetViewContext();

  $: ({sourceFields, enrichedFields, labelFields} = getFields(schema));

  let checkedSourceFields: LilacField[] = [];
  let checkedLabeledFields: LilacField[] = [];
  let checkedEnrichedFields: LilacField[] = [];

  $: downloadFields = [...checkedSourceFields, ...checkedLabeledFields, ...checkedEnrichedFields];

  $: previewRows =
    downloadFields.length > 0
      ? querySelectRows($datasetViewStore.namespace, $datasetViewStore.datasetName, {
          columns: downloadFields.map(x => x.path),
          limit: 3,
          combine_columns: false
        })
      : null;

  function getFields(schema: LilacSchema) {
    const allFields = childFields(schema);
    const petalFields = petals(schema).filter(field => ['embedding'].indexOf(field.dtype!) === -1);
    const sourceFields = petalFields.filter(f => !isSignalField(f) && !isLabelField(f));
    const labelFields = allFields.filter(f => f.label != null);
    const enrichedFields = allFields
      .filter(f => isSignalRootField(f))
      .filter(f => !childFields(f).some(f => f.dtype === 'embedding'));
    return {sourceFields, enrichedFields, labelFields};
  }

  async function submit() {
    const namespace = $datasetViewStore.namespace;
    const datasetName = $datasetViewStore.datasetName;
    const options = {combine_columns: false, columns: downloadFields.map(x => x.path)};
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

<ComposedModal size="lg" {open} on:submit={submit} on:close={() => (open = false)}>
  <ModalHeader title="Download data" />
  <ModalBody hasForm>
    <div class="flex flex-wrap gap-x-12">
      <section>
        <h4>Source fields</h4>
        <DownloadFieldList fields={sourceFields} bind:checkedFields={checkedSourceFields} />
      </section>
      {#if labelFields.length > 0}
        <section>
          <h4>Label fields</h4>
          <DownloadFieldList fields={labelFields} bind:checkedFields={checkedLabeledFields} />
        </section>
      {/if}
      {#if enrichedFields.length > 0}
        <section>
          <h4>Enriched fields</h4>
          <DownloadFieldList fields={enrichedFields} bind:checkedFields={checkedEnrichedFields} />
        </section>
      {/if}
    </div>

    <section>
      <h4>Download preview</h4>
      {#if downloadFields.length === 0}
        <p class="text-gray-600">
          No fields selected. Please select at least one field to download.
        </p>
      {/if}
      <div class="preview">
        {#if $previewRows && $previewRows.isFetching}
          <SkeletonText paragraph />
        {:else if previewRows && $previewRows}
          <TextArea
            value={JSON.stringify($previewRows.data, null, 2)}
            readonly
            rows={30}
            placeholder="3 rows of data for previewing the response"
            class="mb-2 font-mono"
          />
        {/if}
      </div>
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
  .preview {
    height: 30rem;
  }
</style>
