<script lang="ts">
  import {getDatasetContext} from '$lib/stores/datasetStore';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {getSearches, udfByAlias} from '$lib/view_utils';
  import * as Lilac from '$lilac';
  import {Checkbox, OverflowMenu, Tag} from 'carbon-components-svelte';
  import {CaretDown, Chip, SortAscending, SortDescending} from 'carbon-icons-svelte';
  import {slide} from 'svelte/transition';
  import {Command, triggerCommand} from '../commands/Commands.svelte';
  import HoverTooltip from '../common/HoverTooltip.svelte';
  import RemovableTag from '../common/RemovableTag.svelte';
  import SchemaFieldMenu from '../contextMenu/SchemaFieldMenu.svelte';
  import EmbeddingBadge from '../datasetView/EmbeddingBadge.svelte';
  import SearchPill from '../datasetView/SearchPill.svelte';

  export let schema: Lilac.LilacSchema;
  export let field: Lilac.LilacField;
  export let sourceField: Lilac.LilacField | undefined = undefined;
  export let indent = 0;
  export let aliasMapping: Record<string, Lilac.Path> | undefined;

  $: isSignalField = Lilac.isSignalField(field, schema);
  $: isSourceField = !isSignalField;

  const FILTER_SHORTHANDS: Record<Lilac.BinaryOp | Lilac.UnaryOp | Lilac.ListOp, string> = {
    equals: '=',
    not_equal: '!=',
    less: '<',
    less_equal: '<=',
    greater: '>',
    greater_equal: '>=',
    in: 'in',
    exists: 'exists'
  };

  const datasetViewStore = getDatasetViewContext();
  const datasetStore = getDatasetContext();

  let expanded = true;

  $: path = field.path;
  $: alias = field.alias;

  $: isRepeatedField = field.path.at(-1) === Lilac.PATH_WILDCARD ? true : false;
  $: fieldName = isRepeatedField ? field.path.at(-2) : field.path.at(-1);

  $: children = childDisplayFields(field);
  $: hasChildren = children.length > 0;

  $: isVisible = $datasetStore.visibleFields?.some(f => Lilac.pathIsEqual(f.path, path));

  $: embeddingFields = isSourceField
    ? (Lilac.childFields(field).filter(
        f => f.signal != null && Lilac.childFields(f).some(f => f.dtype === 'embedding')
      ) as Lilac.LilacField<Lilac.TextEmbeddingSignal>[])
    : [];

  $: isSortedBy = $datasetViewStore.queryOptions.sort_by?.some(p =>
    Lilac.pathIsEqual(p, alias || path)
  );
  $: sortOrder = $datasetViewStore.queryOptions.sort_order;

  $: filters =
    $datasetViewStore.queryOptions.filters?.filter(f => Lilac.pathIsEqual(f.path, alias || path)) ||
    [];
  $: isFiltered = filters.length > 0;

  // Find all the child display paths for a given field.
  function childDisplayFields(field?: Lilac.LilacField): Lilac.LilacField[] {
    if (field?.repeated_field) return childDisplayFields(field.repeated_field);
    if (!field?.fields) return [];

    return (
      [
        // Find all the child source fields
        ...Object.values(field.fields)
          // Filter out the entity field.
          .filter(f => f.path.at(-1) !== Lilac.VALUE_KEY)
      ]
        .flatMap(f => {
          // Recursively find the children without children
          const children = childDisplayFields(f);
          // If any children are signal roots, dont add the field itself.
          return children.some(c => Lilac.isSignalRootField(c)) ? children : [f];
        })

        // Filter out specific types of signals
        .filter(c => {
          if (c.dtype === 'embedding') return false;
          if (c.signal != null && Lilac.childFields(c).some(f => f.dtype === 'embedding')) {
            return false;
          }
          if (c.signal?.signal_name === 'sentences') return false;
          if (c.signal?.signal_name === 'substring_search') return false;
          if (c.signal?.signal_name === 'semantic_similarity') return false;

          return true;
        })
    );
  }

  // Check if any query option columns match the alias.
  $: udfPath = udfByAlias($datasetStore.selectRowsSchema?.data || null, alias);

  // Check if any query option columns match the alias
  $: searches = getSearches($datasetViewStore, path);
</script>

<div
  class="flex w-full flex-row items-center border-b border-gray-200 px-4 py-2 hover:bg-gray-100"
  class:bg-blue-50={isSignalField}
  class:hover:bg-blue-100={isSignalField}
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
      on:remove={() => datasetViewStore.removeSortBy(alias || path)}
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
    <RemovableTag
      interactive
      type="magenta"
      on:click={() =>
        triggerCommand({
          command: Command.EditFilter,
          namespace: $datasetViewStore.namespace,
          datasetName: $datasetViewStore.datasetName,
          path
        })}
      on:remove={() => datasetViewStore.removeFilters(alias || path)}
    >
      {#if filters.length > 1}
        Filtered
      {:else}
        {FILTER_SHORTHANDS[filters[0].op]} {filters[0].value ?? ''}
      {/if}
    </RemovableTag>
  {/if}
  {#each searches as search}
    <SearchPill {search} />
  {/each}
  {#each embeddingFields as embeddingField}
    <div class="mx-1">
      <EmbeddingBadge embedding={embeddingField.signal?.signal_name} />
    </div>
  {/each}
  {#if Lilac.isSignalRootField(field) && udfPath}
    <div class="mr-2">
      <Tag
        type="cyan"
        on:click={() =>
          field.signal &&
          field.alias?.length === 1 &&
          triggerCommand({
            command: Command.ComputeSignal,
            namespace: $datasetViewStore.namespace,
            datasetName: $datasetViewStore.datasetName,
            path: sourceField?.path,
            signalName: field.signal?.signal_name,
            value: field.signal
          })}
      >
        <HoverTooltip size="small" icon={Chip} class="compute-signal-chip flex">
          <div class="w-48">
            <p>Compute signal over the column and save the result.</p>
            <p class="mt-2">This may be expensive.</p>
          </div>
        </HoverTooltip></Tag
      >
    </div>
    <Tag
      interactive
      type="green"
      on:click={() =>
        field.signal &&
        field.alias?.length === 1 &&
        triggerCommand({
          command: Command.EditPreviewConcept,
          namespace: $datasetViewStore.namespace,
          datasetName: $datasetViewStore.datasetName,
          path: sourceField?.path,
          signalName: field.signal?.signal_name,
          value: field.signal,
          alias: field.alias[0]
        })}
    >
      Preview
    </Tag>
  {:else if Lilac.isSignalRootField(field)}
    <Tag type="blue" class="signal-tag whitespace-nowrap">Signal</Tag>
  {/if}
  <div>
    <OverflowMenu light flipped>
      <SchemaFieldMenu {field} {schema} />
    </OverflowMenu>
  </div>
</div>

{#if expanded}
  <div transition:slide|local>
    {#if children.length}
      {#each children as childField}
        <svelte:self
          {schema}
          field={childField}
          indent={indent + 1}
          {aliasMapping}
          sourceField={isSourceField && Lilac.isSignalField(childField, schema)
            ? field
            : sourceField}
        />
      {/each}
    {/if}
  </div>
{/if}

<style lang="postcss">
  :global(.signal-tag span) {
    @apply px-2;
  }
  :global(.compute-signal-chip .bx--tooltip__label .bx--tooltip__trigger) {
    @apply m-0;
  }
</style>
