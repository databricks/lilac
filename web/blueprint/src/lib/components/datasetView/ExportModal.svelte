<script lang="ts">
  import {exportDatasetMutation, querySelectRows} from '$lib/queries/datasetQueries';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {getDisplayPath} from '$lib/view_utils';
  import {
    childFields,
    isLabelField,
    isSignalField,
    isSignalRootField,
    petals,
    type ExportOptions,
    type LilacField,
    type LilacSchema
  } from '$lilac';
  import {
    Checkbox,
    ComposedModal,
    InlineNotification,
    ModalBody,
    ModalFooter,
    ModalHeader,
    NotificationActionButton,
    RadioButton,
    RadioButtonGroup,
    SkeletonPlaceholder,
    SkeletonText,
    TextArea,
    TextInput,
    Toggle
  } from 'carbon-components-svelte';
  import {Download, Tag} from 'carbon-icons-svelte';
  import {createEventDispatcher} from 'svelte';
  import FieldList from './FieldList.svelte';
  export let open = false;
  export let schema: LilacSchema;

  const formats: ExportOptions['format'][] = ['json', 'csv', 'parquet'];
  let selectedFormat: ExportOptions['format'] = 'json';
  let filepath = '';
  let jsonl = false;

  const dispatch = createEventDispatcher();
  const exportDataset = exportDatasetMutation();

  const datasetViewStore = getDatasetViewContext();

  $: ({sourceFields, enrichedFields, labelFields} = getFields(schema));

  let checkedSourceFields: LilacField[] = [];
  let checkedLabeledFields: LilacField[] = [];
  let checkedEnrichedFields: LilacField[] = [];
  let includeOnlyLabels: boolean[] = [];
  let excludeLabels: boolean[] = [];

  $: exportFields = [...checkedSourceFields, ...checkedLabeledFields, ...checkedEnrichedFields];

  $: previewRows =
    exportFields.length > 0
      ? querySelectRows($datasetViewStore.namespace, $datasetViewStore.datasetName, {
          columns: exportFields.map(x => x.path),
          limit: 3,
          combine_columns: false
        })
      : null;
  $: exportDisabled =
    exportFields.length === 0 || filepath.length === 0 || $exportDataset.isLoading;

  function getFields(schema: LilacSchema) {
    const allFields = childFields(schema);
    const petalFields = petals(schema).filter(
      field => ['embedding'].indexOf(field.dtype?.type || '') === -1
    );
    const sourceFields = petalFields.filter(f => !isSignalField(f) && !isLabelField(f));
    const labelFields = allFields.filter(f => f.label != null);
    const enrichedFields = allFields
      .filter(f => isSignalRootField(f))
      .filter(f => !childFields(f).some(f => f.dtype?.type === 'embedding'));
    return {sourceFields, enrichedFields, labelFields};
  }

  async function submit() {
    const namespace = $datasetViewStore.namespace;
    const datasetName = $datasetViewStore.datasetName;
    const options: ExportOptions = {
      format: selectedFormat,
      filepath,
      jsonl,
      columns: exportFields.map(x => x.path),
      include_labels: labelFields.filter((_, i) => includeOnlyLabels[i]).map(x => x.path[0]),
      exclude_labels: labelFields.filter((_, i) => excludeLabels[i]).map(x => x.path[0])
    };
    $exportDataset.mutate([namespace, datasetName, options]);
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

  function downloadUrl(): string {
    return `/api/v1/datasets/serve_dataset?filepath=${$exportDataset.data}`;
  }
</script>

<ComposedModal size="lg" {open} on:submit={submit} on:close={() => (open = false)}>
  <ModalHeader title="Export dataset" />
  <ModalBody hasForm>
    <div class="flex flex-col gap-y-10">
      <section>
        <h2>Step 1: Fields to export</h2>
        <p class="text-red-600" class:invisible={exportFields.length > 0}>
          No fields selected. Please select at least one field to export.
        </p>
        <div class="flex flex-wrap gap-x-12">
          <section>
            <h4>Source fields</h4>
            <FieldList fields={sourceFields} bind:checkedFields={checkedSourceFields} />
          </section>
          {#if labelFields.length > 0}
            <section>
              <h4>Labels</h4>
              <FieldList fields={labelFields} bind:checkedFields={checkedLabeledFields} />
            </section>
          {/if}
          {#if enrichedFields.length > 0}
            <section>
              <h4>Enriched fields</h4>
              <FieldList fields={enrichedFields} bind:checkedFields={checkedEnrichedFields} />
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
                <th><Tag class="inline" /> Label</th>
                <th>Include only</th>
                <th>Exclude</th>
              </tr>
            </thead>
            <tbody>
              {#each labelFields as label, i}
                <tr>
                  <td>{getDisplayPath(label.path)}</td>
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
      <section>
        <h2>Step {labelFields.length > 0 ? 3 : 2}: Export format</h2>
        <div>
          <RadioButtonGroup bind:selected={selectedFormat}>
            {#each formats as format}
              <RadioButton labelText={format} value={format} />
            {/each}
          </RadioButtonGroup>
        </div>
        <div class="mt-4 max-w-lg pt-2">
          <TextInput
            labelText="Output filepath"
            bind:value={filepath}
            invalid={filepath.length === 0}
            invalidText="The file path is required"
            placeholder="Enter a file path for the exported dataset"
          />
        </div>
        {#if selectedFormat === 'json'}
          <div class="mt-4 border-t border-gray-300 pt-2">
            <Toggle bind:toggled={jsonl} labelText="JSONL" />
          </div>
        {/if}
        {#if $exportDataset.isError}
          <InlineNotification
            kind="error"
            title="Error"
            subtitle={$exportDataset.error.body.detail}
            hideCloseButton
          />
        {:else if $exportDataset.isLoading}
          <SkeletonPlaceholder />
        {:else if $exportDataset.data}
          <div class="export-success">
            <InlineNotification kind="success" lowContrast hideCloseButton>
              <div slot="title" class="inline">
                Dataset exported to <a href={downloadUrl()}>{$exportDataset.data}</a>
              </div>
              <svelte:fragment slot="actions">
                <div class="my-auto">
                  <NotificationActionButton on:click={() => window.open(downloadUrl(), '_blank')}>
                    Download <span class="ml-2"><Download /></span>
                  </NotificationActionButton>
                </div>
              </svelte:fragment>
            </InlineNotification>
          </div>
        {/if}
      </section>
      <section>
        <h2>Step {labelFields.length > 0 ? 4 : 3}: JSON preview</h2>
        {#if exportFields.length === 0}
          <p class="text-gray-600">
            No fields selected. Please select at least one field to preview in JSON.
          </p>
        {/if}
        <div class="preview">
          {#if $previewRows && $previewRows.isFetching}
            <SkeletonText paragraph />
          {:else if previewRows && $previewRows}
            <InlineNotification
              hideCloseButton
              kind="info"
              lowContrast
              title={`The preview below is not identical to the exported file which depends on ` +
                `the format selected above.`}
            />
            <TextArea
              value={JSON.stringify($previewRows.data, null, 2)}
              readonly
              rows={20}
              placeholder="3 rows of data for previewing the response"
              class="mb-2 font-mono"
            />
          {/if}
        </div>
      </section>
    </div>
  </ModalBody>
  <ModalFooter
    primaryButtonText="Export dataset"
    primaryButtonDisabled={exportDisabled}
    secondaryButtonText="Cancel"
    on:click:button--secondary={close}
  />
</ComposedModal>

<style lang="postcss">
  :global(.export-success .bx--inline-notification__text-wrapper) {
    @apply w-full;
  }
  h2 {
    @apply mb-2 border-b border-gray-300 pb-2;
  }
  h4 {
    @apply mb-2 mt-2;
  }
  .preview {
    height: 26rem;
  }
  table th {
    @apply pr-5 text-left text-base;
  }
  table td {
    @apply pr-3 align-middle;
  }
</style>
