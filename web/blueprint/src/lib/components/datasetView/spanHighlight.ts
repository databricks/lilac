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

  // Whether this span is highlighted and needs to always be shown.
  isHighlighted: boolean;
  snippetScore: number;
  // The text for this render span.
  text: string;

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
    let isHighlighted = false;
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
              isHighlighted = true;
            }
          } else {
            isHighlighted = true;
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
      isHighlighted,
      snippetScore: maxScore,
      namedValues: firstNamedValues,
      paths: mergedSpan.paths,
      text: mergedSpan.text,
      originalSpans: mergedSpan.originalSpans,
      isHovered,
      isFirstHover
    });
  }
  return renderSpans;
}

export type SnippetSpan =
  | {
      renderSpan: RenderSpan;
      snippetText: string;
      isEllipsis?: false;
    }
  | {isEllipsis: true};

export function getSnippetSpans(
  renderSpans: RenderSpan[],
  isExpanded: boolean
): {snippetSpans: SnippetSpan[]; someSnippetsHidden: boolean} {
  if (isExpanded) {
    // If the span is expanded, we don't need to do any snippetting.
    return {
      snippetSpans: renderSpans.map(renderSpan => ({renderSpan, snippetText: renderSpan.text})),
      someSnippetsHidden: false
    };
  }
  let someSnippetsHidden = false;
  let someSnippetsHighlighted = false;
  // If the doc is not expanded, we need to do snippetting.
  let snippetSpans: SnippetSpan[] = [];
  for (let i = 0; i < renderSpans.length; i++) {
    const renderSpan = renderSpans[i];
    const prevRenderSpan = i - 1 >= 0 ? renderSpans[i - 1] : null;
    const nextRenderSpan = i + 1 < renderSpans.length ? renderSpans[i + 1] : null;
    const lastSnippetWasEllipsis = snippetSpans.at(-1)?.isEllipsis;
    if (!renderSpan.isHighlighted) {
      if (lastSnippetWasEllipsis) {
        continue;
      }
      if (prevRenderSpan?.isHighlighted || nextRenderSpan?.isHighlighted) {
        continue;
      }
      someSnippetsHidden = true;
      snippetSpans.push({isEllipsis: true});
      continue;
    }
    someSnippetsHighlighted = true;
    const addLeftContext = prevRenderSpan != null && !prevRenderSpan.isHighlighted;
    if (addLeftContext) {
      const addLeftEllipsis =
        !lastSnippetWasEllipsis && prevRenderSpan.text.length > SURROUNDING_SNIPPET_LEN;
      if (addLeftEllipsis) {
        snippetSpans.push({isEllipsis: true});
        someSnippetsHidden = true;
      }
      snippetSpans.push({
        renderSpan: prevRenderSpan,
        snippetText: prevRenderSpan.text.slice(-SURROUNDING_SNIPPET_LEN)
      });
    }

    snippetSpans.push({
      renderSpan,
      snippetText: renderSpan.text
    });

    const addRightContext = nextRenderSpan != null && !nextRenderSpan.isHighlighted;
    if (addRightContext) {
      snippetSpans.push({
        renderSpan: nextRenderSpan,
        snippetText: nextRenderSpan.text.slice(0, SURROUNDING_SNIPPET_LEN)
      });
      const addRightEllipsis =
        !lastSnippetWasEllipsis && nextRenderSpan.text.length > SURROUNDING_SNIPPET_LEN;
      if (addRightEllipsis) {
        snippetSpans.push({isEllipsis: true});
        someSnippetsHidden = true;
      }
    }
  }
  if (!someSnippetsHighlighted) {
    snippetSpans = [];
    someSnippetsHidden = false;
    // Nothing is highlighted, so just show the beginning of the doc.
    snippetSpans.push({
      renderSpan: renderSpans[0],
      snippetText: renderSpans[0].text.slice(0, SNIPPET_LEN_BUDGET)
    });
    const nextRenderSpan: RenderSpan | null = renderSpans[1] || null;
    const addRightEllipsis =
      nextRenderSpan != null || renderSpans[0].text.length > SNIPPET_LEN_BUDGET;
    if (addRightEllipsis) {
      snippetSpans.push({isEllipsis: true});
      someSnippetsHidden = true;
    }
  }
  return {snippetSpans, someSnippetsHidden};
}
