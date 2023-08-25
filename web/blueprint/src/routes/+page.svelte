<script lang="ts">
  import GettingStarted from '$lib/components/GettingStarted.svelte';
  import HuggingFaceSpaceWelcome from '$lib/components/HuggingFaceSpaceWelcome.svelte';
  import Page from '$lib/components/Page.svelte';
  import {queryAuthInfo} from '$lib/queries/serverQueries';
  import {SkeletonText} from 'carbon-components-svelte';

  const authInfo = queryAuthInfo();
  $: huggingFaceSpaceId = $authInfo.data?.huggingface_space_id;
  $: canCreateDataset = $authInfo.data?.access.create_dataset;
</script>

<Page>
  <div class="flex h-full w-full gap-y-4 overflow-y-scroll p-4">
    {#if $authInfo.isFetching}
      <SkeletonText />
    {:else if huggingFaceSpaceId != null && !canCreateDataset}
      <HuggingFaceSpaceWelcome />
    {:else}
      <GettingStarted />
    {/if}
  </div>
</Page>
