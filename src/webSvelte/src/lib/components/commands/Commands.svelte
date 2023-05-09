<script context="module" lang="ts">
  import { writable } from 'svelte/store';

  export enum Command {
    ComputeSignal = 'computeSignal',
    PreviewConcept = 'previewConcept'
  }

  type NoCommand = {
    command?: undefined;
  };
  export type ComputeSignalCommand = {
    command: Command.ComputeSignal;
    namespace: string;
    datasetName: string;
    path?: Path;
    signalName?: string;
  };

  export type PreviewConceptCommand = {
    command: Command.PreviewConcept;
    namespace: string;
    datasetName: string;
    path?: Path;
  };

  export type Commands = NoCommand | ComputeSignalCommand | PreviewConceptCommand;

  export function triggerCommand(command: Commands) {
    store.set(command);
  }

  let store = writable<Commands | NoCommand>({});
</script>

<script lang="ts">
  import type { Path } from '$lilac';
  import CommandComputeSignal from './CommandComputeSignal.svelte';
  import CommandPreviewConcept from './CommandPreviewSignal.svelte';

  $: currentCommand = $store;

  function close() {
    store.set({});
  }
</script>

{#if currentCommand.command === Command.ComputeSignal}
  <CommandComputeSignal command={currentCommand} on:close={close} />
{:else if currentCommand.command === Command.PreviewConcept}
  <CommandPreviewConcept command={currentCommand} on:close={close} />
{/if}
