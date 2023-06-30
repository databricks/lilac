<script lang="ts">
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {
    deserializePath,
    formatValue,
    serializePath,
    type BinaryFilter,
    type BinaryOp,
    type ListFilter,
    type ListOp,
    type UnaryFilter,
    type UnaryOp
  } from '$lilac';
  import {Command, triggerCommand} from '../commands/Commands.svelte';
  import {hoverTooltip} from '../common/HoverTooltip';
  import RemovableTag from '../common/RemovableTag.svelte';

  export const FILTER_SHORTHANDS: Record<BinaryOp | UnaryOp | ListOp, string> = {
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
  $: tooltip = `${serializePath(filter.path)} ${FILTER_SHORTHANDS[filter.op]} ${formattedValue}`;
  $: shortenPath = path.at(-1);
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
    {hidePath ? '' : shortenPath}
    {FILTER_SHORTHANDS[filter.op]}
    {formattedValue}
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
</style>
