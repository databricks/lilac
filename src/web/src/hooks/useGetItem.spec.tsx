import {describe, vi} from 'vitest';

import {renderHook, waitFor} from '@testing-library/react';
import {Provider} from 'react-redux';
import {DatasetsService} from '../../fastapi_client';
import {OpenAPISpy} from '../../tests/utils';
import {setupStore} from '../store/store';
import {useGetItem} from './useGetItem';

describe('useGetItem', () => {
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

  it('should fetch a single row', async () => {
    spy.mockResolvedValue([{__rowid__: 'id1', content: 'row content'}]);
    const {result} = renderHook(
      () =>
        useGetItem({
          namespace: 'namespace',
          datasetName: 'datasetName',
          itemId: 'id1',
        }),
      {wrapper}
    );

    await waitFor(() => {
      expect(result.current).toEqual({
        error: undefined,
        item: {
          __rowid__: 'id1',
          content: 'row content',
        },
        isFetching: false,
      });
    });

    expect(spy).toBeCalledWith('namespace', 'datasetName', {
      filters: [
        {
          comparison: 'in',
          path: ['__rowid__'],
          value: ['id1'],
        },
      ],
      limit: 1,
    });
  });
});
