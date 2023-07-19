<script lang="ts">
  import {queryDatasetSchema} from '$lib/queries/datasetQueries';
  import {getDatasetContext} from '$lib/stores/datasetStore';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {isSignalField, petals, type LilacField, type LilacSchema} from '$lilac';
  import {
    ComposedModal,
    ModalBody,
    ModalFooter,
    ModalHeader,
    SkeletonText
  } from 'carbon-components-svelte';
  import DownloadFieldList from './DownloadFieldList.svelte';

  export let open = false;

  const datasetViewStore = getDatasetViewContext();
  const datasetStore = getDatasetContext();

  $: schema = queryDatasetSchema($datasetViewStore.namespace, $datasetViewStore.datasetName);
  $: ({sourceFields, enrichedFields} = getFields($schema.data));

  let checkedSourceFields: LilacField[] = [];
  let checkedEnrichedFields: LilacField[] = [];

  $: downloadFields = [...checkedSourceFields, ...checkedEnrichedFields];

  $: console.log(downloadFields);

  function getFields(schema: LilacSchema | undefined) {
    if (schema == null) {
      return {sourceFields: null, enrichedFields: null};
    }
    const petalFields = petals(schema).filter(
      field => ['string_span', 'embedding'].indexOf(field.dtype!) === -1
    );
    const sourceFields = petalFields.filter(f => !isSignalField(f, schema));
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
</script>

<ComposedModal {open} on:submit={submit} on:close={() => (open = false)}>
  <ModalHeader title="Download data" />
  <ModalBody hasForm>
    <section>
      <h4>Select source fields</h4>
      {#if sourceFields == null}
        <SkeletonText />
      {:else}
        <DownloadFieldList fields={sourceFields} bind:checkedFields={checkedSourceFields} />
      {/if}
    </section>
    <section>
      <h4>Select enriched fields</h4>
      {#if enrichedFields == null}
        <SkeletonText />
      {:else}
        <DownloadFieldList fields={enrichedFields} bind:checkedFields={checkedEnrichedFields} />
      {/if}
    </section>
  </ModalBody>
  <ModalFooter primaryButtonText="Save" />
</ComposedModal>

<style lang="postcss">
  h4 {
    @apply mb-2 mt-6;
  }
</style>
