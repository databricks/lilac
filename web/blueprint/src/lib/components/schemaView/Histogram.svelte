<script lang="ts">
  import type {LeafValue} from '$lilac';

  export let counts: Array<[LeafValue, number]>;

  $: maxCount = Math.max(...counts.map(([_, count]) => count));
</script>

<div class="histogram my-4">
  {#each counts as [value, count]}
    {@const barWidth = `${(count / maxCount) * 100}%`}
    {@const formattedCount = count.toLocaleString()}

    <div class="flex cursor-pointer items-center text-sm text-black hover:bg-gray-200">
      <div title={value?.toString()} class="w-24 flex-none truncate pl-2">{value}</div>
      <div class="w-24 border-l border-gray-300 pl-2">
        <div
          title={formattedCount}
          style:width={barWidth}
          class="histogram-bar my-px bg-indigo-200 pl-2 text-xs leading-5"
        >
          {formattedCount}
        </div>
      </div>
    </div>
  {/each}
</div>
