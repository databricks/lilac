<script lang="ts">
  /**
   * Component that renders string spans as an absolute positioned
   * layer, meant to be rendered on top of the source text.
   */
  import {getDatasetContext} from '$lib/stores/datasetStore';
  import {ITEM_SCROLL_CONTAINER_CTX_KEY, mergeSpans, type MergedSpan} from '$lib/view_utils';

  import {editConceptMutation} from '$lib/queries/conceptQueries';
  import {queryEmbeddings} from '$lib/queries/signalQueries';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {
    getValueNodes,
    isConceptScoreSignal,
    pathIsEqual,
    petals,
    serializePath,
    type LilacField,
    type LilacSchema,
    type LilacValueNode,
    type LilacValueNodeCasted,
    type Signal
  } from '$lilac';
  import {Button} from 'carbon-components-svelte';
  import {ArrowDown, ArrowUp} from 'carbon-icons-svelte';
  import {getContext} from 'svelte';
  import type {Writable} from 'svelte/store';
  import {hoverTooltip} from '../common/HoverTooltip';
  import {spanClick} from './SpanClick';
  import {spanHover} from './SpanHover';
  import type {SpanDetails} from './StringSpanDetails.svelte';
  import {LABELED_TEXT_COLOR, colorFromOpacity} from './colors';
  import {getRenderSpans, getSnippetSpans, type RenderSpan} from './spanHighlight';

  export let text: string;
  export let row: LilacValueNode;
  export let field: LilacField;
  export let visibleKeywordSpanFields: LilacField[];
  export let visibleSpanFields: LilacField[];
  export let visibleLabelSpanFields: LilacField[];

  const spanHoverOpacity = 0.9;

  const datasetViewStore = getDatasetViewContext();
  const datasetStore = getDatasetContext();
  $: schema = $datasetStore.selectRowsSchema?.data?.data_schema as LilacSchema | undefined;
  // Get the embeddings.
  const embeddings = queryEmbeddings();

  // Find the keyword span paths under this field.
  $: keywordSpanPaths = visibleKeywordSpanFields.map(f => serializePath(f.path));
  $: labelSpanPaths = visibleLabelSpanFields.map(f => serializePath(f.path));

  // Map the span field paths to their children that are floats.
  $: spanValueFields = Object.fromEntries(
    visibleSpanFields.map(f => [
      serializePath(f.path),
      petals(f)
        .filter(f => f.dtype != 'string_span')
        .filter(f =>
          $datasetStore.visibleFields?.some(visibleField => pathIsEqual(visibleField.path, f.path))
        )
    ])
  );

  // Filter the floats to only those that are concept scores.
  let spanConceptFields: {[fieldName: string]: LilacField<Signal>[]};
  $: spanConceptFields = Object.fromEntries(
    Object.entries(spanValueFields)
      .map(([path, fields]) => [path, fields.filter(f => isConceptScoreSignal(f.signal))])
      .filter(([_, fields]) => fields.length > 0)
  );

  // Map a path to the visible span fields.
  $: pathToSpans = Object.fromEntries(
    visibleSpanFields.map(f => [
      serializePath(f.path),
      getValueNodes(row, f.path) as LilacValueNodeCasted<'string_span'>[]
    ])
  );

  // Merge all the spans for different features into a single span array.
  $: mergedSpans = mergeSpans(text, pathToSpans);

  // Span hover tracking.
  let pathsHovered: Set<string> = new Set();
  const spanMouseEnter = (renderSpan: RenderSpan) => {
    renderSpan.paths.forEach(path => pathsHovered.add(path));
    pathsHovered = pathsHovered;
  };
  const spanMouseLeave = (renderSpan: RenderSpan) => {
    renderSpan.paths.forEach(path => pathsHovered.delete(path));
    pathsHovered = pathsHovered;
  };
  $: renderSpans = getRenderSpans(
    mergedSpans,
    schema,
    spanValueFields,
    keywordSpanPaths,
    labelSpanPaths,
    field,
    pathsHovered
  );

  // Map each of the paths to their render spans so we can highlight neighbors on hover when there
  // is overlap.
  let pathToRenderSpans: {[pathStr: string]: Array<MergedSpan>} = {};
  $: {
    pathToRenderSpans = {};
    for (const renderSpan of mergedSpans) {
      for (const path of renderSpan.paths) {
        pathToRenderSpans[path] = pathToRenderSpans[path] || [];
        pathToRenderSpans[path].push(renderSpan);
      }
    }
  }

  const getSpanDetails = (span: RenderSpan): SpanDetails => {
    // Get all the render spans that include this path so we can join the text.
    const spansUnderClick = renderSpans.filter(renderSpan =>
      renderSpan.paths.some(s =>
        (span?.paths || []).some(selectedSpanPath => pathIsEqual(selectedSpanPath, s))
      )
    );
    const fullText = spansUnderClick.map(s => s.text).join('');
    const spanDetails: SpanDetails = {
      conceptName: null,
      conceptNamespace: null,
      text: fullText
    };
    // Find the concepts for the selected spans. For now, we select just the first concept.
    for (const spanPath of Object.keys(span.originalSpans)) {
      for (const conceptField of spanConceptFields[spanPath] || []) {
        // Only use the first concept. We will later support multiple concepts.
        spanDetails.conceptName = conceptField.signal!.concept_name;
        spanDetails.conceptNamespace = conceptField.signal!.namespace;
        break;
      }
    }
    return spanDetails;
  };
  const conceptEdit = editConceptMutation();
  const addConceptLabel = (
    conceptNamespace: string,
    conceptName: string,
    text: string,
    label: boolean
  ) => {
    if (!conceptName || !conceptNamespace)
      throw Error('Label could not be added, no active concept.');
    $conceptEdit.mutate([conceptNamespace, conceptName, {insert: [{text, label}]}]);
  };

  let isExpanded = false;
  // Snippets.
  $: ({snippetSpans, someSnippetsHidden} = getSnippetSpans(renderSpans, isExpanded));

  let itemScrollContainer = getContext<Writable<HTMLDivElement | null>>(
    ITEM_SCROLL_CONTAINER_CTX_KEY
  );
</script>

<div class="relative mx-4 overflow-x-hidden text-ellipsis whitespace-break-spaces py-4">
  {#each snippetSpans as snippetSpan}
    {@const renderSpan = snippetSpan.renderSpan}
    {#if snippetSpan.isShown}
      <span
        use:spanHover={{
          namedValues: renderSpan.hoverInfo,
          isHovered: renderSpan.isFirstHover,
          spansHovered: pathsHovered,
          itemScrollContainer: $itemScrollContainer
        }}
        use:spanClick={{
          details: () => getSpanDetails(renderSpan),
          datasetViewStore,
          datasetStore,
          embeddings: $embeddings.data || [],
          addConceptLabel
        }}
        class="hover:cursor-poiner highlight-span text-sm leading-5"
        class:hover:cursor-pointer={visibleSpanFields.length > 0}
        class:font-bold={renderSpan.isBlackBolded}
        class:font-medium={renderSpan.isHighlightBolded && !renderSpan.isBlackBolded}
        style:color={renderSpan.isHighlightBolded && !renderSpan.isBlackBolded
          ? LABELED_TEXT_COLOR
          : ''}
        style:background-color={!renderSpan.isHovered
          ? renderSpan.backgroundColor
          : colorFromOpacity(spanHoverOpacity)}
        on:mouseenter={() => spanMouseEnter(renderSpan)}
        on:mouseleave={() => spanMouseLeave(renderSpan)}>{renderSpan.snippetText}</span
      >
    {:else if snippetSpan.isEllipsis}<span
        use:hoverTooltip={{
          text: 'Some text was hidden to improve readability. \nClick "Show all" to show the entire document.'
        }}
        class="highlight-span text-sm leading-5">...</span
      >{#if snippetSpan.hasNewline}<span><br /></span>{/if}
    {/if}
  {/each}
  {#if someSnippetsHidden}
    <div class="flex flex-row justify-center">
      <div class="w-30 mt-2 rounded border border-neutral-300 text-center">
        {#if !isExpanded}
          <Button
            size="small"
            class="w-full"
            kind="ghost"
            icon={ArrowDown}
            on:click={() => (isExpanded = true)}
          >
            Show all
          </Button>
        {:else}
          <Button
            size="small"
            class="w-full"
            kind="ghost"
            icon={ArrowUp}
            on:click={() => (isExpanded = false)}
          >
            Hide excess
          </Button>
        {/if}
      </div>
    </div>
  {/if}
</div>

<style lang="postcss">
  .highlight-span {
    /** Add a tiny bit of padding so that the hover doesn't flicker between rows. */
    padding-top: 1.5px;
    padding-bottom: 1.5px;
  }
</style>
