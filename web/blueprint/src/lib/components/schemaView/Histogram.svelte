<script lang="ts">
  import {formatValue, type LeafValue, type LilacField} from '$lilac';
  import {createEventDispatcher} from 'svelte';

  export let field: LilacField;
  export let counts: Array<[LeafValue, number]>;
  export let bins: Record<string, [number | null, number | null]> | null;
  $: maxCount = Math.max(...counts.map(([_, count]) => count));

  function formatValueOrBin(value: LeafValue): string {
    if (value == null) {
      return formatValue(value);
    }
    // If there are no bins, or there are named bins, we can just format the value.
    if (bins == null || field.bins != null) {
      return formatValue(value);
    }
    // If the field didn't have named bins, we need to format the start and end values.
    const [start, end] = bins[value.toString()];
    if (start == null) {
      return `< ${formatValue(end!)}`;
    } else if (end == null) {
      return `≥ ${formatValue(start)}`;
    } else {
      return `${formatValue(start)} .. ${formatValue(end)}`;
    }
  }
  const dispatch = createEventDispatcher();
</script>

<div class="histogram">
  {#each counts as [value, count]}
    {@const groupName = formatValueOrBin(value)}
    {@const barWidth = `${(count / maxCount) * 100}%`}
    {@const formattedCount = formatValue(count)}

    <button
      class="flex items-center p-0 text-left text-xs text-black hover:bg-gray-200"
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
