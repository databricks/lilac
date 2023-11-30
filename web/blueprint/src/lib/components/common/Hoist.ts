export interface HoistOptions {
  // If true, the element will not be hoisted out of the DOM.
  disable?: boolean;
}
/**
 * Hoists an element out of the DOM and positions it absolutely where it was.
 */
export function hoistElement(element: HTMLElement, {disable}: HoistOptions) {
  disable = disable ?? false;
  if (!disable) {
    const boundingRect = element.getBoundingClientRect();
    document.body.append(element);
    element.style.position = 'absolute';
    element.style.top = `${boundingRect.top}px`;
    element.style.left = `${boundingRect.left}px`;
  }
}
