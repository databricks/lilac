import type {MergedSpan} from '$lib/view_utils';
import {
  L,
  deserializePath,
  getField,
  isNumeric,
  pathIncludes,
  serializePath,
  valueAtPath,
  type ConceptLabelsSignal,
  type ConceptScoreSignal,
  type LilacField,
  type LilacSchema,
  type LilacValueNode,
  type LilacValueNodeCasted,
  type SemanticSimilaritySignal,
  type SubstringSignal
} from '$lilac';
import type {SpanHoverNamedValue} from './SpanHoverTooltip.svelte';
import {colorFromScore} from './colors';

// When the text length exceeds this number we start to snippet.
const SNIPPET_LEN_BUDGET = 500;

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

  hoverInfo: SpanHoverNamedValue[];
  // Whether the hover matches any path in this render span. Used for highlighting.
  isHovered: boolean;
  // Whether this render span is the first matching span for the hovered span. This is used for
  // showing the tooltip only on the first matching path.
  isFirstHover: boolean;
}

export function getRenderSpans(
  mergedSpans: MergedSpan[],
  schema: LilacSchema | undefined,
  spanValueFields: {[k: string]: LilacField[]},
  keywordSpanPaths: string[],
  labelSpanPaths: string[],
  field: LilacField,
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

    const hoverInfo: SpanHoverNamedValue[] = [];
    let hasNonNumericMetadata = false;
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
                spanPath: spanPathStr,
                isConcept: true
              });
            }

            if ((value as number) > 0.5) {
              isShownSnippet = true;
            }
          } else if (valueField.signal?.signal_name === 'semantic_similarity') {
            if (!pathSeen) {
              const signal = valueField.signal as SemanticSimilaritySignal;
              hoverInfo.push({
                name: `similarity: ${signal.query}`,
                value,
                spanPath: spanPathStr,
                isSemanticSearch: true
              });
            }

            if ((value as number) > 0.5) {
              isShownSnippet = true;
            }
          } else {
            // Check if this is a concept label.
            let isConceptLabelSignal = false;
            for (const labelSpanPath of labelSpanPaths) {
              if (pathIncludes(valueField.path, labelSpanPath) && schema != null) {
                const field = getField(schema, deserializePath(labelSpanPath).slice(0, -1));
                if (field?.signal?.signal_name === 'concept_labels') {
                  if (!pathSeen) {
                    const signal = field?.signal as ConceptLabelsSignal;
                    hoverInfo.push({
                      name: `${signal.namespace}/${signal.concept_name} label`,
                      value,
                      spanPath: spanPathStr
                    });
                  }
                  isConceptLabelSignal = true;
                  isShownSnippet = true;
                }
              }
            }
            // Show arbitrary metadata.
            if (!isConceptLabelSignal) {
              const isNonNumericMetadata = !isNumeric(valueField.dtype!);
              if (!pathSeen) {
                const name = serializePath(valueField.path.slice(field.path.length));
                hoverInfo.push({
                  name,
                  value,
                  spanPath: spanPathStr,
                  isNonNumericMetadata
                });
              }
              hasNonNumericMetadata = hasNonNumericMetadata || isNonNumericMetadata;
              isShownSnippet = true;
            }
          }
        }
      }
    }

    // Add keyword info. Keyword results don't have values so we process them separately.
    let isKeywordSpan = false;
    if (schema != null) {
      for (const keywordSpanPath of keywordSpanPaths) {
        if (mergedSpan.originalSpans[keywordSpanPath] != null) {
          isKeywordSpan = true;
          const field = getField(schema, deserializePath(keywordSpanPath).slice(0, -1));
          const signal = field?.signal as SubstringSignal;
          hoverInfo.push({
            name: 'keyword',
            value: signal.query,
            spanPath: keywordSpanPath,
            isKeywordSearch: true
          });
          isShownSnippet = true;
        }
      }
    }

    const isLabeled = labelSpanPaths.some(labelPath => mergedSpan.originalSpans[labelPath] != null);
    const isHovered = mergedSpan.paths.some(path => pathsHovered.has(path));

    // The rendered span is a first hover if there is a new path that matches a specific render
    // span that is hovered.
    const isFirstHover =
      isHovered &&
      newPaths.length > 0 &&
      Array.from(pathsHovered).some(pathHovered => newPaths.includes(pathHovered));

    renderSpans.push({
      backgroundColor: colorFromScore(maxScore),
      isBlackBolded: isKeywordSpan || hasNonNumericMetadata,
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
  // Map the merged spans to the information needed to render each span.

  if (isExpanded || renderSpans.length < 2) {
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
    belowThresholdSpans.push(renderSpan);
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
