<script lang="ts">
  import {hoverTooltip} from '$lib/components/common/HoverTooltip';
  import {queryConcept} from '$lib/queries/conceptQueries';
  import {querySelectGroups} from '$lib/queries/datasetQueries';
  import {
    PATH_WILDCARD,
    formatValue,
    type ConceptSignal,
    type LilacField,
    type LilacSchema
  } from '$lilac';
  import {SkeletonText} from 'carbon-components-svelte';
  import Expandable from '../../Expandable.svelte';
  import ConceptInsightItems from './ConceptInsightItems.svelte';

  export let field: LilacField;
  export let schema: LilacSchema;
  export let namespace: string;
  export let datasetName: string;

  const IN_CONCEPT_BIN_NAME = 'In concept';
  const NOT_IN_CONCEPT_BIN_NAME = 'Not in concept';

  let conceptSignal = field.signal as ConceptSignal;

  $: scorePath = [...field.path, PATH_WILDCARD, 'score'];
  $: mediaPath = field.parent!.path;
  $: countQuery = querySelectGroups(namespace, datasetName, {
    leaf_path: scorePath
  });
  $: conceptQuery = queryConcept(conceptSignal.namespace, conceptSignal.concept_name);
  $: conceptDesc = $conceptQuery.data?.metadata?.description;

  $: notInConceptCount =
    $countQuery.data?.counts.find(([binName, _]) => binName === NOT_IN_CONCEPT_BIN_NAME)?.[1] || 0;
  $: inConceptCount =
    $countQuery.data?.counts.find(([binName, _]) => binName === IN_CONCEPT_BIN_NAME)?.[1] || 0;
  $: version = $conceptQuery.data?.version;

  $: conceptFraction = (inConceptCount / (inConceptCount + notInConceptCount)) * 100;
</script>

<Expandable>
  <div slot="above" class="flex w-full items-center">
    <div class="w-full flex-grow">
      <div class="text-lg">
        <span use:hoverTooltip={{text: `version: ${version}`}}
          >{conceptSignal.namespace} / {conceptSignal.concept_name}</span
        >
      </div>
      {#if conceptDesc}
        <div class="text-sm text-gray-500">{conceptDesc}</div>
      {:else}
        <SkeletonText lines={1} width="200px" />
      {/if}
    </div>
    <div class="flex-none">
      {#if $countQuery.isFetching}
        <SkeletonText lines={1} width="200px" />
      {:else}
        <div class="text-lg font-bold">
          {conceptFraction.toFixed(2)}% ({formatValue(inConceptCount)} items)
        </div>
      {/if}
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
