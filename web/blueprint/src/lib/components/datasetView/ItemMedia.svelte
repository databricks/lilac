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
  import {DirectionFork, PropertyRelationship, Search, Undo} from 'carbon-icons-svelte';
  import ButtonDropdown from '../ButtonDropdown.svelte';
  import {hoverTooltip} from '../common/HoverTooltip';
  import ItemMediaDiff from './ItemMediaDiff.svelte';
  import StringSpanHighlight from './StringSpanHighlight.svelte';

  export let path: Path;
  export let row: LilacValueNode;
  export let field: LilacField;
  export let highlightedFields: LilacField[];

  const datasetViewStore = getDatasetViewContext();
  const appSettings = getSettingsContext();

  $: datasetSettings = querySettings($datasetViewStore.namespace, $datasetViewStore.datasetName);
  $: mediaPaths = ($datasetSettings.data?.ui?.media_paths || [])
    .map(p => (Array.isArray(p) ? p : [p]))
    .filter(p => !pathIsEqual(p, path));
  $: compareItems = mediaPaths.map(p => ({
    id: p,
    text: displayPath(p)
  }));
  function selectCompareColumn(event: CustomEvent<{id: Path}>) {
    datasetViewStore.addCompareColumn([path, event.detail.id]);
  }

  $: schema = queryDatasetSchema($datasetViewStore.namespace, $datasetViewStore.datasetName);

  $: computedEmbeddings = getComputedEmbeddings($schema.data, path);

  $: spanValuePaths = getSpanValuePaths(field, highlightedFields);

  $: settings = querySettings($datasetViewStore.namespace, $datasetViewStore.datasetName);

  $: valueNodes = getValueNodes(row, path);

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
  let leftComparePath: Path | null = null;
  let rightComparePath: Path | null = null;
  $: {
    colCompareState = null;
    for (const compareCols of $datasetViewStore.compareColumns) {
      if (pathIsEqual(compareCols.column, path)) {
        colCompareState = compareCols;
        leftComparePath = colCompareState.swapDirection
          ? colCompareState.compareToColumn
          : colCompareState.column;
        rightComparePath = colCompareState.swapDirection
          ? colCompareState.column
          : colCompareState.compareToColumn;
        break;
      }
    }
  }
  function removeComparison() {
    datasetViewStore.removeCompareColumn(path);
  }
</script>

{#each valueNodes as valueNode}
  {@const value = L.value(valueNode)}
  {@const noEmbeddings = computedEmbeddings.length === 0}
  {#if notEmpty(value)}
    {@const path = L.path(valueNode) || []}
    {@const markdown = $settings.data?.ui?.markdown_paths?.find(p => pathIsEqual(p, path)) != null}
    <div class="flex w-full gap-x-4">
      <div class="relative flex w-28 flex-none font-mono font-medium text-neutral-500 md:w-44">
        <div class="relative top-0 flex w-full items-center self-start">
          <div title={displayPath(path)} class="w-full flex-initial truncate">
            {#if colCompareState == null}
              {displayPath(path)}
            {:else if leftComparePath != null && rightComparePath != null}
              <div class="mt-1 flex flex-col gap-y-2">
                <div>
                  {displayPath(leftComparePath)}
                </div>
                <div>
                  <PropertyRelationship />
                </div>
                <div>{displayPath(rightComparePath)}</div>
              </div>
            {/if}
          </div>
          <div class="w-12">
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
          </div>
          <div class="z-50 w-8">
            {#if !colCompareState}
              <ButtonDropdown
                helperText={'Compare to'}
                items={compareItems}
                buttonIcon={DirectionFork}
                on:select={selectCompareColumn}
              />
            {:else}
              <button
                on:click={() => removeComparison()}
                use:hoverTooltip={{text: 'Remove comparison'}}
                ><Undo size={16} />
              </button>
            {/if}
          </div>
        </div>
      </div>

      <div class="relative z-10 w-full grow-0 overflow-x-auto pt-1 font-normal">
        {#if colCompareState == null}
          <StringSpanHighlight
            text={formatValue(value)}
            {row}
            {path}
            {field}
            {markdown}
            spanPaths={spanValuePaths.spanPaths}
            valuePaths={spanValuePaths.valuePaths}
            {datasetViewStore}
            embeddings={computedEmbeddings}
          />
        {:else}
          <ItemMediaDiff {row} {colCompareState} />
        {/if}
      </div>
    </div>
  {/if}
{/each}
