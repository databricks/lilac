<script lang="ts">
  import {querySettings} from '$lib/queries/datasetQueries';
  import {childFields, pathIncludes, type LilacField, type LilacSchema, type Path} from '$lilac';
  import MediaInsight from './MediaInsight.svelte';

  export let schema: LilacSchema;
  export let namespace: string;
  export let datasetName: string;

  $: conceptFields = childFields(schema).filter(
    s => s.signal?.signal_name == 'concept_score'
  ) as LilacField[];

  $: settings = querySettings(namespace, datasetName);
  $: mediaPaths = ($settings.data?.ui?.media_paths || []).map(p => (Array.isArray(p) ? p : [p]));

  function conceptsForMediaPath(mediaPath: Path) {
    return conceptFields.filter(f => pathIncludes(f.path, mediaPath));
  }
</script>

<div class="flex flex-col gap-y-6">
  {#each mediaPaths as mediaPath}
    {@const concepts = conceptsForMediaPath(mediaPath)}
    <MediaInsight {mediaPath} {schema} {namespace} {datasetName} {concepts} />
  {/each}
</div>
