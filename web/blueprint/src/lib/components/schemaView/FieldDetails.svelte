<script lang="ts">
  import {queryDatasetStats, querySelectGroups} from '$lib/queries/datasetQueries';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import type {LilacField} from '$lilac';
  import {SkeletonText} from 'carbon-components-svelte';

  export let field: LilacField;

  const store = getDatasetViewContext();

  $: stats = queryDatasetStats($store.namespace, $store.datasetName, {leaf_path: field.path});

  $: groups = querySelectGroups($store.namespace, $store.datasetName, {leaf_path: field.path});
</script>

{#if $stats.isLoading}
  <SkeletonText paragraph width="50%" />
{:else if $stats.error}
  <p>Error: {$stats.error.message}</p>
{:else}
  <pre>{JSON.stringify($stats.data, null, 2)}</pre>
{/if}

{#if $groups.isLoading}
  <SkeletonText paragraph width="50%" />
{:else if $groups.error}
  <p>Error: {$groups.error.message}</p>
{:else}
  <pre>{JSON.stringify($groups.data, null, 2)}</pre>
{/if}
