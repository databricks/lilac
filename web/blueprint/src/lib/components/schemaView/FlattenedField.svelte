<script lang="ts">
  import {getDatasetContext} from '$lib/stores/datasetStore';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {getSearches, isPreviewSignal} from '$lib/view_utils';

  import {
    PATH_WILDCARD,
    VALUE_KEY,
    childFields,
    isFilterableField,
    isSignalField,
    isSignalRootField,
    isSortableField,
    pathIsEqual,
    serializePath,
    type LilacField,
    type LilacSchema,
    type TextEmbeddingSignal
  } from '$lilac';
  import {Button, Checkbox, OverflowMenu, Tag} from 'carbon-components-svelte';
  import {CaretDown, ChevronDown, Chip, SortAscending, SortDescending} from 'carbon-icons-svelte';
  import {slide} from 'svelte/transition';
  import {Command, triggerCommand} from '../commands/Commands.svelte';
  import {hoverTooltip} from '../common/HoverTooltip';
  import RemovableTag from '../common/RemovableTag.svelte';
  import SchemaFieldMenu from '../contextMenu/SchemaFieldMenu.svelte';
  import EmbeddingBadge from '../datasetView/EmbeddingBadge.svelte';
  import FilterPill from '../datasetView/FilterPill.svelte';
  import SearchPill from '../datasetView/SearchPill.svelte';
  import SignalBadge from '../datasetView/SignalBadge.svelte';
  import FieldDetails from './FieldDetails.svelte';

  export let schema: LilacSchema;
  export let field: LilacField;
  export let sourceField: LilacField | undefined = undefined;
  export let indent = 0;

  $: isSignal = isSignalField(field, schema);
  $: isSourceField = !isSignal;

  const datasetViewStore = getDatasetViewContext();
  const datasetStore = getDatasetContext();

  $: path = field.path;

  let expanded = true;
  $: expandedDetails = $datasetViewStore.expandedColumns[serializePath(path)] || false;

  $: isRepeatedField = path.at(-1) === PATH_WILDCARD ? true : false;
  $: fieldName = isRepeatedField ? path.at(-2) : path.at(-1);

  $: children = childDisplayFields(field);
  $: hasChildren = children.length > 0;

  $: isVisible = $datasetStore.visibleFields?.some(f => pathIsEqual(f.path, path));

  $: embeddingFields = isSourceField
    ? (childFields(field).filter(
        f => f.signal != null && childFields(f).some(f => f.dtype === 'embedding')
      ) as LilacField<TextEmbeddingSignal>[])
    : [];

  $: isSortedBy = $datasetViewStore.queryOptions.sort_by?.some(p => pathIsEqual(p, path));
  $: sortOrder = $datasetViewStore.queryOptions.sort_order;

  $: filters = $datasetViewStore.queryOptions.filters?.filter(f => pathIsEqual(f.path, path)) || [];
  $: isFiltered = filters.length > 0;

  // Find all the child display paths for a given field.
  function childDisplayFields(field?: LilacField): LilacField[] {
    if (field?.repeated_field) return childDisplayFields(field.repeated_field);
    if (!field?.fields) return [];

    return (
      [
        // Find all the child source fields
        ...Object.values(field.fields)
          // Filter out the entity field.
          .filter(f => f.path.at(-1) !== VALUE_KEY)
      ]
        .flatMap(f => {
          // Recursively find the children without children
          const children = childDisplayFields(f);
          // If any children are signal roots, dont add the field itself.
          return children.some(c => isSignalRootField(c)) ? children : [f];
        })

        // Filter out specific types of signals
        .filter(c => {
          if (c.dtype === 'embedding') return false;
          if (c.signal != null && childFields(c).some(f => f.dtype === 'embedding')) {
            return false;
          }
          if (c.signal?.signal_name === 'sentences') return false;
          if (c.signal?.signal_name === 'substring_search') return false;
          if (c.signal?.signal_name === 'semantic_similarity') return false;
          if (c.signal?.signal_name === 'concept_labels') return false;

          return true;
        })
    );
  }

  $: isPreview = isPreviewSignal($datasetStore.selectRowsSchema?.data || null, path);

  $: hasMenu = !isPreview && (isSortableField(field) || isFilterableField(field) || !isSignal);

  $: searches = getSearches($datasetViewStore, path);
</script>

<div
  class="flex w-full flex-row items-center border-b border-gray-200 px-4 py-2 hover:bg-gray-100"
  class:bg-blue-50={isSignal}
  class:hover:bg-blue-100={isSignal}
>
  <div class="w-6">
    <Checkbox
      labelText="Show"
      hideLabel
      checked={isVisible}
      on:change={() => {
        if (!isVisible) {
          datasetViewStore.addSelectedColumn(path);
        } else {
          datasetViewStore.removeSelectedColumn(path);
        }
      }}
    />
  </div>
  <div class="w-6" style:margin-left={indent * 24 + 'px'}>
    {#if hasChildren}
      <button
        class="p-2 transition hover:opacity-60"
        class:rotate-180={!expanded}
        on:click={() => (expanded = !expanded)}><CaretDown class="w-3" /></button
      >
    {/if}
  </div>

  <div class="grow truncate whitespace-nowrap pr-2 text-gray-900">
    {fieldName}
  </div>
  {#if isSortedBy}
    <RemovableTag
      interactive
      type="green"
      on:click={() =>
        sortOrder === 'ASC'
          ? ($datasetViewStore.queryOptions.sort_order = 'DESC')
          : ($datasetViewStore.queryOptions.sort_order = 'ASC')}
      on:remove={() => datasetViewStore.removeSortBy(path)}
    >
      Sorted
      {#if sortOrder == 'ASC'}
        <SortAscending />
      {:else}
        <SortDescending />
      {/if}
    </RemovableTag>
  {/if}
  {#if isFiltered}
    {#each filters as filter}
      <div class="mx-1">
        <FilterPill {filter} hidePath />
      </div>
    {/each}
  {/if}
  {#each searches as search}
    <SearchPill {search} />
  {/each}
  {#each embeddingFields as embeddingField}
    <div class="mx-1">
      <EmbeddingBadge embedding={embeddingField.signal?.signal_name} />
    </div>
  {/each}
  {#if isSignalRootField(field) && isPreview}
    <div
      class="compute-signal-preview pointer-events-auto mr-2"
      use:hoverTooltip={{
        text: 'Compute signal over the column and save the result.\n\nThis may be expensive.'
      }}
    >
      <Tag
        type="cyan"
        icon={Chip}
        on:click={() =>
          field.signal &&
          isPreview &&
          triggerCommand({
            command: Command.ComputeSignal,
            namespace: $datasetViewStore.namespace,
            datasetName: $datasetViewStore.datasetName,
            path: sourceField?.path,
            signalName: field.signal?.signal_name,
            value: field.signal
          })}
      />
    </div>
    <div class="mx-1">
      <SignalBadge
        isPreview
        on:click={() =>
          field.signal &&
          isPreview &&
          triggerCommand({
            command: Command.EditPreviewConcept,
            namespace: $datasetViewStore.namespace,
            datasetName: $datasetViewStore.datasetName,
            path: sourceField?.path,
            signalName: field.signal?.signal_name,
            value: field.signal
          })}
      />
    </div>
  {:else if isSignalRootField(field)}
    <div class="mx-1"><SignalBadge /></div>
  {/if}
  {#if isSortableField(field) && !isPreview}
    <div class="flex">
      <Button
        isSelected={expandedDetails}
        kind="ghost"
        size="field"
        iconDescription={expandedDetails ? 'Close details' : 'Expand details'}
        icon={ChevronDown}
        on:click={() => {
          if (expandedDetails) {
            datasetViewStore.removeExpandedColumn(path);
          } else {
            datasetViewStore.addExpandedColumn(path);
          }
        }}
      />
    </div>
  {/if}
  <div>
    {#if hasMenu}
      <OverflowMenu light flipped>
        <SchemaFieldMenu {field} {schema} />
      </OverflowMenu>
    {/if}
  </div>
</div>

{#if expandedDetails}
  <div transition:slide|local>
    <FieldDetails {field} />
  </div>
{/if}

{#if expanded}
  <div transition:slide|local>
    {#if children.length}
      {#each children as childField}
        <svelte:self
          {schema}
          field={childField}
          indent={indent + 1}
          sourceField={isSourceField && isSignalField(childField, schema) ? field : sourceField}
        />
      {/each}
    {/if}
  </div>
{/if}

<style lang="postcss">
  :global(.bx--btn--selected) {
    @apply !bg-slate-300;
  }
  :global(.bx--btn--selected .bx--btn__icon) {
    @apply rotate-180 transition;
  }
  :global(.signal-tag span) {
    @apply px-2;
  }
  :global(.compute-signal-chip .bx--tooltip__label .bx--tooltip__trigger) {
    @apply m-0;
  }
  :global(.compute-signal-preview .bx--tag) {
    @apply cursor-pointer;
  }
  :global(.compute-signal-preview .bx--tag__custom-icon) {
    @apply m-0;
  }
</style>
