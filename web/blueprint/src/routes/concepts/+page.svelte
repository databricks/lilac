<script lang="ts">
  import {goto} from '$app/navigation';
  import Page from '$lib/components/Page.svelte';
  import Commands, {Command, triggerCommand} from '$lib/components/commands/Commands.svelte';
  import {hoverTooltip} from '$lib/components/common/HoverTooltip';
  import ConceptView from '$lib/components/concepts/ConceptView.svelte';
  import {deleteConceptMutation, queryConcept, queryConcepts} from '$lib/queries/conceptQueries';
  import {queryAuthInfo} from '$lib/queries/serverQueries';
  import {datasetStores} from '$lib/stores/datasetStore';
  import {datasetViewStores} from '$lib/stores/datasetViewStore';
  import {getUrlHashContext} from '$lib/stores/urlHashStore';
  import {conceptLink} from '$lib/utils';
  import {getSortedConcepts} from '$lib/view_utils';
  import {Button, Modal, SkeletonText} from 'carbon-components-svelte';
  import {InProgress, TrashCan, ViewOff} from 'carbon-icons-svelte';
  import {get} from 'svelte/store';

  let namespace: string | undefined;
  let conceptName: string | undefined;

  const urlHashStore = getUrlHashContext();

  $: {
    if ($urlHashStore.page === 'concepts') {
      if ($urlHashStore.identifier == '' || $urlHashStore.identifier == null) {
        namespace = undefined;
        conceptName = undefined;
      } else {
        const [newNamespace, newConceptName] = $urlHashStore.identifier.split('/');
        if (namespace != newNamespace || conceptName != newConceptName) {
          namespace = newNamespace;
          conceptName = newConceptName;
        }
      }
    }
  }

  let deleteConceptInfo: {namespace: string; name: string} | null = null;

  const concepts = queryConcepts();
  const deleteConcept = deleteConceptMutation();

  const authInfo = queryAuthInfo();
  $: userId = $authInfo.data?.user?.id;

  $: namespaceConcepts = getSortedConcepts($concepts.data || [], userId);
  $: username = $authInfo.data?.user?.given_name;

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
      {#each namespaceConcepts as { namespace, concepts }}
        <div
          class="flex flex-row justify-between border-b border-gray-200 bg-neutral-50 p-3 text-sm opacity-80 hover:bg-gray-100"
        >
          <div>
            {#if namespace === userId}
              {username}'s concepts
            {:else}
              {namespace}
            {/if}
          </div>
          <div
            class="opacity-70"
            use:hoverTooltip={{
              text: 'Your concepts are only visible to you when logged in with Google.'
            }}
          >
            {#if namespace === userId}
              <ViewOff />
            {/if}
          </div>
        </div>
        {#each concepts as c}
          {@const canDeleteConcept = c.acls.write}
          <div
            class="flex justify-between border-b border-gray-200 hover:bg-gray-100"
            class:bg-blue-100={c.name === conceptName}
          >
            <a
              href={conceptLink(c.namespace, c.name)}
              class="flex w-full flex-row items-center whitespace-pre px-8 py-2"
            >
              <span> {c.name}</span>
            </a>
            <div
              use:hoverTooltip={{
                text: !canDeleteConcept ? 'User does not have access to delete this concept.' : ''
              }}
              class:opacity-40={!canDeleteConcept}
            >
              <button
                title="Remove concept"
                disabled={!canDeleteConcept}
                class="p-3 opacity-50 hover:text-red-400 hover:opacity-100"
                on:click={() => (deleteConceptInfo = {namespace: c.namespace, name: c.name})}
              >
                <TrashCan size={16} />
              </button>
            </div>
          </div>
        {/each}
      {/each}
    {/if}
  </div>
  <div class="flex h-full w-full">
    <div class="lilac-container">
      <div class="lilac-page flex">
        {#if namespace != null && conceptName != null}
          {#if $concept?.isLoading}
            <SkeletonText />
          {:else if $concept?.isError}
            <p>{$concept.error}</p>
          {:else if $concept?.isSuccess}
            <ConceptView concept={$concept.data} />
          {/if}
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
