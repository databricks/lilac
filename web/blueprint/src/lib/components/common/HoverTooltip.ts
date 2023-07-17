import type {SvelteComponent} from 'svelte';
import HoverTooltip from './HoverTooltip.svelte';

interface HoverTooltipOptions {
  // The text to show upon hover.
  text?: string;
  // The component to show upon hover. This can be defined if the body of the hover is complicated
  // HTML.
  component?: typeof SvelteComponent;
  // The props to pass to the body component.
  props?: Record<string, unknown>;
}

export function hoverTooltip(element: HTMLElement, {text, component, props}: HoverTooltipOptions) {
  if (component == null && text == null) {
    return;
  }
  let tooltipComponent: SvelteComponent | undefined;
  let curText = text;
  let curComponent = component;
  let curProps = props;
  function mouseOver() {
    if (tooltipComponent != null) return;
    const boundingRect = element.getBoundingClientRect();

    tooltipComponent = new HoverTooltip({
      props: {
        text: curText,
        component: curComponent,
        props: curProps,
        x: boundingRect.left + boundingRect.width / 2,
        y: boundingRect.bottom
      },
      target: document.body
    });
  }

  function mouseLeave() {
    tooltipComponent?.$destroy();
    tooltipComponent = undefined;
  }

  element.addEventListener('mouseover', mouseOver);
  element.addEventListener('mouseleave', mouseLeave);
  element.addEventListener('click', mouseLeave);

  return {
    update({
      text: tooltipText,
      component: tooltipBodyComponent,
      props: tooltipBodyProps
    }: HoverTooltipOptions) {
      curText = tooltipText;
      curComponent = tooltipBodyComponent;
      curProps = tooltipBodyProps;
      tooltipComponent?.$set({tooltipText});
    },
    destroy() {
      mouseLeave();
      element.removeEventListener('mouseover', mouseOver);
      element.removeEventListener('mouseleave', mouseLeave);
      element.removeEventListener('click', mouseLeave);
    }
  };
}
