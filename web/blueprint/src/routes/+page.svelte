<script lang="ts">
  import GettingStarted from '$lib/components/GettingStarted.svelte';
  import HuggingFaceSpaceWelcome from '$lib/components/HuggingFaceSpaceWelcome.svelte';
  import Page from '$lib/components/Page.svelte';
  import {queryAuthInfo} from '$lib/queries/serverQueries';
  import {SkeletonText} from 'carbon-components-svelte';

  const authInfo = queryAuthInfo();
  $: huggingFaceSpaceId = $authInfo.data?.huggingface_space_id;
</script>

<Page>
  {#if $authInfo.isFetching}
    <SkeletonText />
  {:else if huggingFaceSpaceId != null}
    <HuggingFaceSpaceWelcome />
  {:else}
    <GettingStarted />
  {/if}
</Page>
