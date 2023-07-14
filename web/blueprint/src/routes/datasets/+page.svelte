<script lang="ts">
  import Dataset from '$lib/components/datasetView/Dataset.svelte';
  import {urlHash} from '$lib/stores/urlHashStore';

  let namespace: string | undefined = undefined;
  let datasetName: string | undefined = undefined;

  $: $urlHash.onHashChange('/(?<namespace>.+)/(?<datasetName>.+)', ctx => {
    namespace = ctx.namespace;
    datasetName = ctx.datasetName;
  });
</script>

{#if namespace && datasetName}
  <Dataset {namespace} {datasetName} />
{/if}
