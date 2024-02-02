<script lang="ts">
  import {queryConcept} from '$lib/queries/conceptQueries';
  import {queryDatasetSchema} from '$lib/queries/datasetQueries';
  import {queryAuthInfo} from '$lib/queries/serverQueries';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {conceptLink} from '$lib/utils';
  import {getSearches} from '$lib/view_utils';
  import {Button, Modal, SkeletonText} from 'carbon-components-svelte';
  import {ArrowUpRight, TagGroup, TagNone} from 'carbon-icons-svelte';
  import ConceptView from '../concepts/ConceptView.svelte';
  import DeleteRowsButton from './DeleteRowsButton.svelte';
  import EditLabel from './EditLabel.svelte';
  import FilterControls from './FilterControls.svelte';
  import GroupByControls from './GroupByControls.svelte';
  import GroupByPanel from './GroupByPanel.svelte';
  import SortControls from './SortControls.svelte';

  export let numRowsInQuery: number | undefined;

  let datasetViewStore = getDatasetViewContext();
  const authInfo = queryAuthInfo();
  $: canLabelAll = $authInfo.data?.access.dataset.label_all || false;

  $: schema = queryDatasetSchema($datasetViewStore.namespace, $datasetViewStore.datasetName);

  let openedConcept: {namespace: string; name: string} | null = null;
  $: concept = openedConcept
    ? queryConcept(openedConcept.namespace, openedConcept.name)
    : undefined;

  $: searches = getSearches($datasetViewStore);

  $: filters = $datasetViewStore.query.filters;
</script>

<div class="relative mx-8 my-2 flex items-center justify-between">
  <div class="flex w-full items-center justify-between gap-x-6 gap-y-2">
    <div class="flex w-full flex-row items-center gap-x-4">
      <div class="flex items-center gap-x-2">
        <EditLabel
          totalNumRows={numRowsInQuery}
          icon={TagGroup}
          disabled={!canLabelAll}
          disabledMessage={!canLabelAll ? 'User does not have access to label all.' : ''}
          labelsQuery={{searches, filters}}
          helperText={'Label all items in the current filter'}
        />
        <EditLabel
          totalNumRows={numRowsInQuery}
          remove
          icon={TagNone}
          disabled={!canLabelAll}
          disabledMessage={!canLabelAll ? 'User does not have access to label all.' : ''}
          labelsQuery={{searches, filters}}
          helperText={'Remove label from all items in the current filter'}
        />
        <DeleteRowsButton
          numRows={numRowsInQuery}
          searches={$datasetViewStore.query.searches}
          filters={$datasetViewStore.query.filters}
        />
      </div>
    </div>
    <div class="flex grow flex-row gap-x-4">
      <FilterControls />
      <GroupByControls />
      <SortControls />
    </div>
  </div>
</div>

{#if $datasetViewStore.groupBy && $schema.data}
  <GroupByPanel schema={$schema.data} groupBy={$datasetViewStore.groupBy} />
{/if}

{#if openedConcept}
  <Modal open modalHeading={''} passiveModal on:close={() => (openedConcept = null)} size="lg">
    {#if $concept?.isLoading}
      <SkeletonText />
    {:else if $concept?.isError}
      <p>{$concept.error.message}</p>
    {:else if $concept?.isSuccess}
      <div class="mb-4 ml-6">
        <Button
          size="small"
          kind="ghost"
          icon={ArrowUpRight}
          href={conceptLink($concept?.data.namespace, $concept.data.concept_name)}
          iconDescription={'Open concept page'}>Go to concept</Button
        >
      </div>

      <ConceptView concept={$concept.data} />
    {/if}
  </Modal>
{/if}
