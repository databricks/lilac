<script lang="ts">
  import {goto} from '$app/navigation';
  import {queryDatasets} from '$lib/queries/datasetQueries';
  import {queryAuthInfo} from '$lib/queries/serverQueries';
  import {datasetLink} from '$lib/utils';
  import {Button, SkeletonText} from 'carbon-components-svelte';
  import {Fork, Help, Launch} from 'carbon-icons-svelte';
  import {hoverTooltip} from './common/HoverTooltip';

  const tryDataset = {
    namespace: 'lilac',
    name: 'OpenOrca-100k'
  };
  const tryLink = datasetLink(tryDataset.namespace, tryDataset.name);
  const authInfo = queryAuthInfo();
  $: huggingFaceSpaceId = $authInfo.data?.huggingface_space_id;

  const datasets = queryDatasets();

  $: hasTryDataset = ($datasets.data || []).some(
    d => d.namespace === tryDataset.namespace && d.dataset_name === tryDataset.name
  );
</script>

<div class="mx-32 flex w-full flex-col items-center gap-y-6 px-8">
  <div class="welcome-item mt-8 shadow-md">
    {#if $datasets.isFetching}
      <SkeletonText />
    {:else if hasTryDataset}
      <div
        class="flex cursor-pointer flex-row bg-green-300 px-4 py-4 font-bold"
        on:click={() => goto(tryLink)}
        on:keypress={() => goto(tryLink)}
      >
        <div class="mr-4"><Launch /></div>
        Try {tryDataset.name}
      </div>
      <div class="px-4 py-4">
        <p class="text-sm">
          Browse the pre-loaded {tryDataset.name} dataset in Lilac.
        </p>
        <p class="mt-4 text-sm">
          Check out our <a href="https://lilacml.com/getting_started/quickstart.html"
            >Getting Started</a
          > guide to follow along the steps to import, analyze and enrich your own dataset.
        </p>
      </div>
    {/if}
  </div>
  <div class="welcome-item text-center">
    <h3>Welcome to the Lilac Demo</h3>
    <div class="mt-2 text-gray-700">A HuggingFace space with pre-loaded datasets</div>
    <div class="mt-4 flex flex-row items-center justify-center gap-x-4 text-gray-700">
      <Button
        href={`https://huggingface.co/spaces/${huggingFaceSpaceId}?duplicate=true`}
        icon={Fork}
        kind="primary">Duplicate this Space</Button
      >
      <a
        use:hoverTooltip={{
          text: 'See Lilac documentation on duplicating the HuggingFace demo space.'
        }}
        href="https://lilacml.com/huggingface/huggingface_spaces.html"><Help /></a
      >
    </div>
  </div>
  <div class=" flex flex-col gap-y-8 rounded-lg border border-gray-200 p-9">
    <p class="text-center">
      Check out our <a href="https://lilacml.com/blog/introducing-lilac.html">Announcement Blog</a>
      or visit our website at <a href="https://lilacml.com/">lilacml.com</a> for details.
    </p>
  </div>
</div>

<style lang="postcss">
  .welcome-item {
    @apply w-full;
  }
</style>
