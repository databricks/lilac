<script lang="ts">
  import type {LeafValue, LilacField} from '$lilac';
  import {createEventDispatcher} from 'svelte';

  export let field: LilacField;
  export let counts: Array<[LeafValue, number]>;
  export let bins: Record<string, [number | null, number | null]> | null;
  $: maxCount = Math.max(...counts.map(([_, count]) => count));

  function formatValue(value: LeafValue): string {
    if (value == null) {
      return 'N/A';
    }
    // If there are no bins, or there are named bins, we can just format the value.
    if (bins == null || field.bins != null) {
      return value.toString();
    }
    // If the field didn't have named bins, we need to format the start and end values.
    const [start, end] = bins[value.toString()];
    if (start == null) {
      return `< ${formatNumber(end!)}`;
    } else if (end == null) {
      return `≥ ${formatNumber(start)}`;
    } else {
      return `${formatNumber(start)} .. ${formatNumber(end)}`;
    }
  }

  function formatNumber(count: number): string {
    return count.toLocaleString();
  }
  const dispatch = createEventDispatcher();
</script>

<div class="histogram">
  {#each counts as [value, count]}
    {@const groupName = formatValue(value)}
    {@const barWidth = `${(count / maxCount) * 100}%`}
    {@const formattedCount = formatNumber(count)}

    <button
      class="flex items-center text-left text-xs text-black hover:bg-gray-200"
      on:click={() => dispatch('row-click', {value})}
    >
      <div title={groupName} class="w-48 flex-none truncate px-2">{groupName}</div>
      <div class="w-36 border-l border-gray-300 pl-2">
        <div
          title={formattedCount}
          style:width={barWidth}
          class="histogram-bar my-px bg-indigo-200 pl-2 text-xs leading-5"
        >
          {formattedCount}
        </div>
      </div>
    </button>
  {/each}
</div>
