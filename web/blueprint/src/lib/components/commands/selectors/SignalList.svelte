<script lang="ts">
  import {querySignals} from '$lib/queries/signalQueries';
  import type {SignalInfoWithTypedSchema} from '$lilac';
  import CommandSelectList from './CommandSelectList.svelte';

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
  <CommandSelectList
    items={$signals.data.map(signal => ({
      title: signal.json_schema.title || 'Unnamed signal',
      value: signal
    }))}
    item={signal}
    on:select={e => (signal = e.detail)}
  />
{:else if $signals.isLoading}
  <CommandSelectList skeleton />
{/if}
