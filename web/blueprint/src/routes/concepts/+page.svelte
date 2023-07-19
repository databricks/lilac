<script lang="ts">
  import {goto} from '$app/navigation';
  import Page from '$lib/components/Page.svelte';
  import Commands, {Command, triggerCommand} from '$lib/components/commands/Commands.svelte';
  import {hoverTooltip} from '$lib/components/common/HoverTooltip';
  import ConceptView from '$lib/components/concepts/ConceptView.svelte';
  import {deleteConceptMutation, queryConcept, queryConcepts} from '$lib/queries/conceptQueries';
  import {queryUserAcls} from '$lib/queries/serverQueries';
  import {datasetStores} from '$lib/stores/datasetStore';
  import {datasetViewStores} from '$lib/stores/datasetViewStore';
  import {urlHash} from '$lib/stores/urlHashStore';
  import {conceptLink} from '$lib/utils';
  import {Button, Modal, SkeletonText} from 'carbon-components-svelte';
  import {InProgress, TrashCan} from 'carbon-icons-svelte';
  import AddAlt from 'carbon-icons-svelte/lib/AddAlt.svelte';
  import {get} from 'svelte/store';

  let namespace: string | undefined;
  let conceptName: string | undefined;

  $: $urlHash.onHashChange('', () => {
    namespace = undefined;
    conceptName = undefined;
  });
  $: $urlHash.onHashChange('/(?<namespace>.+)/(?<conceptName>.+)', ctx => {
    namespace = ctx.namespace;
    conceptName = ctx.conceptName;
  });

  let deleteConceptInfo: {namespace: string; name: string} | null = null;

  const concepts = queryConcepts();
  const deleteConcept = deleteConceptMutation();
  const userAcls = queryUserAcls();
  $: canDeleteConcepts = $userAcls.data?.concept.delete_any_concept;

  $: concept = namespace && conceptName ? queryConcept(namespace, conceptName) : undefined;

  function deleteConceptClicked() {
    if (deleteConceptInfo == null) {
      return;
    }
    const {namespace, name} = deleteConceptInfo;
    $deleteConcept.mutate([namespace, name], {
      onSuccess: () => {
        for (const [datasetKey, store] of Object.entries(datasetViewStores)) {
          const selectRowsSchema = get(datasetStores[datasetKey]).selectRowsSchema?.data;
          store.deleteConcept(namespace, name, selectRowsSchema);
        }
        deleteConceptInfo = null;
      }
    });
  }
</script>

<Page title={'Concepts'}>
  <div slot="header-right">
    <Button
      size="small"
      on:click={() =>
        triggerCommand({
          command: Command.CreateConcept,
          onCreate: e => goto(conceptLink(e.detail.namespace, e.detail.name))
        })}>Add Concept</Button
    >
  </div>
  <div class="flex-col border-r border-gray-200">
    {#if $concepts.isLoading}
      <SkeletonText />
    {:else if $concepts.isSuccess}
      {#each $concepts.data as c}
        <div
          class="flex justify-between border-b border-gray-200 hover:bg-gray-100"
          class:bg-blue-100={c.name === conceptName}
        >
          <a
            href={conceptLink(c.namespace, c.name)}
            class="flex w-full flex-row items-center whitespace-pre px-4 py-2"
          >
            <span class="opacity-50">{c.namespace} / </span><span> {c.name}</span>
          </a>
          <div
            use:hoverTooltip={{
              text: !canDeleteConcepts ? 'User does not have access to delete concepts.' : ''
            }}
            class:opacity-40={!canDeleteConcepts}
          >
            <button
              title="Remove concept"
              disabled={!canDeleteConcepts}
              class="p-3 opacity-50 hover:text-red-400 hover:opacity-100"
              on:click={() => (deleteConceptInfo = {namespace: c.namespace, name: c.name})}
            >
              <TrashCan size={16} />
            </button>
          </div>
        </div>
      {/each}

      <button
        on:click={() =>
          triggerCommand({
            command: Command.CreateConcept,
            onCreate: e => goto(conceptLink(e.detail.namespace, e.detail.name))
          })}
        class="mt-4 flex w-full items-center gap-x-1 px-4 py-2 text-left text-sm text-gray-500 hover:text-blue-500"
        ><AddAlt /> Add Concept</button
      >
    {/if}
  </div>
  <div class="flex h-full w-full">
    <div class="lilac-container">
      <div class="lilac-page flex">
        {#if $concept?.isLoading}
          <SkeletonText />
        {:else if $concept?.isError}
          <p>{$concept.error.message}</p>
        {:else if $concept?.isSuccess}
          <ConceptView concept={$concept.data} />
        {/if}
      </div>
    </div>
  </div>

  <Commands />

  {#if deleteConceptInfo}
    <Modal
      danger
      open
      modalHeading="Delete concept"
      primaryButtonText="Delete"
      primaryButtonIcon={$deleteConcept.isLoading ? InProgress : undefined}
      secondaryButtonText="Cancel"
      on:click:button--secondary={() => (deleteConceptInfo = null)}
      on:close={() => (deleteConceptInfo = null)}
      on:submit={() => deleteConceptClicked()}
    >
      <p class="!text-lg">
        Confirm deleting <code>{deleteConceptInfo.namespace}/{deleteConceptInfo.name}</code> ?
      </p>
      <p class="mt-2">This is a permanent action and cannot be undone.</p>
    </Modal>
  {/if}
</Page>
