<script context="module" lang="ts">
  import {writable} from 'svelte/store';

  export enum Command {
    ComputeSignal = 'computeSignal'
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

  export type Commands = NoCommand | ComputeSignalCommand;

  export function triggerCommand(command: Commands) {
    store.set(command);
  }

  let store = writable<Commands | NoCommand>({});
</script>

<script lang="ts">
  import type {Path} from '$lilac';
  import CommandComputeSignal from './CommandComputeSignal.svelte';

  $: currentCommand = $store;

  function close() {
    store.set({});
  }
</script>

{#if currentCommand.command === Command.ComputeSignal}
  <CommandComputeSignal command={currentCommand} on:close={close} />
{/if}
