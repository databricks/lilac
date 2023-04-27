import '@testing-library/jest-dom/extend-expect';
import matchers from '@testing-library/jest-dom/matchers';
import {cleanup} from '@testing-library/react';
import {afterEach, expect, SpyInstance, vi} from 'vitest';
import * as request from '../fastapi_client/core/request';

const ResizeObserverMock = vi.fn(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
}));

vi.stubGlobal('ResizeObserver', ResizeObserverMock);

// extends Vitest's expect method with methods from react-testing-library
expect.extend(matchers);

// Make sure that no real openapi requests are made during tests
let openApiRequestMock: SpyInstance;
beforeEach(() => {
  openApiRequestMock = vi.spyOn(request, 'request');
});

afterEach(() => {
  expect(openApiRequestMock).not.toHaveBeenCalled();
  cleanup();
});
