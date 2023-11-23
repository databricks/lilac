<script lang="ts">
  import {queryDatasetSchema, querySettings} from '$lib/queries/datasetQueries';
  import {getDatasetViewContext, type ColumnComparisonState} from '$lib/stores/datasetViewStore';
  /**
   * Component that renders a single value from a row in the dataset row view
   * In the case of strings with string_spans, it will render the derived string spans as well
   */
  import {getSettingsContext} from '$lib/stores/settingsStore';
  import {notEmpty} from '$lib/utils';
  import {displayPath, getComputedEmbeddings, getSpanValuePaths} from '$lib/view_utils';
  import {
    L,
    formatValue,
    getValueNodes,
    pathIsEqual,
    type DataTypeCasted,
    type LilacField,
    type LilacValueNode,
    type Path
  } from '$lilac';
  import {ChevronDown, ChevronUp, DirectionFork, Search, Undo} from 'carbon-icons-svelte';
  import ButtonDropdown from '../ButtonDropdown.svelte';
  import {hoverTooltip} from '../common/HoverTooltip';
  import ItemMediaDiff from './ItemMediaDiff.svelte';
  import StringSpanHighlight from './StringSpanHighlight.svelte';

  export let path: Path;
  export let row: LilacValueNode;
  export let field: LilacField;
  export let highlightedFields: LilacField[];

  // The child component will communicate this back upwards to this component.
  let textIsOverBudget = false;
  let userExpanded = false;

  const datasetViewStore = getDatasetViewContext();
  const appSettings = getSettingsContext();

  $: valueNode = getValueNodes(row, path)[0];
  $: value = L.value(valueNode);

  $: datasetSettings = querySettings($datasetViewStore.namespace, $datasetViewStore.datasetName);
  // Compare media paths should contain media paths with resolved path wildcards as sometimes the
  // user wants to compare items in an array.
  $: compareMediaPaths = ($datasetSettings.data?.ui?.media_paths || [])
    .map(p => (Array.isArray(p) ? p : [p]))
    .flatMap(p => {
      const paths = getValueNodes(row, p)
        .map(v => L.path(v))
        .filter(p => !pathIsEqual(p, path));
      return paths;
    }) as Path[];

  $: compareItems = compareMediaPaths.map(p => ({
    id: p,
    text: displayPath(p)
  }));
  function selectCompareColumn(event: CustomEvent<{id: Path}>) {
    datasetViewStore.addCompareColumn([path, event.detail.id]);
  }

  $: schema = queryDatasetSchema($datasetViewStore.namespace, $datasetViewStore.datasetName);

  $: computedEmbeddings = getComputedEmbeddings($schema.data, path);
  $: noEmbeddings = computedEmbeddings.length === 0;

  $: spanValuePaths = getSpanValuePaths(field, highlightedFields);

  $: settings = querySettings($datasetViewStore.namespace, $datasetViewStore.datasetName);

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
      if (pathIsEqual(compareCols.column, path)) {
        colCompareState = compareCols;
        break;
      }
    }
  }
  function removeComparison() {
    datasetViewStore.removeCompareColumn(path);
  }
</script>

{#if notEmpty(valueNode)}
  {@const markdown = $settings.data?.ui?.markdown_paths?.find(p => pathIsEqual(p, path)) != null}
  <div class="flex w-full gap-x-4">
    <div class="relative flex w-28 flex-none font-mono font-medium text-neutral-500 md:w-44">
      <div class="sticky top-0 mt-2 flex w-full flex-col gap-y-2 self-start">
        <div title={displayPath(path)} class="w-full flex-initial truncate">
          {displayPath(path)}
        </div>
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
      {#if colCompareState == null}
        <StringSpanHighlight
          text={formatValue(value)}
          {row}
          {path}
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
    </div>
  </div>
{/if}
