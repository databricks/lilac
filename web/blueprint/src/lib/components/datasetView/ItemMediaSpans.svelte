<script lang="ts">
  /**
   * Component that renders string spans as an absolute positioned
   * layer, meant to be rendered on top of the source text.
   */
  import type * as Monaco from 'monaco-editor/esm/vs/editor/editor.api';
  import {onDestroy, onMount} from 'svelte';

  import {MONACO_LANGUAGE, getMonaco, registerHoverProvider} from '$lib/monaco';
  import {editConceptMutation} from '$lib/queries/conceptQueries';
  import type {DatasetViewStore} from '$lib/stores/datasetViewStore';
  import {conceptLink} from '$lib/utils';
  import {getSearches, mergeSpans, type MergedSpan} from '$lib/view_utils';
  import {
    L,
    getValueNodes,
    pathIncludes,
    pathIsEqual,
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
  import type {SpanDetails} from './StringSpanDetails.svelte';
  import {
    getMonacoRenderSpans,
    getRenderSpans,
    type RenderSpan,
    type RenderSpan2,
    type SpanValueInfo
  } from './spanHighlight';

  export let text: string;
  // The full row item.
  export let row: LilacValueNode;
  export let field: LilacField | undefined = undefined;
  // Path of the spans for this item to render.
  export let spanPaths: Path[];
  // Path has resolved wildcards.
  export let path: Path | undefined = undefined;

  // Information about each value under span paths to render.
  export let valuePaths: SpanValueInfo[];
  export let markdown = false;
  export let embeddings: string[];

  // When defined, enables semantic search on spans.
  export let datasetViewStore: DatasetViewStore | undefined = undefined;
  export let isExpanded = false;
  // Passed back up to the parent.
  export let textIsOverBudget = false;

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

  let spanPathToValueInfos: Record<string, SpanValueInfo[]> = {};
  $: {
    spanPathToValueInfos = {};
    for (const valuePath of valuePaths) {
      const spanPathStr = serializePath(valuePath.spanPath);
      if (spanPathToValueInfos[spanPathStr] == null) {
        spanPathToValueInfos[spanPathStr] = [];
      }
      spanPathToValueInfos[spanPathStr].push(valuePath);
    }
  }

  $: console.log(pathToSpans);

  // Merge all the spans for different features into a single span array.
  $: mergedSpans = mergeSpans(text, pathToSpans);

  // Span hover tracking.
  let pathsHovered: Set<string> = new Set();

  $: renderSpans = getRenderSpans(mergedSpans, spanPathToValueInfos, pathsHovered);

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
      const conceptValues = (spanPathToValueInfos[spanPath] || []).filter(
        v => v.type === 'concept_score'
      );
      for (const conceptValue of conceptValues) {
        // Only use the first concept. We will later support multiple concepts.
        const signal = conceptValue.signal as ConceptSignal;
        spanDetails.conceptName = signal.concept_name;
        spanDetails.conceptNamespace = signal.namespace;
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

  const MAX_MONACO_HEIGHT_COLLAPSED = 360;
  const MAX_MONACO_HEIGHT_EXPANDED = 720;

  let editorContainer: HTMLElement;
  let elementRoot: HTMLElement;

  let monaco: typeof Monaco;
  let editor: Monaco.editor.IStandaloneCodeEditor;

  $: {
    if (isExpanded != null || row != null) {
      relayout();
    }
  }

  function relayout() {
    if (editor != null && editor.getModel() != null) {
      const contentHeight = editor.getContentHeight();
      textIsOverBudget = contentHeight > MAX_MONACO_HEIGHT_COLLAPSED;

      console.log(editorContainer);

      if (isExpanded || !textIsOverBudget) {
        editorContainer.style.height = `${Math.min(contentHeight, MAX_MONACO_HEIGHT_EXPANDED)}px`;
      } else {
        editorContainer.style.height = MAX_MONACO_HEIGHT_COLLAPSED + 'px';
      }
      console.log(editorContainer.offsetWidth);

      editor.layout();
      monaco.editor.remeasureFonts();
    }
  }

  onMount(async () => {
    monaco = await getMonaco();
    // new ResizeObserver(() => console.log('CHANGED')).observe(elementRoot);
    console.log('CONTAINER WIDTH', editorContainer.offsetWidth);

    editor = monaco.editor.create(editorContainer, {
      fontFamily: 'Inconsolata',
      fontSize: 14,
      readOnly: true,
      lineNumbers: 'off',
      renderFinalNewline: 'dimmed',
      lineDecorationsWidth: 0,
      // glyphMargin: true,
      folding: false,
      // lineNumbersMinChars: 3,
      roundedSelection: true,
      domReadOnly: true,
      scrollBeyondLastLine: false,
      wordWrap: 'on',
      wrappingStrategy: 'advanced',
      readOnlyMessage: {value: ''},
      scrollbar: {
        verticalScrollbarSize: 8,
        alwaysConsumeMouseWheel: false
      },
      // fixedOverflowWidgets: true,
      minimap: {
        enabled: true,
        side: 'right'
      },
      language: MONACO_LANGUAGE,
      automaticLayout: true
    });
  });

  $: monacoSpans = getMonacoRenderSpans(text, pathToSpans, spanPathToValueInfos);

  let model: Monaco.editor.ITextModel | null = null;
  $: {
    if (editor != null && text != null) {
      model = monaco.editor.createModel(text, MONACO_LANGUAGE);
      // Register the hover provider. We will get called back when the user hovers over a span.
      registerHoverProvider(model, (model, position) => {
        const charOffset = model.getOffsetAt(position);

        const matchedSpans: RenderSpan2[] = [];
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

        function queryPreview(query: string) {
          const maxQueryLengthChars = 40;
          return query.length > maxQueryLengthChars
            ? query.slice(0, maxQueryLengthChars) + '...'
            : query;
        }
        const hoverContents: Monaco.IMarkdownString[] = matchedSpans.flatMap(renderSpan => {
          const namedValue = renderSpan.namedValue;
          const title = namedValue.info.name;

          if (renderSpan.isConceptSearch) {
            const signal = namedValue.info.signal as ConceptSignal;
            const link =
              window.location.origin + conceptLink(signal.namespace, signal.concept_name);
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
      });
      editor.setModel(model);
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

  // Add highlighting to the editor.
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
    monaco?.editor.getModels().forEach(model => model.dispose());
    editor?.dispose();
  });
</script>

<div bind:this={elementRoot}>
  <div class="editor-container h-64" bind:this={editorContainer} />
</div>

<style lang="postcss">
  .text-preview-overlay {
    mask-image: linear-gradient(to top, transparent, white 75px);
  }
  .highlight-span {
    /** Add a tiny bit of padding so that the hover doesn't flicker between rows. */
    padding-top: 1.5px;
    padding-bottom: 1.5px;
  }
  :global(.keyword-search-decoration) {
    cursor: pointer;
    @apply py-0.5 font-extrabold !text-violet-500 underline;
  }
  :global(.concept-search-decoration, .semantic-search-decoration) {
    cursor: pointer;
    @apply bg-blue-50 py-0.5 !text-black;
  }
  :global(.myLineDecoration) {
    border: 1px solid red;
    border-radius: 10px;
    margin: 0 3px;
  }
  :global(.monaco-menu span[aria-label='Command Palette']) {
    display: none;
  }
</style>
