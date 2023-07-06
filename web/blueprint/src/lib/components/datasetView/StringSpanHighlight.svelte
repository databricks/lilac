<script lang="ts">
  /**
   * Component that renders string spans as an absolute positioned
   * layer, meant to be rendered on top of the source text.
   */
  import {getDatasetContext} from '$lib/stores/datasetStore';
  import {ITEM_SCROLL_CONTAINER_CTX_KEY, mergeSpans, type MergedSpan} from '$lib/view_utils';

  import {
    L,
    deserializePath,
    getField,
    getValueNodes,
    isConceptScoreSignal,
    pathIncludes,
    pathIsEqual,
    petals,
    serializePath,
    valueAtPath,
    type ConceptLabelsSignal,
    type ConceptScoreSignal,
    type LilacField,
    type LilacSchema,
    type LilacValueNode,
    type LilacValueNodeCasted,
    type Signal,
    type SubstringSignal
  } from '$lilac';
  import {Button} from 'carbon-components-svelte';
  import {ArrowDown, ArrowUp} from 'carbon-icons-svelte';
  import {getContext} from 'svelte';
  import type {Writable} from 'svelte/store';
  import {hoverTooltip} from '../common/HoverTooltip';
  import {spanHover} from './SpanHover';
  import type {SpanHoverNamedValue} from './SpanHoverTooltip.svelte';
  import StringSpanDetails, {type SpanDetails} from './StringSpanDetails.svelte';
  import {LABELED_TEXT_COLOR, colorFromOpacity, colorFromScore} from './colors';

  export let text: string;
  export let row: LilacValueNode;
  export let field: LilacField;
  export let visibleKeywordSpanFields: LilacField[];
  export let visibleSpanFields: LilacField[];
  export let visibleLabelSpanFields: LilacField[];

  const spanHoverOpacity = 0.9;
  // When the text length exceeds this number we start to snippet.
  const SNIPPET_LEN_BUDGET = 500;

  const datasetStore = getDatasetContext();
  $: selectRowsSchema = $datasetStore.selectRowsSchema;

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

  interface RenderSpan {
    paths: string[];
    text: string;
    originalSpans: {[spanSet: string]: LilacValueNodeCasted<'string_span'>[]};

    backgroundColor: string;
    isBlackBolded: boolean;
    isHighlightBolded: boolean;

    // Whether this span needs to be shown as a snippet.
    isShownSnippet: boolean;
    snippetScore: number;
    // The text post-processed for snippets.
    snippetText: string;

    hoverInfo: SpanHoverNamedValue[];
    // Whether the hover matches any path in this render span. Used for highlighting.
    isHovered: boolean;
    // Whether this render span is the first matching span for the hovered span. This is used for
    // showing the tooltip only on the first matching path.
    isFirstHover: boolean;
  }

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

  // Map the merged spans to the information needed to render each span.
  let renderSpans: RenderSpan[];
  $: {
    renderSpans = [];
    // Keep a list of paths seen so we don't show the same information twice.
    const pathsProcessed: Set<string> = new Set();
    for (const mergedSpan of mergedSpans) {
      let isShownSnippet = false;
      // Keep track of the paths that haven't been seen before. This is where we'll show metadata
      // and hover info.
      const newPaths: string[] = [];
      for (const mergedSpanPath of mergedSpan.paths) {
        if (pathsProcessed.has(mergedSpanPath)) continue;
        newPaths.push(mergedSpanPath);
        pathsProcessed.add(mergedSpanPath);
      }

      const hoverInfo: SpanHoverNamedValue[] = [];
      // Compute the maximum score for all original spans matching this render span to choose the
      // color.
      let maxScore = -Infinity;
      for (const [spanPathStr, originalSpans] of Object.entries(mergedSpan.originalSpans)) {
        const valueFields = spanValueFields[spanPathStr];
        const spanPath = deserializePath(spanPathStr);
        if (valueFields.length === 0) continue;

        for (const originalSpan of originalSpans) {
          for (const valueField of valueFields) {
            const subPath = valueField.path.slice(spanPath.length);
            const valueNode = valueAtPath(originalSpan as LilacValueNode, subPath);
            if (valueNode == null) continue;

            const value = L.value(valueNode);
            if (value == null) continue;

            if (valueField.dtype === 'float32') {
              const floatValue = L.value<'float32'>(valueNode);
              if (floatValue != null) {
                maxScore = Math.max(maxScore, floatValue);
              }
            }

            // Add extra metadata. If this is a path that we've already seen before, ignore it as
            // the value will be rendered alongside the first path.
            const originalPath = serializePath(L.path(originalSpan as LilacValueNode)!);
            const pathSeen = !newPaths.includes(originalPath);

            if (valueField.signal?.signal_name === 'concept_score') {
              if (!pathSeen) {
                const signal = valueField.signal as ConceptScoreSignal;
                hoverInfo.push({
                  name: `${signal.namespace}/${signal.concept_name}`,
                  value,
                  isConcept: true
                });
              }

              if ((value as number) > 0.5) {
                isShownSnippet = true;
              }
            } else {
              // Check if this is a concept label.
              let isConceptLabelSignal = false;
              for (const labelSpanPath of labelSpanPaths) {
                if (
                  pathIncludes(valueField.path, labelSpanPath) &&
                  selectRowsSchema?.data?.schema != null
                ) {
                  const field = getField(
                    selectRowsSchema.data.schema as LilacSchema,
                    deserializePath(labelSpanPath).slice(0, -1)
                  );
                  if (field?.signal?.signal_name === 'concept_labels') {
                    if (!pathSeen) {
                      const signal = field?.signal as ConceptLabelsSignal;
                      isConceptLabelSignal = true;
                      hoverInfo.push({
                        name: `${signal.namespace}/${signal.concept_name} label`,
                        value
                      });
                    }

                    isShownSnippet = true;
                  }
                }
              }
              // Show arbitrary metadata.
              if (!isConceptLabelSignal) {
                const name = serializePath(valueField.path.slice(field.path.length));
                hoverInfo.push({
                  name,
                  value
                });
              }
            }
          }
        }
      }

      // Add keyword info. Keyword results don't have values so we process them separately.
      let isKeywordSpan = false;
      if (selectRowsSchema?.data?.schema != null) {
        for (const keywordSpanPath of keywordSpanPaths) {
          if (mergedSpan.originalSpans[keywordSpanPath] != null) {
            isKeywordSpan = true;
            const field = getField(
              selectRowsSchema.data.schema as LilacSchema,
              deserializePath(keywordSpanPath).slice(0, -1)
            );
            const signal = field?.signal as SubstringSignal;
            hoverInfo.push({name: 'keyword', value: signal.query, isKeywordSearch: true});
            isShownSnippet = true;
          }
        }
      }

      const isLabeled = labelSpanPaths.some(
        labelPath => mergedSpan.originalSpans[labelPath] != null
      );
      const isHovered = mergedSpan.paths.some(path => pathsHovered.has(path));

      // The rendered span is a first hover if there is a new path that matches a specific render
      // span that is hovered.
      const isFirstHover =
        isHovered &&
        newPaths.length > 0 &&
        Array.from(pathsHovered).some(pathHovered => newPaths.includes(pathHovered));

      renderSpans.push({
        backgroundColor: colorFromScore(maxScore),
        isBlackBolded: isKeywordSpan,
        isHighlightBolded: isLabeled,
        isShownSnippet,
        snippetScore: maxScore,
        hoverInfo,
        paths: mergedSpan.paths,
        text: mergedSpan.text,
        snippetText: mergedSpan.text,
        originalSpans: mergedSpan.originalSpans,
        isHovered,
        isFirstHover
      });
    }
  }

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

  // Span selection via a click.
  let selectedSpan: RenderSpan | undefined;
  let selectedSpanDetails: SpanDetails | undefined;
  // Store the mouse position after selecting a span so we can keep the details next to the cursor.
  let spanClickMousePosition: {x: number; y: number} | undefined;
  $: {
    if (selectedSpan != null) {
      // Get all the render spans that include this path so we can join the text.
      const spansUnderClick = renderSpans.filter(renderSpan =>
        renderSpan.paths.some(s =>
          (selectedSpan?.paths || []).some(selectedSpanPath => pathIsEqual(selectedSpanPath, s))
        )
      );
      const fullText = spansUnderClick.map(s => s.text).join('');
      selectedSpanDetails = {
        conceptName: null,
        conceptNamespace: null,
        text: fullText
      };
      // Find the concepts for the selected spans. For now, we select just the first concept.
      for (const spanPath of Object.keys(selectedSpan.originalSpans)) {
        for (const conceptField of spanConceptFields[spanPath] || []) {
          // Only use the first concept. We will later support multiple concepts.
          selectedSpanDetails.conceptName = conceptField.signal!.concept_name;
          selectedSpanDetails.conceptNamespace = conceptField.signal!.namespace;
          break;
        }
      }
    } else {
      selectedSpanDetails = undefined;
    }
  }

  interface SnippetSpan {
    renderSpan: RenderSpan;
    isShown: boolean;
    // When the snippet is hidden, whether it should be replaced with ellipsis. We only do this once
    // for a contigous set of hidden snippets.
    isEllipsis?: boolean;
    // When the snippet is hidden, whether the original text had a new-line so it can be preserved.
    hasNewline?: boolean;
  }

  let isExpanded = false;
  // Snippets.
  let snippetSpans: SnippetSpan[];
  let someSnippetsHidden = false;

  $: {
    // Map the merged spans to the information needed to render each span.
    snippetSpans = [];

    if (isExpanded) {
      snippetSpans = renderSpans.map(renderSpan => ({renderSpan, isShown: true}));
    } else {
      // Find all the spans that are shown snippets and not shown snippets.
      let shownSnippetTotalLength = 0;
      for (const renderSpan of renderSpans) {
        if (renderSpan.isShownSnippet) {
          shownSnippetTotalLength += renderSpan.text.length;
        }
      }

      // If there is more budget, sort the rest of the spans by the snippet score and add until we
      // reach the budget.
      const belowThresholdSpans: RenderSpan[] = renderSpans
        .filter(renderSpan => !renderSpan.isShownSnippet)
        .sort((a, b) => b.snippetScore - a.snippetScore);
      for (const renderSpan of belowThresholdSpans) {
        renderSpan.isShownSnippet = true;
        belowThresholdSpans.push(renderSpan);
        shownSnippetTotalLength += renderSpan.text.length;
        if (shownSnippetTotalLength > SNIPPET_LEN_BUDGET) {
          break;
        }
      }

      for (const [i, renderSpan] of renderSpans.entries()) {
        if (renderSpan.isShownSnippet) {
          snippetSpans.push({
            renderSpan,
            isShown: true
          });
        } else {
          const isLeftEllipsis = renderSpans[i + 1]?.isShownSnippet === true;
          const isRightEllipsis = renderSpans[i - 1]?.isShownSnippet === true;
          const isPreviousShown = snippetSpans[snippetSpans.length - 1]?.isShown === true;
          snippetSpans.push({
            renderSpan,
            isShown: false,
            isEllipsis: (isLeftEllipsis || isRightEllipsis) && isPreviousShown,
            hasNewline: renderSpan.text.includes('\n')
          });
          someSnippetsHidden = true;
        }
      }
    }
  }

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
          itemScrollContainer: $itemScrollContainer
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
        on:mouseleave={() => spanMouseLeave(renderSpan)}
        on:keydown={e => {
          if (e.key == 'Enter') {
            if (renderSpan.originalSpans != null && visibleSpanFields.length > 0)
              selectedSpan = renderSpan;
          }
        }}
        on:click={e => {
          if (renderSpan.originalSpans != null && visibleSpanFields.length > 0)
            selectedSpan = renderSpan;
          spanClickMousePosition = {x: e.offsetX, y: e.offsetY};
        }}>{renderSpan.snippetText}</span
      >
    {:else if snippetSpan.isEllipsis}<span
        use:hoverTooltip={{
          text: 'Some text was hidden to improve readability. \nClick "Show all" to show the entire document.'
        }}
        class="highlight-span text-sm leading-5">...</span
      >{#if snippetSpan.hasNewline}<span><br /></span>{/if}
    {/if}
  {/each}
  {#if selectedSpanDetails != null}
    <StringSpanDetails
      details={selectedSpanDetails}
      clickPosition={spanClickMousePosition}
      on:close={() => {
        selectedSpan = undefined;
      }}
      on:click={() => {
        selectedSpan = undefined;
      }}
    />
  {/if}
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
