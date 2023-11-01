<script lang="ts">
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {displayPath, shortFieldName} from '$lib/view_utils';
  import {
    deserializePath,
    formatValue,
    getField,
    getLabel,
    type Filter,
    type LilacSchema,
    type Op
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
    exists: 'exists',
    not_exists: 'not exists'
  };

  export let filter: Filter;
  export let hidePath = false;
  export let schema: LilacSchema;

  $: field = getField(schema, typeof filter.path === 'string' ? [filter.path] : filter.path);
  $: label = field != null ? getLabel(field) : null;

  const datasetViewStore = getDatasetViewContext();

  $: formattedValue = formatValue(filter.value || 'false');
  $: path = deserializePath(filter.path);
  $: tooltip =
    filter.op === 'exists'
      ? `has ${displayPath(path)}`
      : filter.op === 'not_exists'
      ? `lacks ${displayPath(path)}`
      : `${displayPath(path)} ${FILTER_SHORTHANDS[filter.op]} ${formattedValue}`;
  $: shortenPath = shortFieldName(path, label);
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
    {:else if filter.op === 'not_exists'}
      lacks <span class="font-mono">{hidePath ? '' : shortenPath}</span>
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
</style>
