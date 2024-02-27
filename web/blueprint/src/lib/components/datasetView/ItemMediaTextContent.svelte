<script lang="ts">
  /**
   * Component that renders string spans as an absolute positioned
   * layer, meant to be rendered on top of the source text.
   */
  import {conceptIdentifier, conceptLink} from '$lib/utils';
  import type * as Monaco from 'monaco-editor/esm/vs/editor/editor.api';
  import {onDestroy, onMount} from 'svelte';

  import {
    DEFAULT_HEIGHT_PEEK_SCROLL_PX,
    DEFAULT_HEIGHT_PEEK_SINGLE_ITEM_PX,
    MAX_MONACO_HEIGHT_COLLAPSED,
    MONACO_OPTIONS,
    getMonaco
  } from '$lib/monaco';
  import {editConceptMutation, queryConcepts} from '$lib/queries/conceptQueries';
  import type {DatasetViewStore} from '$lib/stores/datasetViewStore';
  import {getNotificationsContext} from '$lib/stores/notificationsStore';
  import {getSearches} from '$lib/view_utils';
  import {
    L,
    getValueNodes,
    pathIncludes,
    pathIsEqual,
    pathMatchesPrefix,
    serializePath,
    type ConceptSignal,
    type DatasetUISettings,
    type LilacField,
    type LilacValueNode,
    type LilacValueNodeCasted,
    type Path,
    type SemanticSimilaritySignal,
    type SubstringSignal
  } from '$lilac';
  import {
    ComposedModal,
    ModalBody,
    ModalFooter,
    ModalHeader,
    SkeletonText,
    TextArea,
    Toggle
  } from 'carbon-components-svelte';
  import type {
    DropdownItem,
    DropdownItemId
  } from 'carbon-components-svelte/types/Dropdown/Dropdown.svelte';
  import {derived} from 'svelte/store';
  import DropdownPill from '../common/DropdownPill.svelte';
  import {getMonacoRenderSpans, type MonacoRenderSpan, type SpanValueInfo} from './spanHighlight';
  export let text: string | null | undefined;
  // The full row item.
  export let row: LilacValueNode | undefined | null;
  export let field: LilacField | undefined = undefined;
  // Path of the spans for this item to render.
  export let spanPaths: Path[];
  // Path has resolved wildcards.
  export let path: Path | undefined = undefined;
  export let hidden: boolean;
  // Information about each value under span paths to render.
  export let spanValueInfos: SpanValueInfo[];
  export let embeddings: string[];
  export let datasetViewStore: DatasetViewStore | undefined = undefined;
  export let isExpanded = false;
  // Passed back up to the parent.
  export let textIsOverBudget = false;
  export let viewType: DatasetUISettings['view_type'] | undefined = undefined;
  export let datasetViewHeight: number | undefined = undefined;
  export let isFetching: boolean | undefined = undefined;

  // Map paths from the searches to the spans that they refer to.
  let pathToSpans: {
    [path: string]: LilacValueNodeCasted<'string_span'>[];
  };
  $: {
    pathToSpans = {};
    (spanPaths || []).forEach(sp => {
      if (row == null) return;
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

  // True after the editor has remeasured fonts and ready to render. When false, the monaco element
  // is visibility: hidden.
  let editorReady = false;

  // Map each of the span paths from the search (generic) to the concrete value infos for the row.
  let spanPathToValueInfos: Record<string, SpanValueInfo[]> = {};
  $: {
    spanPathToValueInfos = {};
    for (const spanValueInfo of spanValueInfos || []) {
      const spanPathStr = serializePath(spanValueInfo.spanPath);
      if (spanPathToValueInfos[spanPathStr] == null) {
        spanPathToValueInfos[spanPathStr] = [];
      }
      spanPathToValueInfos[spanPathStr].push(spanValueInfo);
    }
  }

  const notificationStore = getNotificationsContext();
  const conceptEdit = editConceptMutation();
  const addConceptLabel = (
    conceptNamespace: string,
    conceptName: string,
    text: string,
    label: boolean
  ) => {
    if (!conceptName || !conceptNamespace)
      throw Error('Label could not be added, no active concept.');
    $conceptEdit.mutate([conceptNamespace, conceptName, {insert: [{text, label}]}], {
      onSuccess: () => {
        notificationStore.addNotification({
          kind: 'success',
          title: `Added ${
            label ? 'positive' : 'negative'
          } example to concept ${conceptNamespace}/${conceptName}`,
          message: text
        });
      }
    });
  };

  let editorContainer: HTMLElement;

  let monaco: typeof Monaco;
  let editor: Monaco.editor.IStandaloneCodeEditor | null = null;
  let model: Monaco.editor.ITextModel | null = null;

  $: {
    if (isExpanded != null || row != null) {
      relayout();
    }
  }

  $: maxMonacoHeightCollapsed = datasetViewHeight
    ? datasetViewHeight -
      (viewType === 'scroll' ? DEFAULT_HEIGHT_PEEK_SCROLL_PX : DEFAULT_HEIGHT_PEEK_SINGLE_ITEM_PX)
    : MAX_MONACO_HEIGHT_COLLAPSED;

  function relayout() {
    if (editorContainer != null && editor != null && editor.getModel() != null) {
      const contentHeight = editor.getContentHeight();
      textIsOverBudget = contentHeight > maxMonacoHeightCollapsed;

      if (isExpanded) {
        editorContainer.style.height = contentHeight + 'px';
      } else if (!textIsOverBudget) {
        editorContainer.style.height = `${Math.min(contentHeight, maxMonacoHeightCollapsed)}px`;
      } else {
        editorContainer.style.height = maxMonacoHeightCollapsed + 'px';
      }

      editor.layout();
    }
  }

  onMount(async () => {
    if (monaco != null) return;
    monaco = await getMonaco();
    if (editorContainer == null) return;
    editor = monaco.editor.create(editorContainer, {
      ...MONACO_OPTIONS,
      lineNumbers: 'on',
      // GlyphMargins are off because they cause an issue where the minimap overlaps the text.
      glyphMargin: false,
      lineNumbersMinChars: 3,
      renderLineHighlight: 'none',
      minimap: {
        enabled: true,
        side: 'right',
        scale: 2
      }
    });
    model = monaco.editor.createModel(text || '', 'text/plain');
    editor.setModel(model);

    // When the fonts are ready, measure the fonts and display the editor after the font measurement
    // is complete. This is very important, otherwise the cursor will get shifted slightly,
    // breaking all user selection.
    document.fonts.ready.then(() => {
      monaco.editor.remeasureFonts();
      editorReady = true;
    });
  });

  // When text changes, set the value on the global model and relayout.
  $: {
    if (editorContainer != null && model != null && text != null) {
      model.setValue(text);
      relayout();
    }
  }

  $: monacoSpans = getMonacoRenderSpans(text || '', pathToSpans, spanPathToValueInfos);

  // Reveal the first span so that it is near the top of the view.
  $: {
    if (model != null && editor != null) {
      let minPosition: Monaco.Position | null = null;
      for (const renderSpan of monacoSpans || []) {
        const span = L.span(renderSpan.span)!;
        const position = model.getPositionAt(span.start);

        if (minPosition == null) {
          minPosition = position;
        } else {
          if (position.lineNumber < minPosition.lineNumber) {
            minPosition = position;
          }
        }
      }
      if (minPosition != null) {
        editor.revealPositionNearTop(minPosition);
      }
    }
  }

  // Returns a preview of the query for the hover card.
  function queryPreview(query: string) {
    const maxQueryLengthChars = 40;
    return query.length > maxQueryLengthChars ? query.slice(0, maxQueryLengthChars) + '...' : query;
  }

  // Returns the hover content for the given position in the editor by searching through the render
  // spans for the relevant span.
  function getHoverCard(renderSpan: MonacoRenderSpan): Monaco.IMarkdownString[] {
    if (model == null) {
      return [];
    }
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
          value: renderSpan.text,
          supportHtml: false,
          isTrusted: false
        }
      ];
    } else if (renderSpan.isSemanticSearch) {
      const signal = namedValue.info.signal as SemanticSimilaritySignal;
      const value = (namedValue.value as number).toFixed(2);
      const query = queryPreview(signal.query);
      return [
        {
          value: `**more like this** *${query}*`,
          supportHtml: true,
          isTrusted: true
        },
        {
          value: `similarity: ${value}`,
          supportHtml: true,
          isTrusted: true
        },
        {
          value: renderSpan.text,
          supportHtml: false,
          isTrusted: false
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
          value: renderSpan.text,
          supportHtml: false,
          isTrusted: false
        }
      ];
    } else if (renderSpan.isLeafSpan) {
      return [
        {
          value: `**span** *${serializePath(namedValue.info.path)}*`,
          supportHtml: true,
          isTrusted: true
        },
        ...(namedValue.value != null
          ? [
              {
                value: `value: *${namedValue.value}*`,
                supportHtml: false,
                isTrusted: false
              }
            ]
          : []),
        {
          value: renderSpan.text,
          supportHtml: false,
          isTrusted: false
        }
      ];
    }
    return [];
  }

  $: searches = $datasetViewStore != null ? getSearches($datasetViewStore, null) : null;

  // Gets the current editors highlighted text a string.
  function getEditorSelection(): string | null {
    if (editor == null) return null;
    const selection = editor.getSelection();
    if (selection == null) return null;
    return model!.getValueInRange(selection);
  }

  function conceptActionKeyId(conceptNamespace: string, conceptName: string) {
    return `add-to-concept-${conceptNamespace}-${conceptName}`;
  }

  // Remember all of the context key conditions so we don't keep re-creating them.
  let contextKeys: {[key: string]: Monaco.editor.IContextKey} = {};
  $: {
    if (editor != null) {
      // Create conditions for concepts from searches. Always set all the values to false. They will get
      // reset below when searches are defined so we don't keep growing the actions.
      for (const contextKey of Object.values(contextKeys)) {
        contextKey.set(false);
      }

      // Set the conditions for each concept to true if they exist in the searches.
      for (const search of searches || []) {
        if (search.type != 'concept') continue;
        const actionKeyId = conceptActionKeyId(search.concept_namespace, search.concept_name);
        // Don't recreate the key if it exists.
        if (contextKeys[actionKeyId] == null) {
          const contextKey = editor.createContextKey(actionKeyId, true);
          contextKeys[actionKeyId] = contextKey;
        } else {
          contextKeys[actionKeyId].set(true);
        }
      }
    }
  }

  // Add to concept.
  let addToConceptText: string | undefined = undefined;
  function addToConceptTextChanged(e: Event) {
    addToConceptText = (e.target as HTMLInputElement).value;
  }
  let addToConceptSelectedConcept: string | undefined = undefined;

  let addToConceptPositive = true;
  function selectConceptFromModal(
    e: CustomEvent<{
      selectedId: DropdownItemId;
      selectedItem: DropdownItem;
    }>
  ) {
    addToConceptSelectedConcept = e.detail.selectedId;
  }
  function addToConceptFromModal() {
    if (addToConceptSelectedConcept == null || addToConceptText == null) return;
    const [conceptNamespace, conceptName] = addToConceptSelectedConcept.split('/');
    addConceptLabel(conceptNamespace, conceptName, addToConceptText, addToConceptPositive);
    addToConceptText = undefined;
  }

  const conceptQuery = queryConcepts();
  $: concepts = $conceptQuery.data;
  let conceptsInMenu: Set<string> = new Set();
  let addToConceptItems: DropdownItem[] = [];

  $: {
    if (concepts != null) {
      conceptsInMenu = new Set<string>();
      for (const concept of concepts) {
        if (concept.namespace == 'lilac') continue;
        conceptsInMenu.add(conceptIdentifier(concept.namespace, concept.name));
      }
      for (const search of searches || []) {
        if (search.type == 'concept') {
          conceptsInMenu.add(conceptIdentifier(search.concept_namespace, search.concept_name));
        }
      }
    }
    addToConceptItems = Array.from(conceptsInMenu).map(concept => ({
      id: concept,
      text: concept
    }));
  }

  // Add the concept actions to the right-click menu.
  $: {
    if (editor != null && concepts != null) {
      for (const concept of conceptsInMenu) {
        const [conceptNamespace, conceptName] = concept.split('/');
        const idPositive = `add-positive-to-concept-${conceptNamespace}/${conceptName}`;
        if (editor.getAction(idPositive) != null) continue;
        editor.addAction({
          id: idPositive,
          label: `👍 add as positive to concept "${conceptName}"`,
          contextMenuGroupId: 'navigation_concepts',
          precondition: conceptActionKeyId(conceptNamespace, conceptName),
          run: () => {
            const selection = getEditorSelection();
            if (selection == null) return;

            const label = true;
            addConceptLabel(conceptNamespace, conceptName, selection, label);
          }
        });
        const idNegative = `add-negative-to-concept-${conceptNamespace}/${conceptName}`;
        if (editor.getAction(idNegative) != null) continue;
        editor.addAction({
          id: idNegative,
          label: `👎 add as negative to concept "${conceptName}"`,
          contextMenuGroupId: 'navigation_concepts',
          precondition: conceptActionKeyId(conceptNamespace, conceptName),
          run: () => {
            const selection = getEditorSelection();
            if (selection == null) return;

            const label = false;
            addConceptLabel(conceptNamespace, conceptName, selection, label);
          }
        });
      }
    }
  }
  $: {
    if (editor != null) {
      const idAddToConcept = 'add-to-concept';
      if (editor.getAction(idAddToConcept) == null) {
        editor.addAction({
          id: 'add-to-concept',
          label: `➕ Add to concept`,
          contextMenuOrder: 1000,
          contextMenuGroupId: 'navigation_concepts',
          run: () => {
            const selection = getEditorSelection();
            if (selection == null) return;
            addToConceptSelectedConcept = addToConceptItems[0].id;
            addToConceptText = selection;
          }
        });
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

  // Get position information from the URL for deep-linking. The derived store will only retrieve
  // line numbers and column selections for this path and row id.
  const urlSelection =
    datasetViewStore != null
      ? derived(datasetViewStore, $datasetViewStore => {
          if ($datasetViewStore.selection == null) return null;
          const [selectionPath, selection] = $datasetViewStore.selection;
          if (!pathIsEqual(selectionPath, path)) return null;

          return selection;
        })
      : null;

  let spanDecorations: Monaco.editor.IModelDeltaDecoration[] = [];

  // Add highlighting to the editor based on searches.
  $: {
    if (editor != null && model != null) {
      spanDecorations = monacoSpans.flatMap(renderSpan => {
        if (model == null) {
          return [];
        }
        const span = L.span(renderSpan.span)!;
        const startPosition = model.getPositionAt(span.start);
        const endPosition = model.getPositionAt(span.end);
        if (startPosition == null || endPosition == null) {
          return [];
        }

        const spanDecorations: Monaco.editor.IModelDeltaDecoration[] = [];

        const hoverCard = getHoverCard(renderSpan);

        const range = new monaco.Range(
          startPosition.lineNumber,
          startPosition.column,
          endPosition.lineNumber,
          endPosition.column
        );

        // Map the score to a class.
        let bgScoreClass = '';
        if (renderSpan.isConceptSearch || renderSpan.isSemanticSearch) {
          const score = renderSpan.value as number;
          if (score < 0.55) {
            bgScoreClass = 'bg-blue-50';
          } else if (score < 0.6) {
            bgScoreClass = 'bg-blue-100';
          } else if (score < 0.7) {
            bgScoreClass = 'bg-blue-200';
          } else if (score < 0.8) {
            bgScoreClass = 'bg-blue-300';
          } else if (score < 0.9) {
            bgScoreClass = 'bg-blue-400';
          } else {
            bgScoreClass = 'bg-blue-500';
          }
        }

        if (renderSpan.isKeywordSearch) {
          spanDecorations.push({
            range,
            options: {
              className: 'keyword-search-bg',
              inlineClassName: 'keyword-search-text',
              hoverMessage: hoverCard,
              glyphMarginClassName: 'keyword-search-glyph',
              glyphMarginHoverMessage: hoverCard,
              isWholeLine: false,
              minimap: {
                position: monaco.editor.MinimapPosition.Inline,
                color: '#888888'
              }
            }
          });
        } else if (renderSpan.isConceptSearch) {
          spanDecorations.push({
            range,
            options: {
              className: 'concept-search-bg ' + bgScoreClass,
              inlineClassName: 'concept-search-text',
              hoverMessage: hoverCard,
              glyphMarginClassName: 'concept-search-bg',
              glyphMarginHoverMessage: hoverCard,
              isWholeLine: false,
              minimap: {
                position: monaco.editor.MinimapPosition.Inline,
                color: '#dbeafe' // bg-blue-200 from tailwind
              }
            }
          });
        } else if (renderSpan.isSemanticSearch) {
          spanDecorations.push({
            range,
            options: {
              className: 'semantic-search-bg ' + bgScoreClass,
              inlineClassName: 'semantic-search-text',
              hoverMessage: hoverCard,
              glyphMarginClassName: 'semantic-search-bg',
              glyphMarginHoverMessage: hoverCard,
              isWholeLine: false,
              minimap: {
                position: monaco.editor.MinimapPosition.Inline,
                color: '#dbeafe' // bg-blue-200 from tailwind
              }
            }
          });
        } else if (renderSpan.isMetadata) {
          spanDecorations.push({
            range,
            options: {
              className: 'leaf-bg',
              inlineClassName: 'leaf-text',
              hoverMessage: hoverCard,
              glyphMarginClassName: 'leaf-glyph',
              glyphMarginHoverMessage: hoverCard,
              isWholeLine: false,
              minimap: {
                position: monaco.editor.MinimapPosition.Inline,
                color: '#888888'
              }
            }
          });
        }
        return spanDecorations;
      });
    }
  }

  /**
   * Deep linking.
   */
  // Add highlighting to the editor based on URL deep-link selections.
  let deepLinkLineDecorations: Monaco.editor.IModelDeltaDecoration[] = [];
  $: {
    if (editor != null && model != null && urlSelection != null && $urlSelection != null) {
      // The background color of the full line is always present.
      deepLinkLineDecorations = [];
      if (
        $urlSelection.startLine == $urlSelection.endLine &&
        $urlSelection.startCol == $urlSelection.endCol
      ) {
        deepLinkLineDecorations.push({
          range: new monaco.Range(
            $urlSelection.startLine,
            $urlSelection.startCol,
            $urlSelection.endLine,
            $urlSelection.endCol || model.getLineMaxColumn($urlSelection.startLine)
          ),
          options: {
            isWholeLine: true,
            className: 'line-selection-bg',
            glyphMarginClassName: 'line-selection-glyph',
            glyphMarginHoverMessage: {value: '🔗 From the URL'}
          }
        });
      } else {
        // The specific selection highlighting is a darker color.
        deepLinkLineDecorations.push({
          range: new monaco.Range(
            $urlSelection.startLine,
            $urlSelection.startCol,
            $urlSelection.endLine,
            $urlSelection.endCol
          ),
          options: {
            className: 'line-col-selection-bg',
            hoverMessage: [{value: '🔗 From the URL'}],
            glyphMarginClassName: 'line-selection-glyph',
            glyphMarginHoverMessage: {value: '🔗 From the URL'},
            minimap: {
              position: monaco.editor.MinimapPosition.Inline,
              color: '#cccccc'
            }
          }
        });
      }

      editor.revealLineInCenter($urlSelection.startLine);
    }
  }

  // Add right-click menus for deep-linking.
  $: {
    if (model != null && editor != null && viewType != null && path != null) {
      const idLinkSelection = 'link-selection';
      if (editor.getAction(idLinkSelection) == null) {
        editor.addAction({
          id: idLinkSelection,
          label: '🔗 Copy link to selection',
          contextMenuGroupId: 'navigation_links',
          // We use ctrl/cmd + K to create a link, which is standard for hyperlinks.
          keybindings: [monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyK],
          run: () => {
            if (
              datasetViewStore == null ||
              path == null ||
              field == null ||
              editor == null ||
              model == null
            )
              return;

            const selection = editor.getSelection();
            if (selection == null) return;

            datasetViewStore.setTextSelection(path, {
              startLine: selection.startLineNumber,
              endLine: selection.endLineNumber,
              startCol: selection.startColumn,
              endCol: selection.endColumn
            });

            // Copy the URL to the clipboard after the store is updated.
            navigator.clipboard.writeText(location.href).then(null, () => {
              throw Error('Error copying URL to clipboard.');
            });

            editor.setSelection(selection);
          }
        });
      }
    }
  }

  $: {
    if ($urlSelection == null) {
      deepLinkLineDecorations = [];
    }
  }

  let decorationIds: string[] = [];
  $: {
    if (editor != null) {
      // deltaDecorations is deprecated, but it's currently the only API that supports resetting old
      // decorations. This is important for settings that can change from state from stores.
      decorationIds = editor.deltaDecorations(decorationIds, [
        ...spanDecorations,
        ...deepLinkLineDecorations
      ]);
      [decorationIds];
    }
  }
  onDestroy(() => {
    model?.dispose();
    editor?.dispose();
  });
</script>

<!-- For reasons unknown to me, the -ml-6 is required to make the autolayout of monaco react. -->
<div class="relative left-16 -ml-10 flex h-fit w-full flex-col gap-x-4 pr-6">
  {#if !editorReady}
    <div class="w-full"><SkeletonText class="ml-4 w-full " lines={3} /></div>
  {/if}
  <div
    class="editor-container h-64"
    class:hidden
    bind:this={editorContainer}
    class:invisible={!editorReady}
  />
  {#if isFetching}
    <!-- Transparent overlay when fetching rows. -->
    <div class="absolute inset-0 flex items-center justify-center bg-white bg-opacity-70" />
  {/if}
</div>

<div class="add-concept-modal">
  <ComposedModal
    size="sm"
    open={addToConceptText != null}
    selectorPrimaryFocus=".bx--btn--primary"
    on:submit={addToConceptFromModal}
    on:close={() => (addToConceptText = undefined)}
  >
    <ModalHeader title="Add to concept" />
    <ModalBody hasForm>
      <div class="flex w-full flex-col gap-y-8 pt-4">
        <section class="flex flex-col gap-y-4">
          <div class="text-md text-gray-700">Concept</div>
          <div class="flex flex-row items-center gap-x-4">
            <div>
              <DropdownPill
                title="Choose a concept"
                items={addToConceptItems}
                on:select={selectConceptFromModal}
                selectedId={addToConceptSelectedConcept}
                let:item
              >
                {@const groupByItem = addToConceptItems?.find(x => x === item)}
                {#if groupByItem}
                  <div class="flex items-center justify-between gap-x-1">
                    <span title={groupByItem.text} class="truncate text-sm">{groupByItem.text}</span
                    >
                  </div>
                {/if}
              </DropdownPill>
            </div>
            <div>
              <Toggle
                labelA={'Negative'}
                labelB={'Positive'}
                bind:toggled={addToConceptPositive}
                hideLabel
              />
            </div>
          </div>
        </section>
      </div>
      <div class="mt-8">
        <section class="flex flex-col gap-y-4">
          <div class="text-md text-gray-700">Text</div>

          <TextArea
            value={addToConceptText || undefined}
            on:input={addToConceptTextChanged}
            rows={6}
            placeholder="Enter text for the concept"
            class="mb-2 w-full "
          />
        </section>
      </div>
    </ModalBody>
    <ModalFooter
      primaryButtonText={'Save'}
      secondaryButtonText="Close"
      primaryButtonDisabled={addToConceptSelectedConcept == null}
      on:click:button--secondary={() => {
        addToConceptText = undefined;
      }}
    />
  </ComposedModal>
</div>

<style lang="postcss">
  /** Keyword search */
  :global(.keyword-search-bg) {
    @apply bg-amber-900 opacity-20;
  }
  :global(.keyword-search-glyph) {
    @apply border-r-8 border-amber-900 opacity-20;
  }
  :global(.keyword-search-text) {
    @apply font-extrabold text-violet-500 underline;
  }

  /** Concept and semantic search */
  :global(.concept-search-bg, .semantic-search-bg) {
    @apply bg-opacity-20;
  }
  :global(.concept-search-text, .semantic-search-text) {
    @apply text-black;
  }

  /** Spans from users (leaf spans) */
  :global(.leaf-bg) {
    @apply bg-orange-700 opacity-20;
  }
  :global(.leaf-glyph) {
    @apply border-r-8 border-orange-700 opacity-20;
  }
  :global(.leaf-text) {
    @apply text-violet-500;
  }

  /** Deep-linked selection */
  :global(.line-selection-bg) {
    @apply bg-gray-500 bg-opacity-20;
  }
  :global(.line-col-selection-bg) {
    @apply bg-gray-500 bg-opacity-20;
  }

  :global(.line-selection-glyph) {
    @apply border-r-8 border-gray-500 opacity-50;
  }

  :global(.editor-container .monaco-editor .lines-content.monaco-editor-background) {
    margin-left: 10px;
  }
  :global(.add-concept-modal .bx--modal-container) {
    @apply min-h-fit;
  }
</style>
