<script lang="ts">
  import {querySettings} from '$lib/queries/datasetQueries';
  import {getDatasetContext} from '$lib/stores/datasetStore';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
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
  import {Search} from 'carbon-icons-svelte';
  import {hoverTooltip} from '../common/HoverTooltip';
  import StringSpanHighlight from './StringSpanHighlight.svelte';

  export let path: Path;
  export let row: LilacValueNode;
  export let field: LilacField;
  export let highlightedFields: LilacField[];

  const datasetViewStore = getDatasetViewContext();
  const datasetStore = getDatasetContext();
  const appSettings = getSettingsContext();

  $: computedEmbeddings = getComputedEmbeddings($datasetStore.schema, path);

  $: spanValuePaths = getSpanValuePaths(field, highlightedFields);

  $: settings = querySettings($datasetViewStore.namespace, $datasetViewStore.datasetName);

  $: valueNodes = getValueNodes(row, path);

  function findSimilar(searchText: DataTypeCasted, path: Path) {
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
      path,
      type: 'semantic',
      query: searchText as string,
      embedding
    });
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
        <div class="sticky top-0 flex w-full items-center self-start">
          <div title={displayPath(path)} class="w-full truncate">{displayPath(path)}</div>
          <div>
            <div
              use:hoverTooltip={{
                text: noEmbeddings ? '"More like this" requires an embedding index' : undefined
              }}
              class:opacity-50={noEmbeddings}
            >
              <button
                disabled={noEmbeddings}
                on:click={() => findSimilar(value, path)}
                use:hoverTooltip={{text: 'More like this'}}
                ><Search size={16} />
              </button>
            </div>
          </div>
        </div>
      </div>

      <div class="w-full grow-0 pt-1 font-normal">
        <StringSpanHighlight
          text={formatValue(value)}
          {row}
          {path}
          {markdown}
          spanPaths={spanValuePaths.spanPaths}
          valuePaths={spanValuePaths.valuePaths}
          {datasetViewStore}
          datasetStore={$datasetStore}
          embeddings={computedEmbeddings}
        />
      </div>
    </div>
  {/if}
{/each}
