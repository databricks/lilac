import {deserializePath, pathIsMatching} from '$lilac';
import type {SvelteComponent} from 'svelte';
import SpanHoverTooltip, {type SpanHoverNamedValue} from './SpanHoverTooltip.svelte';

export interface SpanHoverInfo {
  namedValues: SpanHoverNamedValue[];
  spansHovered: string[];
  isHovered: boolean;
  itemScrollContainer: HTMLDivElement | null;
}
export function spanHover(element: HTMLSpanElement, spanHoverInfo: SpanHoverInfo) {
  let tooltipComponent: SvelteComponent | undefined;
  let curSpanHoverInfo = spanHoverInfo;
  const itemScrollListener = () => destroyHoverElement();
  showSpan();
  function showSpan() {
    if (!curSpanHoverInfo.isHovered) {
      return;
    }
    curSpanHoverInfo.namedValues = spanHoverInfo.namedValues.filter(namedValue =>
      curSpanHoverInfo.spansHovered.some(path =>
        pathIsMatching(deserializePath(namedValue.spanPath), deserializePath(path))
      )
    );
    if (curSpanHoverInfo.namedValues.length === 0) {
      return;
    }
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
        namedValues: curSpanHoverInfo.namedValues,
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

      if (!spanHoverInfo.isHovered) {
        destroyHoverElement();
      } else {
        showSpan();
      }
      tooltipComponent?.$set({namedValues: curSpanHoverInfo.namedValues});
    },
    destroy() {
      destroyHoverElement();
    }
  };
}
