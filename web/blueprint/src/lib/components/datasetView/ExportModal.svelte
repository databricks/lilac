<script lang="ts">
  import {exportDatasetMutation, querySelectRows} from '$lib/queries/datasetQueries';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {getDisplayPath} from '$lib/view_utils';
  import {
    DELETED_LABEL_KEY,
    childFields,
    isClusterField,
    isEmbeddingField,
    isLabelField,
    isLabelRootField,
    isMapField,
    isSignalField,
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

  $: ({sourceFields, signalFields: signalFields, labelFields, mapFields} = getFields(schema));

  let checkedSourceFields: LilacField[] | undefined = undefined;
  let checkedLabeledFields: LilacField[] = [];
  let checkedSignalFields: LilacField[] = [];
  let checkedMapFields: LilacField[] = [];
  let includeOnlyLabels: boolean[] = [];
  let excludeLabels: boolean[] = [];
  let includeSignals = false;

  function includeSignalsChecked(e: Event) {
    includeSignals = (e.target as HTMLInputElement).checked;
    if (includeSignals) {
      checkedSignalFields = signalFields;
    } else {
      checkedSignalFields = [];
    }
  }
  function signalCheckboxClicked() {
    if (checkedSignalFields.length > 0) {
      includeSignals = true;
    }
  }

  // Default the checked source fields to all of them.
  $: {
    if (sourceFields != null && checkedSourceFields == null) {
      checkedSourceFields = sourceFields;
    }
  }

  $: exportFields = [
    ...(checkedSourceFields || []),
    ...checkedLabeledFields,
    ...checkedSignalFields,
    ...checkedMapFields
  ];

  $: console.log('export fields:', exportFields);

  $: previewRows =
    exportFields.length > 0 && open
      ? querySelectRows($datasetViewStore.namespace, $datasetViewStore.datasetName, {
          columns: exportFields.map(x => x.path),
          limit: 3,
          combine_columns: true,
          exclude_signals: !includeSignals
        })
      : null;
  $: exportDisabled =
    exportFields.length === 0 || filepath.length === 0 || $exportDataset.isLoading;

  function getFields(schema: LilacSchema) {
    const allFields = childFields(schema);
    const petalFields = petals(schema).filter(f => !isEmbeddingField(f));

    const labelFields = allFields.filter(f => isLabelRootField(f));
    const signalFields = allFields
      .filter(f => isSignalField(f))
      .filter(f => !childFields(f).some(f => f.dtype?.type === 'embedding'));
    const mapFields = allFields.filter(f => isMapField(f) || isClusterField(f));

    const sourceFields = petalFields.filter(
      f =>
        !labelFields.includes(f) &&
        !signalFields.includes(f) &&
        !mapFields.includes(f) &&
        // Labels are special in that we only show the root of the label field so the children do
        // not show up in the labelFields.
        !isLabelField(f)
    );
    return {sourceFields, signalFields, labelFields, mapFields};
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
      exclude_labels: labelFields.filter((_, i) => excludeLabels[i]).map(x => x.path[0]),
      include_signals: includeSignals
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

  $: {
    if (excludeLabels.length === 0) {
      excludeLabels = labelFields.map(f => f.label === DELETED_LABEL_KEY);
    }
  }

  function downloadUrl(): string {
    return `/api/v1/datasets/serve_dataset?filepath=${$exportDataset.data}`;
  }
</script>

<ComposedModal size="lg" {open} on:submit={submit} on:close={close}>
  <ModalHeader title="Export dataset" />
  <ModalBody hasForm>
    <div class="flex flex-col gap-y-10">
      <section>
        <h2>Step 1: Fields to export</h2>
        <p class="text-red-600" class:invisible={exportFields.length > 0}>
          No fields selected. Please select at least one field to export.
        </p>
        <div class="flex flex-row gap-x-8">
          <section>
            <h4>Source fields</h4>
            {#if checkedSourceFields != null}
              <FieldList fields={sourceFields} bind:checkedFields={checkedSourceFields} />
            {/if}
          </section>
          {#if labelFields.length > 0}
            <section>
              <h4>Labels</h4>
              <FieldList fields={labelFields} bind:checkedFields={checkedLabeledFields} />
            </section>
          {/if}
          {#if signalFields.length > 0}
            <section>
              <div class="flex flex-row items-center">
                <div class="w-8">
                  <Checkbox
                    hideLabel
                    checked={includeSignals}
                    on:change={e => includeSignalsChecked(e)}
                  />
                </div>
                <h4>Signal fields</h4>
              </div>
              <FieldList
                fields={signalFields}
                bind:checkedFields={checkedSignalFields}
                on:change={() => signalCheckboxClicked()}
              />
            </section>
          {/if}
          {#if mapFields.length > 0}
            <section>
              <h4>Map fields</h4>
              <FieldList fields={mapFields} bind:checkedFields={checkedMapFields} />
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
          <SkeletonText lines={5} class="mt-4" />
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
