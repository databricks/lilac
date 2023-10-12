<script lang="ts">
  import Page from '$lib/components/Page.svelte';
  import DatasetLoadingPage from '$lib/components/datasetView/DatasetLoadingPage.svelte';
  import {getUrlHashContext} from '$lib/stores/urlHashStore';

  let namespace: string;
  let datasetName: string;
  let loadingTaskId: string;

  const urlHashStore = getUrlHashContext();

  $: {
    if ($urlHashStore.page === 'datasets/loading' && $urlHashStore.identifier != null) {
      [namespace, datasetName, loadingTaskId] = $urlHashStore.identifier.split('/');
    }
  }
</script>

<Page>
  {#if namespace != null && datasetName != null && loadingTaskId != null}
    <DatasetLoadingPage {namespace} {datasetName} {loadingTaskId} />
  {/if}
</Page>
