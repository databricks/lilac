<script context="module" lang="ts">
  import {writable} from 'svelte/store';

  export enum Command {
    ComputeSignal = 'computeSignal',
    PreviewConcept = 'previewConcept',
    EditFilter = 'editFilter'
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
    signalName?: string;
  };

  export type EditFilterCommand = {
    command: Command.EditFilter;
    namespace: string;
    datasetName: string;
    path: Path;
  };

  export type Commands =
    | NoCommand
    | ComputeSignalCommand
    | PreviewConceptCommand
    | EditFilterCommand;

  export function triggerCommand(command: Commands) {
    store.set(command);
  }

  let store = writable<Commands | NoCommand>({});
</script>

<script lang="ts">
  import type {Path} from '$lilac';
  import CommandFilter from './CommandFilter.svelte';
  import CommandSignals from './CommandSignals.svelte';

  $: currentCommand = $store;

  function close() {
    store.set({});
  }
</script>

{#if currentCommand.command === Command.ComputeSignal}
  <CommandSignals command={currentCommand} on:close={close} variant={'compute'} />
{:else if currentCommand.command === Command.PreviewConcept}
  <CommandSignals command={currentCommand} on:close={close} variant={'preview'} />
{:else if currentCommand.command === Command.EditFilter}
  <CommandFilter command={currentCommand} on:close={close} />
{/if}
