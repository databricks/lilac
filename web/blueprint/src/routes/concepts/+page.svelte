<script lang="ts">
  import {goto} from '$app/navigation';
  import Page from '$lib/components/Page.svelte';
  import {hoverTooltip} from '$lib/components/common/HoverTooltip';
  import ConceptView from '$lib/components/concepts/ConceptView.svelte';
  import {deleteConceptMutation, queryConcept, queryConcepts} from '$lib/queries/conceptQueries';
  import {datasetStores} from '$lib/stores/datasetStore';
  import {datasetViewStores} from '$lib/stores/datasetViewStore';
  import {getUrlHashContext} from '$lib/stores/urlHashStore';
  import {conceptIdentifier, conceptLink} from '$lib/utils';
  import {Modal, SkeletonText, Tag} from 'carbon-components-svelte';
  import {InProgress, TrashCan} from 'carbon-icons-svelte';
  import {get} from 'svelte/store';

  let namespace: string;
  let conceptName: string;

  const urlHashStore = getUrlHashContext();

  $: {
    if ($urlHashStore.page === 'concepts' && $urlHashStore.identifier != null) {
      const [newNamespace, newConceptName] = $urlHashStore.identifier.split('/');
      if (namespace != newNamespace || conceptName != newConceptName) {
        namespace = newNamespace;
        conceptName = newConceptName;
      }
    }
  }

  let deleteConceptInfo: {namespace: string; name: string} | null = null;

  const concepts = queryConcepts();
  const deleteConcept = deleteConceptMutation();

  $: concept = namespace && conceptName ? queryConcept(namespace, conceptName) : undefined;
  $: conceptInfo = $concepts.data?.find(c => c.namespace === namespace && c.name === conceptName);
  $: canDeleteConcept = conceptInfo?.acls.write;

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
        goto('/');
      }
    });
  }

  $: link = conceptLink(namespace, conceptName);
</script>

<Page>
  <div slot="header-subtext">
    <Tag type="green">
      <a class="font-semibold text-black" on:click={() => goto(link)} href={link}
        >{conceptIdentifier(namespace, conceptName)}
      </a>
    </Tag>
  </div>
  <div slot="header-right">
    <div
      use:hoverTooltip={{
        text: !canDeleteConcept ? 'User does not have access to delete this concept.' : ''
      }}
      class:opacity-40={!canDeleteConcept}
    >
      <button
        title="Remove concept"
        disabled={!canDeleteConcept}
        class="p-3 hover:text-red-400 hover:opacity-100"
        on:click={() => (deleteConceptInfo = {namespace: namespace, name: conceptName})}
      >
        <TrashCan size={16} />
      </button>
    </div>
  </div>

  <div class="flex h-full w-full overflow-x-hidden overflow-y-scroll">
    <div class="lilac-page flex w-full">
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
