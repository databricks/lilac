import {screen} from '@testing-library/react';
import {SpyInstance, vi} from 'vitest';
import {DatasetsService} from '../../fastapi_client';
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
    spy.mockResolvedValueOnce([]);

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
    spy.mockResolvedValueOnce([
      {
        content: 'row content',
      },
    ]);

    renderWithProviders(
      <GalleryItem
        namespace="namespace"
        datasetName="datasetname"
        itemId="itemid"
        mediaPaths={[['content']]}
      />
    );

    expect(await screen.findByText('row content')).toBeInTheDocument();
    // Key's should not be visible when theres only one media path
    expect(await screen.queryByText('content')).not.toBeInTheDocument();
  });

  it('should render number values formatted', async () => {
    spy.mockResolvedValueOnce([
      {
        content: 1234567.1234567,
      },
    ]);

    renderWithProviders(
      <GalleryItem
        namespace="namespace"
        datasetName="datasetname"
        itemId="itemid"
        mediaPaths={[['content']]}
      />
    );

    expect(await screen.findByText('1,234,567.123')).toBeInTheDocument();
  });

  it('should render multiple medias', async () => {
    spy.mockResolvedValueOnce([
      {
        key1: 'content 1',
        key2: 'content 2',
      },
    ]);

    renderWithProviders(
      <GalleryItem
        namespace="namespace"
        datasetName="datasetname"
        itemId="itemid"
        mediaPaths={[['key1'], ['key2']]}
      />
    );

    expect(await screen.findByText('key1')).toBeInTheDocument();
    expect(await screen.findByText('content 1')).toBeInTheDocument();
    expect(await screen.findByText('key2')).toBeInTheDocument();
    expect(await screen.findByText('content 2')).toBeInTheDocument();
  });

  it('should render metadata', async () => {
    spy.mockResolvedValueOnce([
      {
        contentKey: 'content 1',
        metadataKey1: 'metadata 1',
        metadataKey2: 'metadata 2',
      },
    ]);

    renderWithProviders(
      <GalleryItem
        namespace="namespace"
        datasetName="datasetname"
        itemId="itemid"
        mediaPaths={[['contentKey']]}
        metadataPaths={[['metadataKey1'], ['metadataKey2']]}
      />
    );

    expect(await screen.findByText('metadataKey1')).toBeInTheDocument();
    expect(await screen.findByText('metadata 1')).toBeInTheDocument();
    expect(await screen.findByText('metadataKey2')).toBeInTheDocument();
    expect(await screen.findByText('metadata 2')).toBeInTheDocument();
  });

  it('should render error messages', async () => {
    spy.mockRejectedValueOnce(['error message']);

    renderWithProviders(
      <GalleryItem
        namespace="namespace"
        datasetName="datasetname"
        itemId="itemid"
        mediaPaths={[]}
      />
    );

    expect(await screen.findByText('error message')).toBeInTheDocument();
  });
});
