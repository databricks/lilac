<script lang="ts">
  import GettingStartedStep from '$lib/components/GettingStartedStep.svelte';
  import Page from '$lib/components/Page.svelte';
  import {Button} from 'carbon-components-svelte';
</script>

<Page title="">
  <div class="flex w-full flex-col items-center gap-y-6 px-8 pt-20">
    <div class="text-center">
      <h3>Getting started</h3>
      <div class="mt-2 text-gray-700">Import, configure and analyze your dataset</div>
    </div>
    <div class="flex flex-col gap-y-8 rounded-lg border border-gray-200 p-9">
      <GettingStartedStep
        stepNumber={1}
        title="Import your dataset"
        description="Click 'Add dataset' to add a new dataset."
      >
        <div class="mt-4"><Button>+ Add dataset</Button></div>
      </GettingStartedStep>

      <GettingStartedStep
        stepNumber={2}
        title="Configure and index the dataset"
        description="Choose metadata fields to visualize and media fields to index and query."
      />

      <GettingStartedStep
        stepNumber={3}
        title="Enrich your dataset"
        description="Run signals and concepts over the data to produce additional metadata."
      />

      <GettingStartedStep
        stepNumber={4}
        title="Explore your dataset"
        description="Interactively explore your dataset to uncover insights."
      />
    </div>
  </div>
</Page>
