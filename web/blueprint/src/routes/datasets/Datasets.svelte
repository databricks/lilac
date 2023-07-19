<script lang="ts">
  import {goto} from '$app/navigation';
  import Page from '$lib/components/Page.svelte';
  import {hoverTooltip} from '$lib/components/common/HoverTooltip';
  import {deleteDatasetMutation, queryDatasets} from '$lib/queries/datasetQueries';
  import {queryUserAcls} from '$lib/queries/serverQueries';
  import {datasetLink} from '$lib/utils';
  import {Button, InlineNotification, Modal, SkeletonText} from 'carbon-components-svelte';
  import {InProgress, TrashCan} from 'carbon-icons-svelte';

  const datasets = queryDatasets();
  const deleteDataset = deleteDatasetMutation();
  const userAcls = queryUserAcls();
  $: canDeleteDataset = $userAcls.data?.dataset.delete_dataset;
  $: canCreateDataset = $userAcls.data?.create_dataset;

  let deleteDatasetInfo: {namespace: string; name: string} | null = null;

  function deleteDatasetClicked() {
    if (deleteDatasetInfo == null) {
      return;
    }
    const {namespace, name} = deleteDatasetInfo;
    $deleteDataset.mutate([namespace, name], {
      onSuccess: () => (deleteDatasetInfo = null)
    });
  }
</script>

<Page title={'Datasets'}>
  <div slot="header-right">
    <Button size="small" disabled={!canCreateDataset} on:click={() => goto('/datasets/new')}
      >Add Dataset</Button
    >
  </div>
  <div class="flex flex-col gap-y-4 p-4">
    <div class="flex flex-wrap gap-x-4 gap-y-4">
      {#if $datasets.isLoading}
        <SkeletonText paragraph lines={3} width={'30%'} />
      {:else if $datasets.isError}
        <InlineNotification
          kind="error"
          title="Error loading datasets"
          lowContrast
          subtitle={$datasets.error.message}
        />
      {:else if $datasets.isSuccess}
        {#each $datasets.data as dataset}
          <button
            class="w-80 cursor-pointer rounded-md border border-gray-200 px-3 py-4 text-left hover:border-gray-400"
            on:click={() => goto(datasetLink(dataset.namespace, dataset.dataset_name))}
          >
            <div class="truncate text-xl">{dataset.namespace} / {dataset.dataset_name}</div>
            {#if dataset.description}
              <div class="my-4">{dataset.description}</div>
            {/if}
            <div class="mt-4 flex gap-x-2">
              <Button
                kind="tertiary"
                on:click={() => goto(datasetLink(dataset.namespace, dataset.dataset_name))}
                >Open</Button
              >
              <div
                use:hoverTooltip={{
                  text: !canDeleteDataset ? 'User does not have access to delete this dataset.' : ''
                }}
                class:opacity-40={!canDeleteDataset}
              >
                <button
                  title="Delete dataset"
                  disabled={!canDeleteDataset}
                  class:hover:border-red-400={canDeleteDataset}
                  class:hover:text-red-400={canDeleteDataset}
                  class="h-full w-full rounded border border-gray-300 p-2"
                  on:click|stopPropagation={() =>
                    (deleteDatasetInfo = {
                      namespace: dataset.namespace,
                      name: dataset.dataset_name
                    })}
                >
                  <TrashCan size={16} />
                </button>
              </div>
            </div>
          </button>
        {/each}
      {/if}
    </div>
  </div>

  {#if deleteDatasetInfo}
    <Modal
      danger
      open
      modalHeading="Delete dataset"
      primaryButtonText="Delete"
      primaryButtonIcon={$deleteDataset.isLoading ? InProgress : undefined}
      secondaryButtonText="Cancel"
      on:click:button--secondary={() => (deleteDatasetInfo = null)}
      on:close={() => (deleteDatasetInfo = null)}
      on:submit={() => deleteDatasetClicked()}
    >
      <p class="!text-lg">
        Confirm deleting <code>{deleteDatasetInfo.namespace}/{deleteDatasetInfo.name}</code> ?
      </p>
      <p class="mt-2">This is a permanent action and cannot be undone.</p>
    </Modal>
  {/if}
</Page>
