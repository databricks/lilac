<script lang="ts">
  import {parseHash, urlHash} from '$lib/stores/urlHashStore';
  import Dataset from './dataset.svelte';

  let namespace: string | undefined = undefined;
  let datasetName: string | undefined = undefined;

  $: parseHash($urlHash, '/(?<namespace>.+)/(?<datasetName>.+)', ctx => {
    console.log('ctx', ctx.namespace, ctx.datasetName);
    namespace = ctx.namespace;
    datasetName = ctx.datasetName;
  });
</script>

{#if namespace && datasetName}
  <Dataset {namespace} {datasetName} />
{/if}
