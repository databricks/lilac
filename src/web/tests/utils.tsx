import {render, RenderOptions} from '@testing-library/react';
import {Provider} from 'react-redux';
import {BrowserRouter} from 'react-router-dom';

import {PreloadedState} from '@reduxjs/toolkit';
import React, {PropsWithChildren} from 'react';
import {AppStore, RootState, setupStore} from '../src/store/store';

interface ExtendedRenderOptions extends Omit<RenderOptions, 'queries'> {
  preloadedState?: PreloadedState<RootState>;
  store?: AppStore;
}

/**
 * Helper utility that renders a component wrapped in both browser router
 * and in the redux provider.
 */
export function renderWithProviders(
  ui: React.ReactElement,

  {
    route = '/',
    preloadedState = {},
    // Automatically create a store instance if no store was passed in
    store = setupStore(preloadedState),
    ...renderOptions
  }: ExtendedRenderOptions & {route?: string} = {}
): {store: ReturnType<typeof setupStore>} {
  window.history.pushState({}, 'Test page', route);

  function Wrapper({children}: PropsWithChildren): JSX.Element {
    return (
      <BrowserRouter>
        <Provider store={store}>{children}</Provider>
      </BrowserRouter>
    );
  }
  return {store, ...render(ui, {wrapper: Wrapper, ...renderOptions})};
}
