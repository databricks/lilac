<script lang="ts">
  import {queryConcept} from '$lib/queries/conceptQueries';
  import {querySelectGroups} from '$lib/queries/datasetQueries';
  import {PATH_WILDCARD, type ConceptSignal, type LilacField} from '$lilac';
  import {SkeletonText} from 'carbon-components-svelte';
  import Expandable from '../Expandable.svelte';

  export let field: LilacField;
  export let namespace: string;
  export let name: string;

  let conceptField = field as LilacField<ConceptSignal> &
    Required<Pick<LilacField<ConceptSignal>, 'signal'>>;

  $: countQuery = querySelectGroups(namespace, name, {
    leaf_path: [...conceptField.path, PATH_WILDCARD, 'score']
  });
  $: conceptQuery = queryConcept(conceptField.signal.namespace, conceptField.signal.concept_name);
  $: conceptDesc = $conceptQuery.data?.metadata?.description;

  $: notInConceptCount = $countQuery.data?.counts[0][1];
  $: inConceptCount = $countQuery.data?.counts[1][1];
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
          {conceptField.signal.namespace} / {conceptField.signal.concept_name}
          <span class="text-sm text-gray-500">v{version}</span>
        </div>
        <div class="text-sm text-gray-500">{conceptDesc}</div>
      </div>
      <div class="flex-none">
        <div class="text-xl font-bold">
          {conceptFraction.toFixed(2)}% ({inConceptCount} items)
        </div>
      </div>
    </div>
    <div slot="below">This is below.</div>
  </Expandable>
{/if}
