<script lang="ts">
  import {goto} from '$app/navigation';
  import {useGetDatasetsQuery} from '$lib/store/apiDataset';
  import {Button, InlineNotification, SkeletonText, TreeView} from 'carbon-components-svelte';

  const datasets = useGetDatasetsQuery();

  // Unique namespaces
  $: namespaces = $datasets.isSuccess ? [...new Set($datasets.data.map(row => row.namespace))] : [];

  let expandedIds: string[] = [];
  // Expand all root nodes
  $: {
    if ($datasets.isSuccess && !expandedIds.length) {
      expandedIds = namespaces;
    }
  }

  $: treeviewChildren = namespaces.map(namespace => ({
    text: namespace,
    id: namespace,
    children: $datasets.isSuccess
      ? $datasets.data
          .filter(row => row.namespace === namespace)
          .map(row => ({
            id: `${row.namespace}/${row.dataset_name}`,
            text: row.dataset_name
          }))
          .sort((a, b) => a.text.localeCompare(b.text))
      : []
  }));
</script>

<div class="flex flex-col gap-y-4 p-4">
  <div>
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
      <TreeView
        labelText="Datasets"
        children={treeviewChildren}
        {expandedIds}
        on:select={ev => {
          if (ev.detail.leaf) {
            goto(`/datasets/${ev.detail.id}`);
          }
        }}
      />
    {/if}
  </div>
  <Button on:click={() => goto('/datasets/new')}>Add Dataset</Button>
</div>

<style lang="postcss">
  :global(.bx--tree-leaf-node) {
    @apply cursor-pointer;
  }
</style>
