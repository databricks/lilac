<script lang="ts">
  import Dataset from '$lib/components/datasetView/Dataset.svelte';
  import {urlHash} from '$lib/stores/urlHashStore';
  import Datasets from './Datasets.svelte';

  let namespace: string | undefined = undefined;
  let datasetName: string | undefined = undefined;

  $: $urlHash.onHashChange('', () => {
    namespace = undefined;
    datasetName = undefined;
  });
  $: $urlHash.onHashChange('/(?<namespace>.+)/(?<datasetName>.+)', ctx => {
    namespace = ctx.namespace;
    datasetName = ctx.datasetName;
  });
</script>

{#if namespace && datasetName}
  <Dataset {namespace} {datasetName} />
{:else}
  <Datasets />
{/if}
