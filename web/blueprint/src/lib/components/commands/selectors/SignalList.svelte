<script lang="ts">
  import {querySignals} from '$lib/queries/signalQueries';
  import type {SignalInfoWithTypedSchema} from '$lilac';
  import CommandSelectList from './CommandSelectList.svelte';

  export let defaultSignal: string | undefined = undefined;
  export let signal: SignalInfoWithTypedSchema | undefined = undefined;

  const signals = querySignals();

  $: shownSignals = $signals.data?.filter(
    s => s.name != 'concept_score' && s.name != 'concept_labels'
  );

  $: {
    if (shownSignals && !signal) {
      signal = shownSignals.find(s => s.name === defaultSignal) || shownSignals[0];
    }
  }
</script>

{#if shownSignals}
  <CommandSelectList
    items={shownSignals.map(signal => ({
      title: signal.json_schema.title || 'Unnamed signal',
      value: signal
    }))}
    item={signal}
    on:select={e => (signal = e.detail)}
  />
{:else if $signals.isLoading}
  <CommandSelectList skeleton />
{/if}
