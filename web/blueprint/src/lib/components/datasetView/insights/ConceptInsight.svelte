<script lang="ts">
  import {queryConcept} from '$lib/queries/conceptQueries';
  import {querySelectGroups} from '$lib/queries/datasetQueries';
  import {PATH_WILDCARD, type ConceptSignal, type LilacField, type LilacSchema} from '$lilac';
  import {SkeletonText} from 'carbon-components-svelte';
  import Expandable from '../../Expandable.svelte';
  import ConceptInsightItems from './ConceptInsightItems.svelte';

  export let field: LilacField;
  export let schema: LilacSchema;
  export let namespace: string;
  export let datasetName: string;

  let conceptSignal = field.signal as ConceptSignal;

  $: scorePath = [...field.path, PATH_WILDCARD, 'score'];
  $: mediaPath = field.parent!.path;
  $: countQuery = querySelectGroups(namespace, datasetName, {
    leaf_path: scorePath
  });
  $: conceptQuery = queryConcept(conceptSignal.namespace, conceptSignal.concept_name);
  $: conceptDesc = $conceptQuery.data?.metadata?.description;

  $: notInConceptCount = $countQuery.data?.counts[0]?.[1] || 0;
  $: inConceptCount = $countQuery.data?.counts[1]?.[1] || 0;
  $: version = $conceptQuery.data?.version;

  $: conceptFraction = (inConceptCount / (inConceptCount + notInConceptCount)) * 100;
</script>

{#if $countQuery.isFetching || $conceptQuery.isFetching}
  <SkeletonText />
{:else}
  <Expandable>
    <div slot="above" class="flex w-full items-center">
      <div class="w-full flex-grow">
        <div class="text-lg">
          {conceptSignal.namespace} / {conceptSignal.concept_name}
          <span class="text-sm text-gray-500">v{version}</span>
        </div>
        <div class="text-sm text-gray-500">{conceptDesc}</div>
      </div>
      <div class="flex-none">
        <div class="text-lg font-bold">
          {conceptFraction.toFixed(2)}% ({inConceptCount} items)
        </div>
      </div>
    </div>
    <div slot="below">
      {#if $conceptQuery.data}
        <ConceptInsightItems {schema} {namespace} {datasetName} {mediaPath} {scorePath} />
      {:else}
        <SkeletonText />
      {/if}
    </div>
  </Expandable>
{/if}
