<script lang="ts">
  import {queryDatasetSchema, querySettings} from '$lib/queries/datasetQueries';
  import {getDatasetViewContext, type ColumnComparisonState} from '$lib/stores/datasetViewStore';
  /**
   * Component that renders a single value from a row in the dataset row view
   * In the case of strings with string_spans, it will render the derived string spans as well
   */
  import {getSettingsContext} from '$lib/stores/settingsStore';
  import {getComputedEmbeddings, getDisplayPath, getSpanValuePaths} from '$lib/view_utils';
  import {
    L,
    PATH_WILDCARD,
    formatValue,
    getValueNodes,
    pathIsEqual,
    pathIsMatching,
    type DataTypeCasted,
    type LilacField,
    type LilacValueNode,
    type Path
  } from '$lilac';
  import {SkeletonText} from 'carbon-components-svelte';
  import {ChevronDown, ChevronUp, DirectionFork, Search, Undo} from 'carbon-icons-svelte';
  import ButtonDropdown from '../ButtonDropdown.svelte';
  import {hoverTooltip} from '../common/HoverTooltip';
  import ItemMediaDiff from './ItemMediaDiff.svelte';
  import StringSpanHighlight from './StringSpanHighlight.svelte';

  export let mediaPath: Path;
  export let row: LilacValueNode | undefined | null = undefined;
  export let field: LilacField;
  export let highlightedFields: LilacField[];
  // The root path contains the sub-path up to the point of this leaf.
  export let rootPath: Path | undefined = undefined;
  // The showPath is a subset of the path that will be displayed for this node.
  export let showPath: Path | undefined = undefined;

  // Choose the root path which is up to the point of the next repeated value.
  $: firstRepeatedIndex = mediaPath.findIndex(p => p === PATH_WILDCARD);
  $: {
    if (rootPath == null) {
      if (firstRepeatedIndex != -1) {
        rootPath = mediaPath.slice(0, firstRepeatedIndex + 1);
      } else {
        rootPath = mediaPath;
      }
    }
  }

  $: valueNodes = row != null ? getValueNodes(row, rootPath!) : [];
  $: isLeaf = valueNodes.length <= 1;

  // Get the list of next root paths for children of a repeated node.
  $: nextRootPaths = valueNodes.map(v => {
    const path = L.path(v)!;
    const nextRepeatedIdx = mediaPath.findIndex((p, i) => p === PATH_WILDCARD && i >= path.length);
    const showPath = mediaPath.slice(nextRepeatedIdx).filter(p => p !== PATH_WILDCARD);
    return {
      rootPath: [
        ...path,
        ...mediaPath.slice(path.length, nextRepeatedIdx === -1 ? undefined : nextRepeatedIdx)
      ],
      showPath
    };
  });

  // The child component will communicate this back upwards to this component.
  let textIsOverBudget = false;
  let userExpanded = false;

  const datasetViewStore = getDatasetViewContext();
  const appSettings = getSettingsContext();

  $: pathForDisplay = showPath != null ? showPath : rootPath!;

  $: displayPath = getDisplayPath(pathForDisplay);

  $: valueNode = valueNodes[0];
  $: value = L.value(valueNode);
  $: settings = querySettings($datasetViewStore.namespace, $datasetViewStore.datasetName);
  // Compare media paths should contain media paths with resolved path wildcards as sometimes the
  // user wants to compare items in an array.
  $: mediaPaths = row != null ? $settings.data?.ui?.media_paths || [] : [];
  $: compareMediaPaths = mediaPaths
    .map(p => (Array.isArray(p) ? p : [p]))
    .flatMap(p => {
      return getValueNodes(row!, p)
        .map(v => L.path(v))
        .filter(p => !pathIsMatching(p, rootPath));
    }) as Path[];

  $: compareItems = compareMediaPaths.map(p => ({
    id: p,
    text: getDisplayPath(p)
  }));
  function selectCompareColumn(event: CustomEvent<{id: Path}>) {
    datasetViewStore.addCompareColumn([rootPath!, event.detail.id]);
  }

  $: schema = queryDatasetSchema($datasetViewStore.namespace, $datasetViewStore.datasetName);

  $: computedEmbeddings = getComputedEmbeddings($schema.data, mediaPath);
  $: noEmbeddings = computedEmbeddings.length === 0;

  $: spanValuePaths = getSpanValuePaths(field, highlightedFields);

  function findSimilar(searchText: DataTypeCasted) {
    let embedding = computedEmbeddings[0];

    if ($settings.data?.preferred_embedding != null) {
      const preferred = $settings.data.preferred_embedding;
      if (computedEmbeddings.some(v => v === preferred)) {
        embedding = preferred;
      }
    }
    if ($appSettings.embedding != null) {
      const preferred = $appSettings.embedding;
      if (computedEmbeddings.some(v => v === preferred)) {
        embedding = preferred;
      }
    }
    datasetViewStore.addSearch({
      path: field.path,
      type: 'semantic',
      query: searchText as string,
      query_type: 'document',
      embedding
    });
  }
  // Returns the second path of a diff, if a given path is being diffed.
  let colCompareState: ColumnComparisonState | null = null;
  $: {
    colCompareState = null;
    for (const compareCols of $datasetViewStore.compareColumns) {
      if (pathIsEqual(compareCols.column, rootPath)) {
        colCompareState = compareCols;
        break;
      }
    }
  }
  function removeComparison() {
    datasetViewStore.removeCompareColumn(mediaPath);
  }
  $: markdown = $settings.data?.ui?.markdown_paths?.find(p => pathIsEqual(p, mediaPath)) != null;
</script>

<div class="flex w-full gap-x-4">
  {#if isLeaf}
    <div class="relative mr-4 flex w-28 flex-none font-mono font-medium text-neutral-500 md:w-44">
      <div class="sticky top-0 flex w-full flex-col gap-y-2 self-start">
        {#if displayPath != ''}
          <div title={displayPath} class="mx-2 mt-2 w-full flex-initial truncate">
            {displayPath}
          </div>
        {/if}
        <div class="flex flex-row">
          <div
            use:hoverTooltip={{
              text: noEmbeddings ? '"More like this" requires an embedding index' : undefined
            }}
            class:opacity-50={noEmbeddings}
          >
            <button
              disabled={noEmbeddings}
              on:click={() => findSimilar(value)}
              use:hoverTooltip={{text: 'More like this'}}
              ><Search size={16} />
            </button>
          </div>
          {#if !colCompareState}
            <ButtonDropdown
              disabled={compareItems.length === 0}
              helperText={'Compare to'}
              items={compareItems}
              buttonIcon={DirectionFork}
              on:select={selectCompareColumn}
              hoist={true}
            />
          {:else}
            <button
              on:click={() => removeComparison()}
              use:hoverTooltip={{text: 'Remove comparison'}}
              ><Undo size={16} />
            </button>
          {/if}
          <button
            disabled={!textIsOverBudget}
            class:opacity-50={!textIsOverBudget}
            on:click={() => (userExpanded = !userExpanded)}
            use:hoverTooltip={{text: userExpanded ? 'Collapse text' : 'Expand text'}}
            >{#if userExpanded}<ChevronUp size={16} />{:else}<ChevronDown size={16} />{/if}
          </button>
        </div>
      </div>
    </div>
    <div class="w-full grow-0 overflow-x-auto pt-1 font-normal">
      {#if row != null}
        {#if colCompareState == null}
          <StringSpanHighlight
            text={formatValue(value)}
            {row}
            path={rootPath}
            {field}
            {markdown}
            isExpanded={userExpanded}
            spanPaths={spanValuePaths.spanPaths}
            valuePaths={spanValuePaths.valuePaths}
            {datasetViewStore}
            embeddings={computedEmbeddings}
            bind:textIsOverBudget
          />
        {:else}
          <ItemMediaDiff {row} {colCompareState} bind:textIsOverBudget isExpanded={userExpanded} />
        {/if}
      {:else}
        <SkeletonText lines={3} paragraph class="w-full" />
      {/if}
    </div>
  {:else}
    <!-- Repeated values will render <ItemMedia> again. -->
    <div class="my-2 flex w-full flex-col rounded border border-neutral-200">
      <div class="m-2 flex flex-col gap-y-2">
        <div title={displayPath} class="mx-2 mt-2 truncate font-mono font-medium text-neutral-500">
          {displayPath}
        </div>
        {#each nextRootPaths as nextRootPath}
          <div class="m-2 rounded border border-neutral-100 p-2">
            <svelte:self
              rootPath={nextRootPath.rootPath}
              showPath={nextRootPath.showPath}
              {row}
              {field}
              {highlightedFields}
              {mediaPath}
            />
          </div>
        {/each}
      </div>
    </div>
  {/if}
</div>
