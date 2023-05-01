import {describe, vi} from 'vitest';

import {renderHook, waitFor} from '@testing-library/react';
import {Provider} from 'react-redux';
import {DatasetsService} from '../../fastapi_client';
import {OpenAPISpy} from '../../tests/utils';
import {setupStore} from '../store/store';
import {useGetIds} from './useGetIds';

describe('useGetIds', () => {
  const wrapper = ({children}: {children: React.ReactNode}) => (
    <Provider store={setupStore({})}>{children}</Provider>
  );
  let spy: OpenAPISpy<typeof DatasetsService.selectRows>;

  beforeEach(() => {
    spy = vi.spyOn(DatasetsService, 'selectRows');
  });

  afterEach(() => {
    spy.mockRestore();
  });

  it('should fetch list of ids from dataset', async () => {
    spy.mockResolvedValue([{__rowid__: 'id1'}, {__rowid__: 'id2'}]);
    const {result} = renderHook(
      () =>
        useGetIds({
          namespace: 'namespace',
          datasetName: 'datasetName',
          filters: [],
          limit: 10,
          offset: 0,
        }),
      {wrapper}
    );

    expect(spy).toBeCalledWith('namespace', 'datasetName', {
      columns: [['__rowid__']],
      filters: [],
      limit: 10,
      offset: 0,
      sort_by: undefined,
      sort_order: undefined,
    });

    await waitFor(() => {
      expect(result.current).toEqual({
        error: undefined,
        ids: ['id1', 'id2'],
        isFetching: false,
      });
    });
  });

  it('applied sortyBy', () => {
    spy.mockResolvedValue([]);
    renderHook(
      () =>
        useGetIds({
          namespace: 'namespace',
          datasetName: 'datasetName',
          filters: [],
          limit: 10,
          offset: 0,
          sortBy: [['columnPath1', 'columnPath2']],
          sortOrder: 'ASC',
        }),
      {wrapper}
    );

    expect(spy).toBeCalledWith('namespace', 'datasetName', {
      columns: [['__rowid__'], ['columnPath1', 'columnPath2']],
      filters: [],
      limit: 10,
      offset: 0,
      sort_by: [['columnPath1', 'columnPath2']],
      sort_order: 'ASC',
    });
  });
});
