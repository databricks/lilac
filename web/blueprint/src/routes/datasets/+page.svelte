<script lang="ts">
  import {urlHash} from '$lib/stores/urlHashStore';
  import Dataset from './dataset.svelte';

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
