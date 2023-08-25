<script lang="ts">
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {shortFieldName} from '$lib/view_utils';
  import {
    deserializePath,
    formatValue,
    serializePath,
    type BinaryFilter,
    type ListFilter,
    type Op,
    type UnaryFilter
  } from '$lilac';
  import {Command, triggerCommand} from '../commands/Commands.svelte';
  import {hoverTooltip} from '../common/HoverTooltip';
  import RemovableTag from '../common/RemovableTag.svelte';

  export const FILTER_SHORTHANDS: Record<Op, string> = {
    equals: '=',
    not_equal: '≠',
    less: '<',
    less_equal: '≤',
    greater: '>',
    greater_equal: '≥',
    in: 'in',
    exists: 'exists'
  };

  export let filter: BinaryFilter | UnaryFilter | ListFilter;
  export let hidePath = false;

  const datasetViewStore = getDatasetViewContext();

  $: formattedValue = formatValue(filter.value || 'false');
  $: path = deserializePath(filter.path);
  $: tooltip =
    filter.op === 'exists'
      ? `has ${serializePath(filter.path)}`
      : `${serializePath(filter.path)} ${FILTER_SHORTHANDS[filter.op]} ${formattedValue}`;
  $: shortenPath = shortFieldName(path);
</script>

<div class="filter-pill items-center" use:hoverTooltip={{text: tooltip}}>
  <RemovableTag
    interactive
    type="magenta"
    on:click={() =>
      triggerCommand({
        command: Command.EditFilter,
        namespace: $datasetViewStore.namespace,
        datasetName: $datasetViewStore.datasetName,
        path: path
      })}
    on:remove={() => datasetViewStore.removeFilter(filter)}
  >
    {#if filter.op === 'exists'}
      has <span class="font-mono">{hidePath ? '' : shortenPath}</span>
    {:else}
      <span class="font-mono">{hidePath ? '' : shortenPath}</span>
      {FILTER_SHORTHANDS[filter.op]}
      {formattedValue}
    {/if}
  </RemovableTag>
</div>

<style lang="postcss">
  :global(.filter-pill .bx--tooltip__label) {
    @apply mr-1 inline-block h-full truncate;
    max-width: 5rem;
  }
  :global(.filter-pill .bx--tooltip__content) {
    @apply flex flex-col items-center;
  }
  :global(.search-container .bx--list-box__menu) {
    max-height: 26rem !important;
  }
</style>
