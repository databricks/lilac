<script lang="ts">
  import {formatValue, type LeafValue, type LilacField} from '$lilac';
  import {createEventDispatcher} from 'svelte';

  export let field: LilacField;
  export let counts: Array<[LeafValue, number]>;
  export let bins: Array<[string, number | null, number | null]> | null;

  $: maxCount = Math.max(...counts.map(([_, count]) => count));

  function formatBin(bin: [string, number | null, number | null]): string {
    const [binName, start, end] = bin;
    if (field.bins != null) {
      return binName;
    }
    // If the field didn't have named bins, we need to format the start and end values.
    if (start == null) {
      return `< ${formatValue(end)}`;
    } else if (end == null) {
      return `≥ ${formatValue(start)}`;
    } else {
      return `${formatValue(start)} .. ${formatValue(end)}`;
    }
  }
  const dispatch = createEventDispatcher();
</script>

<div class="histogram">
  {#each counts as [value, count], i}
    {@const groupName = bins != null ? formatBin(bins[i]) : value?.toString()}
    {@const barWidth = `${(count / maxCount) * 100}%`}
    {@const formattedCount = formatValue(count)}

    <button
      class="flex items-center text-left text-xs text-black hover:bg-gray-200"
      on:click={() => dispatch('row-click', {value, index: i})}
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
