import {screen} from '@testing-library/react';
import {SpyInstance, vi} from 'vitest';
import {CancelablePromise, DatasetsService} from '../../fastapi_client';
import {renderWithProviders} from '../../tests/utils';
import {GalleryItem} from './gallery_item';

describe('GalleryItem', () => {
  let spy: SpyInstance;
  beforeEach(() => {
    spy = vi.spyOn(DatasetsService, 'selectRows');
  });

  afterEach(() => {
    spy.mockRestore();
  });

  it('should call the api with correct parameters', async () => {
    spy.mockImplementation(
      () =>
        new CancelablePromise(async (resolve) => {
          resolve([]);
        })
    );

    renderWithProviders(
      <GalleryItem
        namespace="test-namespace"
        datasetName="test-dataset"
        itemId="test-item-id"
        mediaPaths={[['content']]}
      />
    );

    expect(spy).toBeCalledWith('test-namespace', 'test-dataset', {
      filters: [
        {
          comparison: 'equals',
          path: ['__rowid__'],
          value: 'test-item-id',
        },
      ],
      limit: 1,
    });
  });

  it('should render simple row with one media path', async () => {
    spy.mockImplementation(
      () =>
        new CancelablePromise(async (resolve) => {
          resolve([
            {
              content: 'row content',
            },
          ]);
        })
    );

    renderWithProviders(
      <GalleryItem namespace="test" datasetName="test" itemId="test" mediaPaths={[['content']]} />
    );

    expect(await screen.findByText('row content')).toBeInTheDocument();
  });

  it('should render error messages', async () => {
    spy.mockImplementation(
      () =>
        new CancelablePromise(async (resolve, reject) => {
          reject(['error message']);
        })
    );

    renderWithProviders(
      <GalleryItem
        namespace="test"
        datasetName="test"
        itemId="test"
        mediaPaths={[]}
        metadataPaths={[]}
      />
    );

    expect(await screen.findByText('error message')).toBeInTheDocument();
  });
});
