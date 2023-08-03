<script lang="ts">
  import logo_50x50 from '$lib/assets/logo_50x50.png';
  import {queryConcepts} from '$lib/queries/conceptQueries';
  import {deleteDatasetMutation, queryDatasets} from '$lib/queries/datasetQueries';
  import {queryAuthInfo} from '$lib/queries/serverQueries';
  import {getUrlHashContext} from '$lib/stores/urlHashStore';
  import {conceptIdentifier, conceptLink, datasetIdentifier, datasetLink} from '$lib/utils';
  import {getSortedConcepts, getSortedDatasets} from '$lib/view_utils';
  import {Modal} from 'carbon-components-svelte';
  import {InProgress, Settings, SidePanelClose} from 'carbon-icons-svelte';
  import NavigationButton from './NavigationButton.svelte';
  import type {NavigationGroupItem} from './NavigationGroup.svelte';
  import NavigationGroup from './NavigationGroup.svelte';
  import {hoverTooltip} from './common/HoverTooltip';

  const authInfo = queryAuthInfo();
  $: userId = $authInfo.data?.user?.id;
  $: username = $authInfo.data?.user?.given_name;
  $: urlHashContext = getUrlHashContext();

  // Datasets.
  const datasets = queryDatasets();
  $: namespaceDatasets = getSortedDatasets($datasets.data || []);
  let datasetNavGroups: NavigationGroupItem[];
  let deleteDatasetInfo: {namespace: string; name: string} | null = null;

  $: {
    datasetNavGroups = namespaceDatasets.map(({namespace, datasets}) => ({
      group: namespace,
      items: datasets.map(c => ({
        name: c.dataset_name,
        link: datasetLink(c.namespace, c.dataset_name),
        isSelected:
          $urlHashContext.page === 'datasets' &&
          $urlHashContext.identifier === datasetIdentifier(c.namespace, c.dataset_name)
      }))
    }));
  }
  const deleteDataset = deleteDatasetMutation();
  function deleteDatasetClicked() {
    if (deleteDatasetInfo == null) {
      return;
    }
    const {namespace, name} = deleteDatasetInfo;
    $deleteDataset.mutate([namespace, name], {
      onSuccess: () => (deleteDatasetInfo = null)
    });
  }

  // Concepts.
  const concepts = queryConcepts();
  $: namespaceConcepts = getSortedConcepts($concepts.data || [], userId);
  let conceptNavGroups: NavigationGroupItem[];
  $: {
    conceptNavGroups = namespaceConcepts.map(({namespace, concepts}) => ({
      group: namespace === userId ? `${username}'s concepts` : namespace,
      items: concepts.map(c => ({
        name: c.name,
        link: conceptLink(c.namespace, c.name),
        isSelected:
          $urlHashContext.page === 'concepts' &&
          $urlHashContext.identifier === conceptIdentifier(c.namespace, c.name)
      }))
    }));
  }
</script>

<div class="nav-container flex h-full w-56 flex-col items-center overflow-y-scroll">
  <div class="w-full flex-initial flex-grow-0 border-b border-gray-200 py-2 pl-2">
    <div class="flex flex-row justify-between">
      <a class="flex flex-row items-center text-xl normal-case" href="/">
        <img class="logo-img mr-2 rounded opacity-90" src={logo_50x50} alt="Logo" />
        Lilac
      </a>
      <button
        class="mr-1 px-1 opacity-60 hover:bg-gray-200"
        use:hoverTooltip={{text: 'Close sidebar'}}><SidePanelClose /></button
      >
    </div>
  </div>
  <NavigationGroup title="Datasets" groups={datasetNavGroups} isLoading={$concepts.isLoading} />
  <NavigationGroup title="Concepts" groups={conceptNavGroups} isLoading={$datasets.isLoading} />
  <NavigationButton href="/settings" title="Settings" icon={Settings} />
</div>

{#if deleteDatasetInfo}
  <Modal
    danger
    open
    modalHeading="Delete dataset"
    primaryButtonText="Delete"
    primaryButtonIcon={$deleteDataset.isLoading ? InProgress : undefined}
    secondaryButtonText="Cancel"
    on:click:button--secondary={() => (deleteDatasetInfo = null)}
    on:close={() => (deleteDatasetInfo = null)}
    on:submit={() => deleteDatasetClicked()}
  >
    <p class="!text-lg">
      Confirm deleting <code>{deleteDatasetInfo.namespace}/{deleteDatasetInfo.name}</code> ?
    </p>
    <p class="mt-2">This is a permanent action and cannot be undone.</p>
  </Modal>
{/if}

<style lang="postcss">
  .logo-img {
    width: 20px;
    height: 20px;
  }
</style>
