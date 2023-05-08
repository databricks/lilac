<script lang="ts">
  import { useGetSignalsQuery } from '$lib/store/apiSignal';
  import {
    StructuredList,
    StructuredListBody,
    StructuredListCell,
    StructuredListHead,
    StructuredListInput,
    StructuredListRow,
    StructuredListSkeleton
  } from 'carbon-components-svelte';
  import CheckmarkFilled from 'carbon-icons-svelte/lib/CheckmarkFilled.svelte';

  export let signalName: string | undefined;
  const signals = useGetSignalsQuery();
</script>

{#if $signals.isSuccess}
  <StructuredList selection required bind:selected={signalName} label="Signal">
    <StructuredListHead>
      <StructuredListRow head>
        <StructuredListCell head>Signal</StructuredListCell>
        <StructuredListCell head>Description</StructuredListCell>
      </StructuredListRow>
    </StructuredListHead>
    <StructuredListBody>
      {#each $signals.data as signal}
        <StructuredListRow label for={signal.name}>
          <StructuredListCell>{signal.name}</StructuredListCell>
          <StructuredListCell>
            {signal.json_schema.description}
          </StructuredListCell>
          <StructuredListInput id={signal.name} value={signal.name} />
          <StructuredListCell>
            <CheckmarkFilled
              class="bx--structured-list-svg"
              aria-label="select an option"
              title="select an option"
            />
          </StructuredListCell>
        </StructuredListRow>
      {/each}
    </StructuredListBody>
  </StructuredList>
{:else if $signals.isLoading}
  <StructuredListSkeleton rows={5} />
{/if}
