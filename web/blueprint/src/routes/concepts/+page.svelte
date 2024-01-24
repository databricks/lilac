<script lang="ts">
  import {goto} from '$app/navigation';
  import Page from '$lib/components/Page.svelte';
  import {hoverTooltip} from '$lib/components/common/HoverTooltip';
  import ConceptSettingsModal from '$lib/components/concepts/ConceptSettingsModal.svelte';
  import ConceptView from '$lib/components/concepts/ConceptView.svelte';
  import {queryConcept, queryConcepts} from '$lib/queries/conceptQueries';
  import {getUrlHashContext} from '$lib/stores/urlHashStore';
  import {conceptIdentifier, conceptLink} from '$lib/utils';
  import {SkeletonText, Tag} from 'carbon-components-svelte';
  import {Settings, Share} from 'carbon-icons-svelte';
  import {fade} from 'svelte/transition';

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

  const concepts = queryConcepts();

  $: concept = namespace && conceptName ? queryConcept(namespace, conceptName) : undefined;
  $: conceptInfo = $concepts.data?.find(c => c.namespace === namespace && c.name === conceptName);
  $: canEditConcept = conceptInfo?.acls.write;

  $: link = conceptLink(namespace, conceptName);

  let settingsOpen = false;
  let showCopyToast = false;
</script>

<Page>
  <div slot="header-subtext">
    <Tag type="green">
      <a class="font-semibold text-black" on:click={() => goto(link)} href={link}
        >{conceptIdentifier(namespace, conceptName)}
      </a>
    </Tag>
  </div>
  <div slot="header-right" class="flex flex-row">
    {#if conceptInfo?.metadata.is_public}
      <div class="relative flex flex-row justify-items-center">
        {#if showCopyToast}
          <div
            out:fade
            class="absolute right-12 z-50 mt-2 rounded border border-neutral-300 bg-neutral-50 px-4 py-1 text-xs"
          >
            Copied!
          </div>
        {/if}
        <button
          class="p-3"
          use:hoverTooltip={{text: 'Copy the URL'}}
          on:click={() =>
            navigator.clipboard.writeText(location.href).then(
              () => {
                showCopyToast = true;
                setTimeout(() => (showCopyToast = false), 2000);
              },
              () => {
                throw Error('Error copying link to clipboard.');
              }
            )}><Share /></button
        >
      </div>
    {/if}
    <div
      use:hoverTooltip={{
        text: !canEditConcept
          ? 'User does not have access to edit this concept.'
          : 'Edit concept settings'
      }}
      class:opacity-40={!canEditConcept}
    >
      <button
        title="Concept settings"
        disabled={!canEditConcept}
        class="p-3"
        on:click={() => (settingsOpen = true)}
      >
        <Settings size={16} />
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

  {#if settingsOpen}
    <ConceptSettingsModal bind:open={settingsOpen} {namespace} {conceptName} />
  {/if}
</Page>
