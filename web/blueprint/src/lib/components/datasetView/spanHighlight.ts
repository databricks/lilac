import type {MergedSpan} from '$lib/view_utils';
import {
  L,
  deserializePath,
  isNumeric,
  serializePath,
  valueAtPath,
  type DataType,
  type LilacValueNode,
  type LilacValueNodeCasted,
  type Path,
  type Signal
} from '$lilac';
import type {SpanHoverNamedValue} from './SpanHoverTooltip.svelte';
import {colorFromScore} from './colors';

// When the text length exceeds this number we start to snippet.
const SNIPPET_LEN_BUDGET = 300;
const SURROUNDING_SNIPPET_LEN = 50;

export interface SpanValueInfo {
  path: Path;
  spanPath: Path;
  name: string;
  type: 'concept_score' | 'label' | 'semantic_similarity' | 'keyword' | 'metadata' | 'leaf_span';
  dtype: DataType;
  signal?: Signal;
}

export interface RenderSpan {
  paths: string[];
  originalSpans: {[spanSet: string]: LilacValueNodeCasted<'string_span'>[]};

  backgroundColor: string;
  isBlackBolded: boolean;
  isHighlightBolded: boolean;

  // Whether this span needs to be shown as a snippet.
  isShownSnippet: boolean;
  snippetScore: number;
  // The text post-processed for snippets.
  snippetText: string;

  namedValues: SpanHoverNamedValue[];
  // Whether the hover matches any path in this render span. Used for highlighting.
  isHovered: boolean;
  // Whether this render span is the first matching span for the hovered span. This is used for
  // showing the tooltip only on the first matching path.
  isFirstHover: boolean;
}

export function getRenderSpans(
  mergedSpans: MergedSpan[],
  spanPathToValueInfos: Record<string, SpanValueInfo[]>,
  pathsHovered: Set<string>
): RenderSpan[] {
  const renderSpans: RenderSpan[] = [];
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

    // The named values only when the path is first seen (to power the hover tooltip).
    const firstNamedValues: SpanHoverNamedValue[] = [];
    // All named values.
    const namedValues: SpanHoverNamedValue[] = [];

    // Compute the maximum score for all original spans matching this render span to choose the
    // color.
    let maxScore = -Infinity;
    for (const [spanPathStr, originalSpans] of Object.entries(mergedSpan.originalSpans)) {
      const valueInfos = spanPathToValueInfos[spanPathStr];
      const spanPath = deserializePath(spanPathStr);
      if (valueInfos == null || valueInfos.length === 0) continue;

      for (const originalSpan of originalSpans) {
        for (const valueInfo of valueInfos) {
          const subPath = valueInfo.path.slice(spanPath.length);
          const valueNode = valueAtPath(originalSpan as LilacValueNode, subPath);
          if (valueNode == null) continue;

          const value = L.value(valueNode);
          const span = L.span(valueNode);
          if (value == null && span == null) continue;

          if (valueInfo.dtype === 'float32') {
            const floatValue = L.value<'float32'>(valueNode);
            if (floatValue != null) {
              maxScore = Math.max(maxScore, floatValue);
            }
          }

          // Add extra metadata. If this is a path that we've already seen before, ignore it as
          // the value will be rendered alongside the first path.
          const originalPath = serializePath(L.path(originalSpan as LilacValueNode)!);
          const pathSeen = !newPaths.includes(originalPath);

          const namedValue = {value, info: valueInfo, specificPath: L.path(valueNode)!};
          if (!pathSeen) {
            firstNamedValues.push(namedValue);
          }
          namedValues.push(namedValue);
          if (valueInfo.type === 'concept_score' || valueInfo.type === 'semantic_similarity') {
            if ((value as number) > 0.5) {
              isShownSnippet = true;
            }
          } else {
            isShownSnippet = true;
          }
        }
      }
    }

    const isLabeled = namedValues.some(v => v.info.type === 'label');
    const isLeafSpan = namedValues.some(v => v.info.type === 'leaf_span');
    const isKeywordSearch = namedValues.some(v => v.info.type === 'keyword');
    const hasNonNumericMetadata = namedValues.some(
      v => v.info.type === 'metadata' && !isNumeric(v.info.dtype)
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
      isBlackBolded: isKeywordSearch || hasNonNumericMetadata || isLeafSpan,
      isHighlightBolded: isLabeled,
      isShownSnippet,
      snippetScore: maxScore,
      namedValues: firstNamedValues,
      paths: mergedSpan.paths,
      snippetText: mergedSpan.text,
      originalSpans: mergedSpan.originalSpans,
      isHovered,
      isFirstHover
    });
  }
  return renderSpans;
}

export interface SnippetSpan {
  renderSpan: RenderSpan;
  // When the snippet is hidden, whether it should be replaced with ellipsis. We only do this once
  // for a continuous set of hidden snippets.
  isEllipsis?: boolean;
}

export function getSnippetSpans(
  renderSpans: RenderSpan[],
  isExpanded: boolean
): {snippetSpans: SnippetSpan[]; someSnippetsHidden: boolean} {
  if (isExpanded) {
    // If the span is expanded, we don't need to do any snippetting.
    return {
      snippetSpans: renderSpans.map(renderSpan => ({renderSpan, isShown: true})),
      someSnippetsHidden: false
    };
  }
  let someSnippetsHidden = false;
  // If the doc is not expanded, we need to do snippetting.
  const snippetSpans: SnippetSpan[] = [];
  for (let i = 0; i < renderSpans.length; i++) {
    const renderSpan = renderSpans[i];
    if (!renderSpan.isShownSnippet) {
      continue;
    }
    const prevRenderSpan: RenderSpan | null = renderSpans[i - 1] || null;
    const addLeftContext = prevRenderSpan != null && !prevRenderSpan.isShownSnippet;
    if (addLeftContext) {
      const addLeftElipsis = prevRenderSpan.snippetText.length > SURROUNDING_SNIPPET_LEN;
      if (addLeftElipsis) {
        snippetSpans.push({
          renderSpan: prevRenderSpan,
          isEllipsis: true
        });
        someSnippetsHidden = true;
      }
      snippetSpans.push({
        renderSpan: {
          ...prevRenderSpan,
          snippetText: prevRenderSpan.snippetText.slice(-SURROUNDING_SNIPPET_LEN)
        }
      });
    }

    snippetSpans.push({
      renderSpan
    });

    const nextRenderSpan: RenderSpan | null = renderSpans[i + 1] || null;
    const addRightContext = nextRenderSpan != null && !nextRenderSpan.isShownSnippet;

    if (addRightContext) {
      snippetSpans.push({
        renderSpan: {
          ...nextRenderSpan,
          snippetText: nextRenderSpan.snippetText.slice(0, SURROUNDING_SNIPPET_LEN)
        }
      });
      const addRightElipsis = nextRenderSpan.snippetText.length > SURROUNDING_SNIPPET_LEN;
      if (addRightElipsis) {
        snippetSpans.push({
          renderSpan: nextRenderSpan,
          isEllipsis: true
        });
        someSnippetsHidden = true;
      }
    }
  }
  if (snippetSpans.length === 0) {
    // Nothing is highlighted, so just show the beginning of the doc.
    snippetSpans.push({
      renderSpan: {
        ...renderSpans[0],
        snippetText: renderSpans[0].snippetText.slice(0, SNIPPET_LEN_BUDGET)
      }
    });
    const nextRenderSpan: RenderSpan | null = renderSpans[1] || null;
    const addRightEllipsis =
      nextRenderSpan != null || renderSpans[0].snippetText.length > SNIPPET_LEN_BUDGET;
    if (addRightEllipsis) {
      snippetSpans.push({
        renderSpan: nextRenderSpan,
        isEllipsis: true
      });
      someSnippetsHidden = true;
    }
  }
  return {snippetSpans, someSnippetsHidden};
}
