<script lang="ts">
  import {querySelectRows} from '$lib/queries/datasetQueries';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {displayPath} from '$lib/view_utils';
  import {
    DatasetsService,
    childFields,
    isLabelField,
    isSignalField,
    isSignalRootField,
    petals,
    type DownloadOptions,
    type LilacField,
    type LilacSchema
  } from '$lilac';
  import {
    Checkbox,
    ComposedModal,
    ModalBody,
    ModalFooter,
    ModalHeader,
    RadioButton,
    RadioButtonGroup,
    SkeletonText,
    TextArea,
    TextInput,
    Toggle
  } from 'carbon-components-svelte';
  import {createEventDispatcher} from 'svelte';
  import DownloadFieldList from './DownloadFieldList.svelte';

  export let open = false;
  export let schema: LilacSchema;

  const formats = ['json in browser', 'json', 'csv', 'parquet'];
  let selectedFormat: 'json in browser' | 'json' | 'csv' | 'parquet' = 'json';
  let filepath = '';
  let jsonl = false;

  const dispatch = createEventDispatcher();

  const datasetViewStore = getDatasetViewContext();

  $: ({sourceFields, enrichedFields, labelFields} = getFields(schema));

  let checkedSourceFields: LilacField[] = [];
  let checkedLabeledFields: LilacField[] = [];
  let checkedEnrichedFields: LilacField[] = [];
  let includeOnlyLabels: boolean[] = [];
  let excludeLabels: boolean[] = [];

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
    if (selectedFormat === 'json in browser') {
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
      return;
    }
    const options: DownloadOptions = {
      format: selectedFormat,
      filepath,
      jsonl,
      columns: downloadFields.map(x => x.path),
      include_labels: labelFields.filter((_, i) => includeOnlyLabels[i]).map(x => x.path[0]),
      exclude_labels: labelFields.filter((_, i) => excludeLabels[i]).map(x => x.path[0])
    };
    await DatasetsService.downloadDataset(namespace, datasetName, options);
  }

  function close() {
    open = false;
    dispatch('close');
  }
  function filterLabelClicked(index: number, include: boolean) {
    if (include) {
      excludeLabels[index] = false;
    } else {
      includeOnlyLabels[index] = false;
    }
  }
</script>

<ComposedModal size="lg" {open} on:submit={submit} on:close={() => (open = false)}>
  <ModalHeader title="Download data" />
  <ModalBody hasForm>
    <div class="flex flex-col gap-y-10">
      <section>
        <h2>Step 1: Fields to download</h2>
        <div class="flex flex-wrap gap-x-12">
          <section>
            <h4>Source</h4>
            <DownloadFieldList fields={sourceFields} bind:checkedFields={checkedSourceFields} />
          </section>
          {#if labelFields.length > 0}
            <section>
              <h4>Labels</h4>
              <DownloadFieldList fields={labelFields} bind:checkedFields={checkedLabeledFields} />
            </section>
          {/if}
          {#if enrichedFields.length > 0}
            <section>
              <h4>Enriched</h4>
              <DownloadFieldList
                fields={enrichedFields}
                bind:checkedFields={checkedEnrichedFields}
              />
            </section>
          {/if}
        </div>
      </section>
      {#if labelFields.length > 0}
        <section>
          <h2>Step 2: Filter by label</h2>
          <table>
            <thead>
              <tr>
                <th>Label</th>
                <th>Include only</th>
                <th>Exclude</th>
              </tr>
            </thead>
            <tbody>
              {#each labelFields as label, i}
                <tr>
                  <td>{displayPath(label.path)}</td>
                  <td
                    ><Checkbox
                      bind:checked={includeOnlyLabels[i]}
                      on:change={() => filterLabelClicked(i, true)}
                    />
                  </td>
                  <td
                    ><Checkbox
                      bind:checked={excludeLabels[i]}
                      on:change={() => filterLabelClicked(i, false)}
                    />
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </section>
      {/if}
      <section class="max-w-lg">
        <h2>Step {labelFields.length > 0 ? 3 : 2}: Download format</h2>
        <div>
          <RadioButtonGroup bind:selected={selectedFormat}>
            {#each formats as format}
              <RadioButton labelText={format} value={format} />
            {/each}
          </RadioButtonGroup>
        </div>
        {#if selectedFormat !== 'json in browser'}
          <div class="mt-4 pt-2">
            <TextInput
              labelText="Output path"
              bind:value={filepath}
              invalid={filepath.length === 0}
              invalidText="The output path is required"
              placeholder="Enter output path"
            />
          </div>
          {#if selectedFormat === 'json'}
            <div class="mt-4 border-t border-gray-300 pt-2">
              <Toggle bind:toggled={jsonl} labelText="JSONL" />
            </div>
          {/if}
        {/if}
      </section>
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
    </div>
  </ModalBody>
  <ModalFooter
    primaryButtonText="Download"
    primaryButtonDisabled={downloadFields.length === 0 || filepath.length === 0}
    secondaryButtonText="Cancel"
    on:click:button--secondary={close}
  />
</ComposedModal>

<style lang="postcss">
  h2 {
    @apply mb-2;
  }
  h4 {
    @apply mb-2 mt-2;
  }
  .preview {
    height: 30rem;
  }
  table th {
    @apply pr-5 text-left text-base;
  }
  table td {
    @apply pr-3 align-middle;
  }
</style>
