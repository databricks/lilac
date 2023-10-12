<script lang="ts">
  import {getDatasetViewContext, getSelectRowsSchemaOptions} from '$lib/stores/datasetViewStore';
  import {DTYPE_TO_ICON, getSearches, isPreviewSignal} from '$lib/view_utils';

  import {computeSignalMutation, querySelectRowsSchema} from '$lib/queries/datasetQueries';
  import {querySignals} from '$lib/queries/signalQueries';
  import {
    PATH_WILDCARD,
    VALUE_KEY,
    childFields,
    isLabelField,
    isSignalField,
    isSignalRootField,
    isSortableField,
    pathIsEqual,
    serializePath,
    type ConceptSignal,
    type LilacField,
    type LilacSchema,
    type TextEmbeddingSignal
  } from '$lilac';
  import {Tag} from 'carbon-components-svelte';
  import {ChevronDown, Chip, SortAscending, SortDescending} from 'carbon-icons-svelte';
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

  $: isSignal = isSignalField(field);
  $: isSignalRoot = isSignalRootField(field);
  $: isLabel = isLabelField(field);
  $: isSourceField = !isSignal && !isLabel;

  const signalMutation = computeSignalMutation();
  const datasetViewStore = getDatasetViewContext();

  $: selectRowsSchema = querySelectRowsSchema(
    $datasetViewStore.namespace,
    $datasetViewStore.datasetName,
    getSelectRowsSchemaOptions($datasetViewStore)
  );

  $: path = field.path;

  $: expandedStats = $datasetViewStore.expandedStats[serializePath(path)] || false;

  const signals = querySignals();

  $: isRepeatedField = path.at(-1) === PATH_WILDCARD ? true : false;
  $: fieldTitle = isRepeatedField ? path.at(-2) : path.at(-1);
  let fieldHoverDetails: string | null = null;
  // If the field is a signal root, use the signal name to define the title.
  $: {
    if (field.signal && $signals.data != null) {
      if (field.signal.signal_name === 'concept_score') {
        const conceptSignal = field.signal as ConceptSignal;
        fieldTitle = `${conceptSignal.concept_name}`;
        fieldHoverDetails =
          `Concept '${conceptSignal.namespace}/${conceptSignal.concept_name}' arguments:\n\n` +
          `embedding: '${conceptSignal.embedding}'` +
          (conceptSignal.version != null ? `\nversion: ${conceptSignal.version}` : '');
      } else {
        const signalInfo = $signals.data.find(s => s.name === field.signal?.signal_name);
        if (signalInfo != null) {
          fieldTitle = signalInfo.json_schema.title;

          const argumentDetails = Object.entries(field.signal || {})
            .filter(([arg, _]) => arg != 'signal_name')
            .map(([k, v]) => `${k}: ${v}`)
            .join('\n');

          if (argumentDetails.length > 0) {
            fieldHoverDetails = `Signal '${signalInfo.name}' arguments: \n\n${argumentDetails}`;
          }
        }
      }
    }
  }

  $: children = childDisplayFields(field);

  $: embeddingFields = isSourceField
    ? (childFields(field).filter(
        f => f.signal != null && childFields(f).some(f => f.dtype === 'embedding')
      ) as LilacField<TextEmbeddingSignal>[])
    : [];

  $: isSortedBy = $datasetViewStore.query.sort_by?.some(p => pathIsEqual(p, path));
  $: sortOrder = $datasetViewStore.query.sort_order;

  $: filters = $datasetViewStore.query.filters?.filter(f => pathIsEqual(f.path, path)) || [];
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

  $: isPreview = isPreviewSignal($selectRowsSchema.data || null, path);

  $: searches = getSearches($datasetViewStore, path);

  $: signalTooltip = isSignal ? '. Generated by a signal' : '';
  // TODO(smilkov): Handle nested arrays (repeated of repeated).
  $: dtypeTooltip =
    field.dtype ??
    (field.repeated_field && field.repeated_field.dtype
      ? `${field.repeated_field.dtype}[]`
      : 'object');
  $: tooltip = `${dtypeTooltip}${signalTooltip}`;

  $: isExpandable = isSortableField(field) && !isPreview;
</script>

<div class="border-gray-300" class:border-b={isSourceField}>
  <div
    class="flex w-full flex-row items-center gap-x-2 border-gray-300 px-4 hover:bg-gray-100"
    class:bg-blue-50={isSignal}
    class:bg-emerald-100={isPreview}
    class:bg-teal-100={isLabel}
    class:hover:bg-blue-100={isSignal}
  >
    <div
      class="rounded-md bg-blue-200 p-0.5"
      style:margin-left={indent * 1.5 + 'rem'}
      class:bg-blue-200={isSignal}
      use:hoverTooltip={{text: tooltip}}
    >
      {#if field.dtype}
        <svelte:component this={DTYPE_TO_ICON[field.dtype]} title={field.dtype} />
      {:else if field.repeated_field && field.repeated_field.dtype}
        <!-- TODO(smilkov): Handle nested arrays (repeated of repeated). -->
        <div class="flex">
          <svelte:component
            this={DTYPE_TO_ICON[field.repeated_field.dtype]}
            title={field.dtype || undefined}
          />[]
        </div>
      {:else}
        <span class="font-mono">{'{}'}</span>
      {/if}
    </div>
    <div class="grow" use:hoverTooltip={{text: fieldHoverDetails || ''}}>
      <button
        class="ml-2 w-full cursor-pointer truncate whitespace-nowrap text-left text-gray-900"
        class:cursor-default={!isExpandable}
        disabled={!isExpandable}
        on:click={() => {
          if (isExpandable) {
            if (expandedStats) {
              datasetViewStore.removeExpandedColumn(path);
            } else {
              datasetViewStore.addExpandedColumn(path);
            }
          }
        }}
      >
        {fieldTitle}
      </button>
    </div>
    {#if isSortedBy}
      <RemovableTag
        interactive
        type="green"
        on:click={() =>
          sortOrder === 'ASC'
            ? ($datasetViewStore.query.sort_order = 'DESC')
            : ($datasetViewStore.query.sort_order = 'ASC')}
        on:remove={() => datasetViewStore.removeSortBy(path)}
      >
        <div class="flex flex-row">
          <div class="mr-1">Sorted</div>
          <span>
            {#if sortOrder == 'ASC'}
              <SortAscending />
            {:else}
              <SortDescending />
            {/if}</span
          >
        </div>
      </RemovableTag>
    {/if}
    {#if isFiltered}
      {#each filters as filter}
        <FilterPill {schema} {filter} hidePath />
      {/each}
    {/if}
    {#each searches as search}
      <SearchPill {search} />
    {/each}
    {#each embeddingFields as embeddingField}
      <EmbeddingBadge embedding={embeddingField.signal?.signal_name} />
    {/each}
    {#if isPreview && isSignalRoot}
      <div
        class="compute-signal-preview pointer-events-auto"
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
            sourceField &&
            $signalMutation.mutate([
              $datasetViewStore.namespace,
              $datasetViewStore.datasetName,
              {
                leaf_path: sourceField.path,
                signal: field.signal
              }
            ])}
        />
      </div>
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
    {/if}
    {#if isExpandable}
      <button
        use:hoverTooltip={{text: expandedStats ? 'Close statistics' : 'See statistics'}}
        class:bg-slate-300={expandedStats}
        on:click={() => {
          if (expandedStats) {
            datasetViewStore.removeExpandedColumn(path);
          } else {
            datasetViewStore.addExpandedColumn(path);
          }
        }}
      >
        <div class="transition" class:rotate-180={expandedStats}><ChevronDown /></div>
      </button>
    {/if}
    <SchemaFieldMenu {field} />
  </div>

  {#if expandedStats}
    <div transition:slide|local class="px-2">
      <FieldDetails {field} />
    </div>
  {/if}

  <div transition:slide|local>
    {#if children.length}
      {#each children as childField}
        <svelte:self
          {schema}
          field={childField}
          indent={indent + 1}
          sourceField={isSourceField && isSignalField(childField) ? field : sourceField}
        />
      {/each}
    {/if}
  </div>
</div>

<style lang="postcss">
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
