import {deserializePath, pathIsEqual} from '$lilac';
import type {SvelteComponent} from 'svelte';
import SpanHoverTooltip, {type SpanHoverNamedValue} from './SpanHoverTooltip.svelte';

export interface SpanHoverInfo {
  namedValues: SpanHoverNamedValue[];
  spansHovered: Set<string>;
  isHovered: boolean;
  itemScrollContainer: HTMLDivElement | null;
}
export function spanHover(element: HTMLSpanElement, spanHoverInfo: SpanHoverInfo) {
  let tooltipComponent: SvelteComponent | undefined;
  let curSpanHoverInfo = spanHoverInfo;
  const itemScrollListener = () => destroyHoverElement();
  if (curSpanHoverInfo.isHovered) {
    showSpan();
  }
  function showSpan() {
    const namedValues = curSpanHoverInfo.namedValues.filter(namedValue =>
      Array.from(curSpanHoverInfo.spansHovered).some(path => {
        const spanHoveredPath = deserializePath(path);
        // The specific path may point to metadata under the hovered span, so we cut it to the
        // length of the hovered span to check if they match.
        return pathIsEqual(
          namedValue.specificPath.slice(0, spanHoveredPath.length),
          spanHoveredPath
        );
      })
    );
    if (curSpanHoverInfo.itemScrollContainer != null) {
      curSpanHoverInfo.itemScrollContainer.addEventListener('scroll', itemScrollListener);
    }
    const boundingRect = element.getBoundingClientRect();
    const style = window.getComputedStyle(element);
    const lineHeight = parseInt(style.getPropertyValue('line-height'));
    // If the span only takes a single line, we don't need to offset with the offsetLeft.
    const x =
      boundingRect.height > lineHeight
        ? boundingRect.x + element.offsetLeft || element.clientLeft
        : boundingRect.x;

    tooltipComponent = new SpanHoverTooltip({
      props: {
        namedValues,
        x,
        y: boundingRect.top
      },
      target: document.body
    });
  }

  function destroyHoverElement() {
    tooltipComponent?.$destroy();
    tooltipComponent = undefined;
    if (curSpanHoverInfo.itemScrollContainer != null) {
      curSpanHoverInfo.itemScrollContainer.removeEventListener('scroll', itemScrollListener);
    }
  }

  return {
    update(spanHoverInfo: SpanHoverInfo) {
      curSpanHoverInfo = spanHoverInfo;

      if (!curSpanHoverInfo.isHovered) {
        destroyHoverElement();
      } else {
        showSpan();
      }
    },
    destroy() {
      destroyHoverElement();
    }
  };
}
