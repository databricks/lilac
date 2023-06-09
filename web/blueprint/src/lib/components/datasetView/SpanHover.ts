import type {SpanHoverNamedValue} from '$lib/view_utils';
import type {SvelteComponent} from 'svelte';
import SpanHoverTooltip from './SpanHoverTooltip.svelte';

export function spanHover(element: HTMLSpanElement, namedValues: SpanHoverNamedValue[]) {
  let tooltipComponent: SvelteComponent | undefined;
  let curNamedValues = namedValues;
  function mouseOver() {
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
        namedValues: curNamedValues,
        x,
        y: boundingRect.top
      },
      target: document.body
    });
  }

  function mouseLeave() {
    tooltipComponent?.$destroy();
  }

  element.addEventListener('mouseover', mouseOver);
  element.addEventListener('mouseleave', mouseLeave);

  return {
    update(namedValues: SpanHoverNamedValue[]) {
      console.log('update');
      curNamedValues = namedValues;
    },
    destroy() {
      tooltipComponent?.$destroy();
      element.removeEventListener('mouseover', mouseOver);
      element.removeEventListener('mouseleave', mouseLeave);
    }
  };
}
