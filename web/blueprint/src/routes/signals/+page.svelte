<script lang="ts">
  import {goto} from '$app/navigation';
  import Page from '$lib/components/Page.svelte';
  import SignalView from '$lib/components/signals/SignalView.svelte';
  import {querySignals} from '$lib/queries/signalQueries';
  import {getUrlHashContext} from '$lib/stores/urlHashStore';
  import {signalLink} from '$lib/utils';
  import {SkeletonText, Tag} from 'carbon-components-svelte';

  let signalName: string | undefined = undefined;

  const urlHashStore = getUrlHashContext();
  $: {
    if ($urlHashStore.page === 'signals' && $urlHashStore.identifier != null) {
      if (signalName != $urlHashStore.identifier) {
        signalName = $urlHashStore.identifier;
      }
    }
  }

  const signals = querySignals();
  $: signalInfo = $signals.data?.find(c => c.name === signalName);

  $: link = signalName != null ? signalLink(signalName) : '';
</script>

<Page>
  <div slot="header-subtext">
    {#if $signals.isFetching}
      <SkeletonText />
    {:else}
      <Tag type="blue">
        <a class="font-semibold text-black" on:click={() => goto(link)} href={link}
          >{signalName}
        </a>
      </Tag>
    {/if}
  </div>

  <div class="flex h-full w-full overflow-x-hidden overflow-y-scroll">
    <div class="lilac-page flex w-full">
      {#if $signals?.isFetching}
        <SkeletonText />
      {:else if $signals?.isError}
        <p>{$signals.error}</p>
      {:else if $signals?.isSuccess && signalInfo}
        {#key signalInfo}
          <SignalView {signalInfo} />
        {/key}
      {/if}
    </div>
  </div>
</Page>
