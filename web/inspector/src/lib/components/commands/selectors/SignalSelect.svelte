<script lang="ts">
  import {querySignals} from '$lib/queries/signalQueries';
  import type {SignalInfoWithTypedSchema} from '$lilac';
  import {SkeletonText} from 'carbon-components-svelte';

  export let defaultSignal: string | undefined = undefined;
  export let signal: SignalInfoWithTypedSchema | undefined = undefined;

  const signals = querySignals();

  $: {
    if ($signals.isSuccess && !signal) {
      signal = $signals.data?.find(s => s.name === defaultSignal) || $signals.data?.[0];
    }
  }
</script>

{#if $signals.isSuccess}
  <div class="flex flex-col" role="list">
    {#each $signals.data as _signal}
      <button data-active={signal === _signal} on:click={() => (signal = _signal)}>
        {_signal.json_schema.title}
      </button>
    {/each}
  </div>
{:else if $signals.isLoading}
  <SkeletonText lines={3} />
{/if}

<style lang="postcss">
  button {
    @apply w-full px-4 py-2 text-left text-gray-800;
  }

  button:hover {
    @apply bg-gray-200 text-black;
  }

  button[data-active='true'] {
    @apply bg-gray-300 text-black;
  }
</style>
