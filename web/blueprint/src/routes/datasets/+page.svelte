<script lang="ts">
  import {urlHash} from '$lib/stores/urlHashStore';
  import Datasets from './Datasets.svelte';
  import Dataset from './dataset.svelte';

  let namespace: string | undefined = undefined;
  let datasetName: string | undefined = undefined;

  $: $urlHash.onHashChange(
    '/(?<namespace>.+)/(?<datasetName>.+)',
    ctx => {
      console.log(ctx);
      namespace = ctx.namespace;
      datasetName = ctx.datasetName;
    },
    () => {
      namespace = undefined;
      datasetName = undefined;
    }
  );
  $: console.log(namespace, datasetName);
</script>

{#if namespace && datasetName}
  <Dataset {namespace} {datasetName} />
{:else}
  <Datasets />
{/if}
