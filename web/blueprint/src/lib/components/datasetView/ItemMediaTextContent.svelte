<script lang="ts">
  /**
   * Component that renders string spans as an absolute positioned
   * layer, meant to be rendered on top of the source text.
   */
  import type * as Monaco from 'monaco-editor/esm/vs/editor/editor.api';
  import {onDestroy, onMount} from 'svelte';

  import {
    MAX_MONACO_HEIGHT_COLLAPSED,
    MAX_MONACO_HEIGHT_EXPANDED,
    MONACO_LANGUAGE,
    MONACO_OPTIONS,
    getMonaco,
    registerHoverProvider,
    removeHoverProvider
  } from '$lib/monaco';
  import {editConceptMutation} from '$lib/queries/conceptQueries';
  import type {DatasetViewStore} from '$lib/stores/datasetViewStore';
  import {conceptLink} from '$lib/utils';
  import {getSearches} from '$lib/view_utils';
  import {
    L,
    getValueNodes,
    pathIncludes,
    pathMatchesPrefix,
    serializePath,
    type ConceptSignal,
    type LilacField,
    type LilacValueNode,
    type LilacValueNodeCasted,
    type Path,
    type SemanticSimilaritySignal,
    type SubstringSignal
  } from '$lilac';
  import {getMonacoRenderSpans, type MonacoRenderSpan, type SpanValueInfo} from './spanHighlight';
  export let text: string;
  // The full row item.
  export let row: LilacValueNode;
  export let field: LilacField | undefined = undefined;
  // Path of the spans for this item to render.
  export let spanPaths: Path[];
  // Path has resolved wildcards.
  export let path: Path | undefined = undefined;
  export let hidden: boolean;
  // Information about each value under span paths to render.
  export let spanValueInfos: SpanValueInfo[];
  export let embeddings: string[];

  // When defined, enables semantic search on spans.
  export let datasetViewStore: DatasetViewStore | undefined = undefined;
  export let isExpanded = false;
  // Passed back up to the parent.
  export let textIsOverBudget = false;

  // Map paths from the searches to the spans that they refer to.
  let pathToSpans: {
    [path: string]: LilacValueNodeCasted<'string_span'>[];
  };
  $: {
    pathToSpans = {};
    spanPaths.forEach(sp => {
      let valueNodes = getValueNodes(row, sp);
      const isSpanNestedUnder = pathMatchesPrefix(sp, path);
      if (isSpanNestedUnder) {
        // Filter out any span values that do not share the same coordinates as the current path we
        // are rendering.
        valueNodes = valueNodes.filter(v => pathIncludes(L.path(v), path) || path == null);
      }
      pathToSpans[serializePath(sp)] = valueNodes as LilacValueNodeCasted<'string_span'>[];
    });
  }

  // Map each of the span paths from the search (generic) to the concrete value infos for the row.
  let spanPathToValueInfos: Record<string, SpanValueInfo[]> = {};
  $: {
    spanPathToValueInfos = {};
    for (const spanValueInfo of spanValueInfos) {
      const spanPathStr = serializePath(spanValueInfo.spanPath);
      if (spanPathToValueInfos[spanPathStr] == null) {
        spanPathToValueInfos[spanPathStr] = [];
      }
      spanPathToValueInfos[spanPathStr].push(spanValueInfo);
    }
  }

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

  let editorContainer: HTMLElement;

  let monaco: typeof Monaco;
  let editor: Monaco.editor.IStandaloneCodeEditor;
  let model: Monaco.editor.ITextModel | null = null;

  $: {
    if (isExpanded != null || row != null) {
      relayout();
    }
  }

  function relayout() {
    if (editor != null && editor.getModel() != null) {
      const contentHeight = editor.getContentHeight();
      textIsOverBudget = contentHeight > MAX_MONACO_HEIGHT_COLLAPSED;

      if (isExpanded || !textIsOverBudget) {
        editorContainer.style.height = `${Math.min(contentHeight, MAX_MONACO_HEIGHT_EXPANDED)}px`;
      } else {
        editorContainer.style.height = MAX_MONACO_HEIGHT_COLLAPSED + 'px';
      }

      editor.layout();
      monaco.editor.remeasureFonts();
    }
  }

  onMount(async () => {
    monaco = await getMonaco();

    editor = monaco.editor.create(editorContainer, {
      ...MONACO_OPTIONS,
      lineNumbers: 'off',
      minimap: {
        enabled: true,
        side: 'right',
        scale: 2
      }
    });
  });

  $: monacoSpans = getMonacoRenderSpans(text, pathToSpans, spanPathToValueInfos);

  // Returns a preview of the query for the hover card.
  function queryPreview(query: string) {
    const maxQueryLengthChars = 40;
    return query.length > maxQueryLengthChars ? query.slice(0, maxQueryLengthChars) + '...' : query;
  }

  // Returns the hover content for the given position in the editor by searching through the render
  // spans for the relevant span.
  function getHoverCard(
    model: Monaco.editor.ITextModel,
    position: Monaco.Position
  ): Monaco.languages.ProviderResult<Monaco.languages.Hover> {
    const charOffset = model.getOffsetAt(position);

    // Matched spans are spans that are within the hover position.
    const matchedSpans: MonacoRenderSpan[] = [];
    for (const renderSpan of monacoSpans) {
      const span = L.span(renderSpan.span)!;
      // Ignore non-highlighted spans.
      if (span == null || !renderSpan.isHighlighted) continue;

      // Only show the hover if the mouse is over the span.
      if (span.start <= charOffset && charOffset <= span.end) {
        matchedSpans.push(renderSpan);
      }
    }

    // Don't show a hover card when no spans are matched.
    if (matchedSpans.length === 0) return null;

    // Map the render spans to their hover card components.
    const hoverContents: Monaco.IMarkdownString[] = matchedSpans.flatMap(renderSpan => {
      const namedValue = renderSpan.namedValue;
      const title = namedValue.info.name;

      if (renderSpan.isConceptSearch) {
        const signal = namedValue.info.signal as ConceptSignal;
        const link = window.location.origin + conceptLink(signal.namespace, signal.concept_name);
        const value = (namedValue.value as number).toFixed(2);
        return [
          {
            value: `**concept** <a href="${link}">${title}</a> (${value})`,
            supportHtml: true,
            isTrusted: true
          },
          {
            value: `<span>${renderSpan.text}</span>`,
            supportHtml: true,
            isTrusted: true
          }
        ];
      } else if (renderSpan.isSemanticSearch) {
        const signal = namedValue.info.signal as SemanticSimilaritySignal;
        const value = (namedValue.value as number).toFixed(2);
        const query = queryPreview(signal.query);
        return [
          {
            value: `**more like this** *${query}* (${value})`,
            supportHtml: true,
            isTrusted: true
          },
          {
            value: `<span>${renderSpan.text}</span>`,
            supportHtml: true,
            isTrusted: true
          }
        ];
      } else if (renderSpan.isKeywordSearch) {
        const signal = namedValue.info.signal as SubstringSignal;
        const query = queryPreview(signal.query);
        return [
          {
            value: `**keyword search** *${query}*`,
            supportHtml: true,
            isTrusted: true
          },
          {
            value: `<span>${renderSpan.text}</span>`,
            supportHtml: true,
            isTrusted: true
          }
        ];
      }
      return [];
    });

    return {
      contents: hoverContents
    };
  }

  $: {
    if (editor != null && text != null) {
      model = monaco.editor.createModel(text, MONACO_LANGUAGE);
      editor.setModel(model);

      // Register the hover provider. We will get called back when the user hovers over a span.
      registerHoverProvider(model, (model, position) => getHoverCard(model, position));

      relayout();

      editor.onDidChangeModel(() => {
        relayout();
      });
    }
  }
  $: searches = $datasetViewStore != null ? getSearches($datasetViewStore, null) : null;

  // Gets the current editors highlighted text a string.
  function getEditorSelection(): string | null {
    if (editor == null) return null;
    const selection = editor.getSelection();
    if (selection == null) return null;
    const value = model!.getValueInRange(selection);
    return value;
  }

  // Add the concept actions to the right-click menu.
  $: {
    if (editor != null && searches != null) {
      for (const search of searches) {
        if (search.type == 'concept') {
          const idAdd = `add-positive-to-concept-${search.concept_name}`;
          if (editor.getAction(idAdd) != null) continue;
          editor.addAction({
            id: idAdd,
            label: `👍 add as positive to concept "${search.concept_name}"`,
            contextMenuGroupId: 'navigation_concepts',
            run: () => {
              const selection = getEditorSelection();
              if (selection == null) return;

              const label = true;
              addConceptLabel(search.concept_namespace, search.concept_name, selection, label);
            }
          });
          editor.addAction({
            id: 'add-negative-to-concept',
            label: `👎 add as negative to concept "${search.concept_name}"`,
            contextMenuGroupId: 'navigation_concepts',
            run: () => {
              const selection = getEditorSelection();
              if (selection == null) return;

              const label = false;
              addConceptLabel(search.concept_namespace, search.concept_name, selection, label);
            }
          });
        }
      }
    }
  }

  // Add the search actions to the right-click menu.
  $: {
    if (editor != null && embeddings != null) {
      for (const embedding of embeddings) {
        const idEmbedding = `find-similar-${embedding}`;
        if (editor.getAction(idEmbedding) != null) continue;
        editor.addAction({
          id: idEmbedding,
          label: `🔍 More like this` + (embeddings.length > 1 ? ` with ${embedding}` : ''),
          contextMenuGroupId: 'navigation_searches',
          run: () => {
            if (datasetViewStore == null || field == null) return;
            const selection = getEditorSelection();
            if (selection == null) return;

            datasetViewStore.addSearch({
              path: field.path,
              type: 'semantic',
              query_type: 'document',
              query: selection,
              embedding
            });
          }
        });
      }
      const idKeyword = 'keyword-search';
      if (editor.getAction(idKeyword) == null) {
        editor.addAction({
          id: idKeyword,
          label: '🔍 Keyword search',
          contextMenuGroupId: 'navigation_searches',
          run: () => {
            if (datasetViewStore == null || field == null) return;
            const selection = getEditorSelection();
            if (selection == null) return;

            datasetViewStore.addSearch({
              path: field.path,
              type: 'keyword',
              query: selection
            });
          }
        });
      }
    }
  }

  // Add highlighting to the editor based on searches.
  $: {
    if (editor != null && model != null) {
      editor.createDecorationsCollection(
        monacoSpans.flatMap(renderSpan => {
          if (!renderSpan.isHighlighted || model == null) {
            return [];
          }
          const span = L.span(renderSpan.span)!;
          const startPosition = model.getPositionAt(span.start);
          const endPosition = model.getPositionAt(span.end);
          if (startPosition == null || endPosition == null) {
            return [];
          }

          const classNames: string[] = [];
          if (renderSpan.isKeywordSearch) {
            classNames.push('keyword-search-decoration');
          }
          if (renderSpan.isConceptSearch) {
            classNames.push('concept-search-decoration');
          }
          if (renderSpan.isSemanticSearch) {
            classNames.push('semantic-search-decoration');
          }

          return [
            {
              range: new monaco.Range(
                startPosition.lineNumber,
                startPosition.column,
                endPosition.lineNumber,
                endPosition.column
              ),
              options: {inlineClassName: classNames.join(' ')}
            }
          ];
        })
      );
    }
  }

  onDestroy(() => {
    if (model != null) {
      // Clean up the hover provider to avoid memory leaks.
      removeHoverProvider(model);
      model.dispose();
    }

    editor?.dispose();
  });
</script>

<!-- For reasons unknown to me, the -ml-6 is required to make the autolayout of monaco react. -->
<div class="relative -ml-6 flex h-fit w-full flex-col gap-x-4">
  <div class="ml-6 h-64" class:hidden bind:this={editorContainer} />
</div>

<style lang="postcss">
  :global(.keyword-search-decoration) {
    cursor: pointer;
    @apply py-0.5 font-extrabold !text-violet-500 underline;
  }
  :global(.concept-search-decoration, .semantic-search-decoration) {
    cursor: pointer;
    @apply bg-blue-50 py-0.5 !text-black;
  }
</style>
