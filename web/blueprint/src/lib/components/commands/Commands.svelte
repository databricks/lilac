<script context="module" lang="ts">
  import {writable} from 'svelte/store';

  export enum Command {
    ComputeSignal = 'computeSignal',
    PreviewConcept = 'previewConcept',
    EditPreviewConcept = 'editPreviewConcept',
    EditFilter = 'editFilter',
    CreateConcept = 'createConcept',
    ComputeEmbedding = 'computeEmbedding'
  }

  type NoCommand = {
    command?: undefined;
  };

  type SignalCommandBase = {
    /** The dataset namespace */
    namespace: string;
    /** The dataset name */
    datasetName: string;
    /** The path to the field to select by default */
    path?: Path;
    /** The name of the signal to show by default */
    signalName?: string;
  };

  export type ComputeSignalCommand = SignalCommandBase & {
    command: Command.ComputeSignal;
  };

  export type PreviewConceptCommand = SignalCommandBase & {
    command: Command.PreviewConcept;
  };

  export type EditPreviewConceptCommand = SignalCommandBase & {
    command: Command.EditPreviewConcept;
    /** The value of the signal to edit */
    value: Signal;
    /** The alias of the signal to edit */
    alias: string;
  };

  export type ComputeEmbeddingCommand = SignalCommandBase & {
    command: Command.ComputeEmbedding;
  };

  export type EditFilterCommand = {
    command: Command.EditFilter;
    namespace: string;
    datasetName: string;
    path: Path;
  };

  export type CreateConceptCommand = {
    command: Command.CreateConcept;
  };

  export type Commands =
    | NoCommand
    | ComputeSignalCommand
    | PreviewConceptCommand
    | EditPreviewConceptCommand
    | EditFilterCommand
    | CreateConceptCommand
    | ComputeEmbeddingCommand;

  export function triggerCommand(command: Commands) {
    store.set(command);
  }

  let store = writable<Commands | NoCommand>({});
</script>

<script lang="ts">
  import type {Path, Signal} from '$lilac';
  import CommandCreateConcept from './CommandCreateConcept.svelte';
  import CommandFilter from './CommandFilter.svelte';
  import CommandSignals from './CommandSignals.svelte';

  $: currentCommand = $store;

  function close() {
    store.set({});
  }
</script>

{#if currentCommand.command === Command.ComputeSignal || currentCommand.command === Command.ComputeEmbedding || currentCommand.command === Command.PreviewConcept || currentCommand.command === Command.EditPreviewConcept}
  <CommandSignals command={currentCommand} on:close={close} />
{:else if currentCommand.command === Command.EditFilter}
  <CommandFilter command={currentCommand} on:close={close} />
{:else if currentCommand.command === Command.CreateConcept}
  <CommandCreateConcept on:close={close} />
{/if}
