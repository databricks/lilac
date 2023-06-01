<script lang="ts">
  import {getDatasetViewContext, isPathVisible} from '$lib/stores/datasetViewStore';
  import * as Lilac from '$lilac';
  import {Checkbox, OverflowMenu, Tag, Tooltip} from 'carbon-components-svelte';
  import {AssemblyCluster, CaretDown, SortAscending, SortDescending} from 'carbon-icons-svelte';
  import {slide} from 'svelte/transition';
  import {Command, triggerCommand} from '../commands/Commands.svelte';
  import RemovableTag from '../common/RemovableTag.svelte';
  import SchemaFieldMenu from '../contextMenu/SchemaFieldMenu.svelte';

  export let schema: Lilac.LilacSchema;
  export let field: Lilac.LilacSchemaField;
  export let sourceField: Lilac.LilacSchemaField | undefined = undefined;
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

  let datasetViewStore = getDatasetViewContext();
  let expanded = true;

  $: path = field.path;
  $: alias = field.alias;

  $: isRepeatedField = field.path.at(-1) === Lilac.PATH_WILDCARD ? true : false;
  $: fieldName = isRepeatedField ? field.path.at(-2) : field.path.at(-1);

  $: children = childFields(field);
  $: hasChildren = children.length > 0;

  $: isVisible = isPathVisible($datasetViewStore.visibleColumns, path, aliasMapping);

  $: embeddingFields = isSourceField
    ? (Lilac.listFields(field).filter(
        f => f.signal != null && Lilac.listFields(f).some(f => f.dtype === 'embedding')
      ) as Lilac.LilacSchemaField<Lilac.TextEmbeddingSignal>[])
    : [];

  $: isSortedBy = $datasetViewStore.queryOptions.sort_by?.some(p =>
    Lilac.pathIsEqual(p, alias || path)
  );
  $: sortOrder = $datasetViewStore.queryOptions.sort_order;

  $: filters =
    $datasetViewStore.queryOptions.filters?.filter(f => Lilac.pathIsEqual(f.path, alias || path)) ||
    [];
  $: isFiltered = filters.length > 0;

  // Find all the child paths for a given field.
  function childFields(field?: Lilac.LilacSchemaField): Lilac.LilacSchemaField[] {
    if (field?.repeated_field) return childFields(field.repeated_field);
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
          const children = childFields(f);
          // If any children are signal roots, dont add the field itself.
          return children.some(c => Lilac.isSignalRootField(c)) ? children : [f];
        })
        // Filter out specific types of signals
        .filter(c => {
          if (c.dtype === 'embedding') return false;
          if (c.signal != null && Lilac.listFields(c).some(f => f.dtype === 'embedding')) {
            return false;
          }
          if (c.signal?.signal_name === 'sentences') return false;
          if (c.signal?.signal_name === 'substring_search') return false;

          return true;
        })
    );
  }

  // Check if any query option columns match the alias
  $: udfColumn = alias
    ? $datasetViewStore.queryOptions.columns?.find(
        c => typeof c === 'object' && !Array.isArray(c) && c.alias === alias?.[0]
      )
    : undefined;
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
          datasetViewStore.addVisibleColumn(path);
        } else {
          datasetViewStore.removeVisibleColumn(path);
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

  <div class="grow truncate whitespace-nowrap text-gray-900">
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
  {#each embeddingFields as embeddingField}<Tooltip>
      <Tag type="purple" slot="icon"
        ><AssemblyCluster class="mr-1 inline-block" />{embeddingField.signal?.signal_name}</Tag
      >
      {embeddingField.signal?.signal_name} embeddings computed
    </Tooltip>
  {/each}
  {#if Lilac.isSignalRootField(field) && udfColumn}
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
        })}>Signal Preview</Tag
    >
  {:else if Lilac.isSignalRootField(field)}
    <Tag type="blue">Signal</Tag>
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
