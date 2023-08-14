<script lang="ts">
  import {goto} from '$app/navigation';
  import GettingStartedStep from '$lib/components/GettingStartedStep.svelte';
  import {queryAuthInfo} from '$lib/queries/serverQueries';
  import {Button} from 'carbon-components-svelte';

  const authInfo = queryAuthInfo();
  $: canCreateDataset = $authInfo.data?.access.create_dataset;
</script>

<div class="flex w-full flex-col items-center gap-y-6 px-8 pt-20">
  <div class="text-center">
    <h3>Getting started</h3>
    <div class="mt-2 text-gray-700">Import, analyze and enrich your dataset</div>
  </div>
  <div class="flex flex-col gap-y-8 rounded-lg border border-gray-200 p-9">
    <GettingStartedStep
      stepNumber={1}
      title="Import your dataset"
      description="Click 'Add dataset' to add a new dataset."
    >
      <div class="mt-4">
        <Button disabled={!canCreateDataset} size="small" on:click={() => goto('/datasets/new')}
          >+ Add dataset</Button
        >
      </div>
      {#if !canCreateDataset}
        <div class="flex flex-col border border-neutral-100 bg-red-100 p-2">
          <span class="mb-2">You do not have authorization to create a dataset.</span>
          <span>
            For HuggingFace spaces, fork this space and set <span class="font-mono"
              >LILAC_AUTH_ENABLED</span
            > environment flag to 'false' from settings.
          </span>
        </div>
      {/if}
    </GettingStartedStep>

    <GettingStartedStep
      stepNumber={2}
      title="Configure and index the dataset"
      description="Choose metadata fields to visualize and media fields to index and query."
    />

    <GettingStartedStep
      stepNumber={3}
      title="Enrich and explore your dataset"
      description="Run signals and concepts over the data to produce additional metadata."
    />

    <GettingStartedStep
      stepNumber={4}
      title="Download the new data"
      description="Click the Download button in the top-right corner to get the annotated dataset."
    />
  </div>
</div>
