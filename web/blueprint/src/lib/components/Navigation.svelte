<script lang="ts">
  import {goto} from '$app/navigation';
  import logo_50x50 from '$lib/assets/logo_50x50.png';
  import {queryConcepts} from '$lib/queries/conceptQueries';
  import {queryDatasets} from '$lib/queries/datasetQueries';
  import {queryAuthInfo} from '$lib/queries/serverQueries';
  import {querySignals} from '$lib/queries/signalQueries';
  import {getNavigationContext} from '$lib/stores/navigationStore';
  import {getUrlHashContext} from '$lib/stores/urlHashStore';
  import {conceptLink, signalLink} from '$lib/utils';
  import {getTaggedConcepts, getTaggedDatasets} from '$lib/view_utils';
  import {AddAlt, Settings, SidePanelClose} from 'carbon-icons-svelte';
  import NavigationGroup from './NavigationGroup.svelte';
  import {Command, triggerCommand} from './commands/Commands.svelte';
  import {hoverTooltip} from './common/HoverTooltip';

  const authInfo = queryAuthInfo();
  $: userId = $authInfo.data?.user?.id;
  $: username = $authInfo.data?.user?.given_name;
  $: canCreateDataset = $authInfo.data?.access.create_dataset;

  const urlHashContext = getUrlHashContext();
  const navStore = getNavigationContext();

  // Datasets.
  const datasets = queryDatasets();
  let selectedDataset: {namespace: string; datasetName: string} | null = null;
  $: {
    if ($urlHashContext.page === 'datasets' && $urlHashContext.identifier != null) {
      const [namespace, datasetName] = $urlHashContext.identifier.split('/');
      selectedDataset = {namespace, datasetName};
    } else {
      selectedDataset = null;
    }
  }
  $: taggedDatasets = getTaggedDatasets(selectedDataset, $datasets.data || []);

  // Concepts.
  const concepts = queryConcepts();
  let selectedConcept: {namespace: string; name: string} | null = null;
  $: {
    if ($urlHashContext.page === 'concepts' && $urlHashContext.identifier != null) {
      const [namespace, name] = $urlHashContext.identifier.split('/');
      selectedConcept = {namespace, name};
    } else {
      selectedConcept = null;
    }
  }

  $: taggedConcepts = getTaggedConcepts(selectedConcept, $concepts.data || [], userId, username);

  // Signals.
  const signals = querySignals();
  const SIGNAL_EXCLUDE_LIST = [
    'concept_labels',
    'concept_score',
    // Near dup is disabled until we have multi-inputs.
    'near_dup'
  ];

  $: sortedSignals = $signals.data
    ?.filter(s => !SIGNAL_EXCLUDE_LIST.includes(s.name))
    .sort((a, b) => a.name.localeCompare(b.name));

  $: signalNavGroups = [
    {
      // Display no tag for signals.
      tag: '',
      groups: [
        {
          group: 'lilac',
          items: (sortedSignals || []).map(s => ({
            name: s.name,
            link: signalLink(s.name),
            isSelected: $urlHashContext.page === 'signals' && $urlHashContext.identifier === s.name
          }))
        }
      ]
    }
  ];

  // Settings.
  $: settingsSelected = $urlHashContext.page === 'settings';
</script>

<div class="nav-container flex h-full w-56 flex-col items-center overflow-y-scroll pb-2">
  <div class="w-full border-b border-gray-200">
    <div class="header flex flex-row items-center justify-between px-1 pl-4">
      <a class="flex flex-row items-center text-xl normal-case" href="/">
        <img class="logo-img mr-2 rounded opacity-90" src={logo_50x50} alt="Logo" />
        Lilac
      </a>
      <button
        class="mr-1 opacity-60 hover:bg-gray-200"
        use:hoverTooltip={{text: 'Close sidebar'}}
        on:click={() => ($navStore.open = false)}><SidePanelClose /></button
      >
    </div>
  </div>
  <NavigationGroup title="Datasets" tagGroups={taggedDatasets} isFetching={$datasets.isFetching}>
    <div slot="add" class="w-full">
      {#if canCreateDataset}
        <button
          class="mr-1 flex w-full flex-row px-1 py-1 text-black hover:bg-gray-200"
          on:click={() => goto('/datasets/new')}><AddAlt class="mr-1" />Add dataset</button
        >
      {/if}
    </div>
  </NavigationGroup>
  <NavigationGroup title="Concepts" tagGroups={taggedConcepts} isFetching={$concepts.isFetching}>
    <div slot="add" class="w-full">
      <button
        class="mr-1 flex w-full flex-row px-1 py-1 text-black hover:bg-gray-200"
        on:click={() =>
          triggerCommand({
            command: Command.CreateConcept,
            onCreate: e => goto(conceptLink(e.detail.namespace, e.detail.name))
          })}><AddAlt class="mr-1" />Add concept</button
      >
    </div>
  </NavigationGroup>
  <NavigationGroup title="Signals" tagGroups={signalNavGroups} isFetching={$signals.isFetching} />
  <div class="w-full px-1">
    <button
      class={`w-full px-4 py-2 text-left  ${!settingsSelected ? 'hover:bg-gray-100' : ''}`}
      class:bg-neutral-200={settingsSelected}
      on:click={() => goto('/settings')}
    >
      <div class="flex items-center justify-between">
        <div class="text-sm font-medium">Settings</div>
        <div><Settings /></div>
      </div>
    </button>
  </div>
</div>

<style lang="postcss">
  .logo-img {
    width: 20px;
    height: 20px;
  }
</style>
