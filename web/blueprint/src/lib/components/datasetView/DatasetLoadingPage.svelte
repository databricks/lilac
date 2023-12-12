<script lang="ts">
  import {goto} from '$app/navigation';
  import DatasetSettingsFields from '$lib/components/datasetView/DatasetSettingsFields.svelte';
  import RowItem from '$lib/components/datasetView/RowItem.svelte';
  import {
    queryDatasetSchema,
    querySelectRows,
    querySelectRowsSchema,
    querySettings,
    updateDatasetSettingsMutation
  } from '$lib/queries/datasetQueries';
  import {queryTaskManifest} from '$lib/queries/taskQueries';
  import {
    createDatasetViewStore,
    getSelectRowsSchemaOptions,
    setDatasetViewContext
  } from '$lib/stores/datasetViewStore';
  import {datasetLink} from '$lib/utils';
  import {getHighlightedFields, getMediaFields} from '$lib/view_utils';
  import {L, ROWID, valueAtPath, type DatasetSettings} from '$lilac';
  import {Button, ProgressBar, ToastNotification} from 'carbon-components-svelte';
  import type {ProgressBarProps} from 'carbon-components-svelte/types/ProgressBar/ProgressBar.svelte';
  import {ArrowUpRight} from 'carbon-icons-svelte';

  export let namespace: string;
  export let datasetName: string;
  export let loadingTaskId: string;

  let newSettings: DatasetSettings | undefined = undefined;
  const updateSettings = updateDatasetSettingsMutation();

  $: loadTaskComplete = task?.status == 'completed';

  const datasetViewStore = createDatasetViewStore(namespace, datasetName);
  setDatasetViewContext(datasetViewStore);

  $: settingsQuery = loadTaskComplete ? querySettings(namespace, datasetName) : null;

  $: newSettings =
    $settingsQuery?.isFetching || $settingsQuery?.data == null
      ? null
      : newSettings == null
      ? JSON.parse(JSON.stringify($settingsQuery?.data))
      : newSettings;

  $: schema = loadTaskComplete ? queryDatasetSchema(namespace, datasetName) : null;
  $: selectRowsSchema = loadTaskComplete
    ? querySelectRowsSchema(namespace, datasetName, getSelectRowsSchemaOptions($datasetViewStore))
    : null;

  $: firstRow =
    namespace && datasetName && $schema?.data != null
      ? querySelectRows(
          namespace,
          datasetName,
          {
            columns: [ROWID],
            limit: 1,
            combine_columns: true
          },
          $schema.data
        )
      : null;
  $: firstRowId =
    $firstRow?.data != null
      ? L.value(valueAtPath($firstRow.data.rows[0], [ROWID])!, 'string')
      : null;

  $: highlightedFields = getHighlightedFields($datasetViewStore.query, $selectRowsSchema?.data);

  $: mediaFields =
    newSettings != null && $schema?.data != null ? getMediaFields($schema?.data, newSettings) : [];

  const tasks = queryTaskManifest();

  $: task = loadingTaskId != null && $tasks.data != null ? $tasks.data.tasks[loadingTaskId] : null;
  $: progressValue = task?.step_progress == null ? undefined : task.step_progress;

  const taskToProgressStatus: {[taskStatus: string]: ProgressBarProps['status']} = {
    pending: 'active',
    completed: 'finished',
    error: 'error'
  };

  function saveAndOpen() {
    if (newSettings == null) return;
    $updateSettings.mutate([namespace, datasetName, newSettings], {
      onSuccess: () => {
        goto(datasetLink(namespace, datasetName));
      }
    });
  }
</script>

<div class="w-full overflow-y-scroll">
  <div class="center-panel mx-auto p-8">
    {#if $tasks.isSuccess && task == null}
      <ToastNotification
        hideCloseButton
        kind="warning"
        fullWidth
        lowContrast
        title="Unknown task"
        caption="This could be from a stale link, or a new server instance."
      />
    {/if}
    {#if task}
      <section class="flex flex-col gap-y-2">
        <div class="text-2xl text-gray-700">Step 1: Load dataset "{namespace}/{datasetName}"</div>
        <div class="text-base">
          {#if task.status === 'error'}
            Error loading {namespace}/{datasetName}
          {/if}
        </div>
        {#if task.status != 'error'}
          <div class="mt-2">
            <ProgressBar
              labelText={task.message || ''}
              helperText={task.status != 'completed' ? task.details || undefined : ''}
              value={task.status === 'completed' ? 1.0 : progressValue}
              max={1.0}
              status={taskToProgressStatus[task.status]}
            />
          </div>
          <div class="text-sm text-gray-700">
            {#if $firstRow?.data?.total_num_rows != null}
              {$firstRow?.data?.total_num_rows} rows loaded
            {/if}
          </div>
        {/if}
      </section>
      {#if task.status == 'completed'}
        <div class="my-8">
          <section class="flex flex-col gap-y-4">
            <div class="flex flex-col gap-y-2">
              <div class="text-2xl text-gray-700">Step 2: Choose settings</div>
              <div class="text-sm text-gray-500">
                These settings can be changed from the dataset page at any time.
              </div>
            </div>
            {#if newSettings}
              <DatasetSettingsFields {namespace} {datasetName} bind:newSettings />
            {/if}
          </section>
        </div>

        <div>
          {#if firstRowId != null}
            <div class="text-xl text-gray-700">Preview</div>
            <RowItem rowId={firstRowId} {mediaFields} {highlightedFields} />
          {/if}
        </div>
        <div class="dataset-link mt-8">
          <Button
            disabled={newSettings == null}
            size="xl"
            icon={ArrowUpRight}
            iconDescription={'Open dataset'}
            on:click={() => saveAndOpen()}>Save and open dataset</Button
          >
        </div>
      {:else if task.status === 'error'}
        <ToastNotification
          hideCloseButton
          kind="error"
          fullWidth
          lowContrast
          title="Error loading dataset"
          caption={task.error || undefined}
        />
      {/if}
    {/if}
  </div>
</div>

<style lang="postcss">
  :global(.dataset-link .bx--btn.bx--btn--primary) {
    @apply flex h-16 min-h-0 flex-row items-center justify-between gap-x-4 px-4 py-6 text-base;
  }
  .center-panel {
    width: 52rem;
  }
</style>
