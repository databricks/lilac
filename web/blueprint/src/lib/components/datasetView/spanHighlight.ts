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
const SNIPPET_LEN_BUDGET = 500;
const MAX_RENDER_SPAN_LENGTH = 100;

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
          if (value == null) continue;

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
      text: mergedSpan.text,
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
  isShown: boolean;
  // When the snippet is hidden, whether it should be replaced with ellipsis. We only do this once
  // for a continuous set of hidden snippets.
  isEllipsis?: boolean;
  // When the snippet is hidden, whether the original text had a new-line so it can be preserved.
  hasNewline?: boolean;
}

export function getSnippetSpans(
  renderSpans: RenderSpan[],
  isExpanded: boolean
): {snippetSpans: SnippetSpan[]; someSnippetsHidden: boolean} {
  // First, cut any snippet shown render spans that are too long.
  renderSpans = renderSpans
    .map(renderSpan => {
      if (renderSpan.isShownSnippet && renderSpan.text.length > MAX_RENDER_SPAN_LENGTH) {
        const shownRenderSpan = {
          ...renderSpan,
          text: renderSpan.text.slice(0, MAX_RENDER_SPAN_LENGTH),
          snippetText: renderSpan.snippetText.slice(0, MAX_RENDER_SPAN_LENGTH)
        };
        const hiddenRenderSpan = {
          ...renderSpan,
          text: renderSpan.text.slice(MAX_RENDER_SPAN_LENGTH),
          snippetText: renderSpan.snippetText.slice(MAX_RENDER_SPAN_LENGTH),
          isShownSnippet: false,
          // The hover metadata is already displayed in the shown span.
          namedValues: []
        };
        return [shownRenderSpan, hiddenRenderSpan];
      } else {
        return [renderSpan];
      }
    })
    .flat();
  // Map the merged spans to the information needed to render each span.
  if (isExpanded) {
    return {
      snippetSpans: renderSpans.map(renderSpan => ({renderSpan, isShown: true})),
      someSnippetsHidden: false
    };
  }
  const snippetSpans: SnippetSpan[] = [];
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
    shownSnippetTotalLength += renderSpan.text.length;
    if (shownSnippetTotalLength > SNIPPET_LEN_BUDGET) {
      break;
    }
  }
  let someSnippetsHidden = false;
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
  return {snippetSpans, someSnippetsHidden};
}
