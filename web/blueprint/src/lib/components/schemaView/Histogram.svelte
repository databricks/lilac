<script lang="ts">
  import {formatValue, type LeafValue, type LilacField} from '$lilac';
  import {createEventDispatcher} from 'svelte';

  export let field: LilacField;
  export let counts: Array<[LeafValue, number]>;
  export let bins: Record<string, [number | null, number | null]> | null;
  $: maxCount = Math.max(...counts.filter(val => val[0] != null).map(([_, count]) => count));

  // Sort the counts by the index of their value in the named bins.
  $: binKeys = bins != null ? (Object.keys(bins) as LeafValue[]) : [];
  $: sortedCounts = counts
    .slice()
    .sort(([aValue], [bValue]) => binKeys.indexOf(aValue) - binKeys.indexOf(bValue));

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
      return `[${formatValue(start)} .. ${formatValue(end)})`;
    }
  }
  const dispatch = createEventDispatcher();
</script>

<div class="histogram">
  {#each sortedCounts as [value, count]}
    {@const groupName = formatValueOrBin(value)}
    {@const barWidth = `${Math.min(1, count / maxCount) * 100}%`}
    {@const formattedCount = formatValue(count)}
    {@const backgroundColor = value != null ? 'bg-indigo-200' : 'bg-gray-200'}

    <button
      class="flex items-center p-0 text-left text-xs text-black hover:bg-gray-200"
      on:click={() => dispatch('row-click', {value})}
    >
      <div title={groupName} class="histogram-label histogram-bar w-48 flex-none truncate px-2">
        {groupName}
      </div>
      <div class="w-36 border-l border-gray-300 pl-2">
        <div
          title={formattedCount}
          style:width={barWidth}
          class="histogram-label histogram-bar my-px {backgroundColor} pl-2 text-xs leading-5"
        >
          {formattedCount}
        </div>
      </div>
    </button>
  {/each}
</div>

<style>
  .histogram-label {
    font-family: 'inconsolata variable';
  }
</style>
