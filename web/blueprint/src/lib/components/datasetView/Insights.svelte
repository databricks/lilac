<script lang="ts">
  import {querySettings} from '$lib/queries/datasetQueries';
  import {childFields, pathIncludes, type LilacField, type LilacSchema, type Path} from '$lilac';
  import ConceptInsight from './ConceptInsight.svelte';

  export let schema: LilacSchema;
  export let namespace: string;
  export let name: string;

  $: conceptFields = childFields(schema).filter(
    s => s.signal?.signal_name == 'concept_score'
  ) as LilacField[];

  $: settings = querySettings(namespace, name);

  $: mediaPaths = ($settings.data?.ui?.media_paths || []).map(p => (Array.isArray(p) ? p : [p]));

  function conceptsForMediaPath(mediaPath: Path) {
    return conceptFields.filter(f => pathIncludes(f.path, mediaPath));
  }
</script>

{#each mediaPaths as mediaPath}
  {@const concepts = conceptsForMediaPath(mediaPath)}
  <div class="flex flex-col gap-y-4 rounded border border-gray-300 p-4">
    <div class="mb-3 text-2xl">{mediaPath}</div>
    {#each concepts as concept}
      <ConceptInsight field={concept} {name} {namespace} />
    {/each}
  </div>
{/each}
