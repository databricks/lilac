import {renderHook, waitFor} from '@testing-library/react';
import React from 'react';
import {Provider} from 'react-redux';
import {afterEach, beforeEach, describe, vi} from 'vitest';
import {DatasetsService} from '../../fastapi_client';
import {OpenAPISpy} from '../../tests/utils';
import {useSelectRowsByUUIDQuery} from './apiDataset';
import {setupStore} from './store';

describe('apiDataset', () => {
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

  describe('useSelectRowsByUUIDQuery', () => {
    it('selects a single row by uuid', async () => {
      spy.mockResolvedValue([{column: 'data'}]);

      const {result} = renderHook(
        () =>
          useSelectRowsByUUIDQuery({
            namespace: 'namespace',
            datasetName: 'datasetName',
            uuid: 'id1',
            options: {},
          }),
        {wrapper}
      );

      await waitFor(() => {
        expect(result.current.currentData).toEqual({column: 'data'});
      });

      expect(spy).toBeCalledTimes(1);
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

    it('selects rows with batching disabled', async () => {
      spy.mockResolvedValue([{column: 'data'}]);

      const {result} = renderHook(
        () =>
          useSelectRowsByUUIDQuery({
            namespace: 'namespace',
            datasetName: 'datasetName',
            uuid: 'id1',
            options: {},
            batched: false,
          }),
        {wrapper}
      );

      await waitFor(() => {
        expect(result.current.currentData).toEqual({column: 'data'});
      });

      expect(spy).toBeCalledWith('namespace', 'datasetName', {
        filters: [
          {
            comparison: 'equals',
            path: ['__rowid__'],
            value: 'id1',
          },
        ],
        limit: 1,
      });
    });

    it('selects multiple rows', async () => {
      spy.mockResolvedValue([{column: 'data1'}, {column: 'data2'}]);

      const {result: result1} = renderHook(
        () =>
          useSelectRowsByUUIDQuery({
            namespace: 'namespace',
            datasetName: 'datasetName',
            uuid: 'id1',
            options: {},
          }),
        {wrapper}
      );

      const {result: result2} = renderHook(
        () =>
          useSelectRowsByUUIDQuery({
            namespace: 'namespace',
            datasetName: 'datasetName',
            uuid: 'id2',
            options: {},
          }),
        {wrapper}
      );

      await waitFor(() => {
        expect(result1.current.currentData).toEqual({column: 'data1'});
      });

      expect(result2.current.currentData).toEqual({column: 'data2'});

      expect(spy).toBeCalledTimes(1);
      expect(spy).toBeCalledWith('namespace', 'datasetName', {
        filters: [
          {
            comparison: 'in',
            path: ['__rowid__'],
            value: ['id1', 'id2'],
          },
        ],
        limit: 2,
      });
    });

    it('seperates requests with different options', async () => {
      spy.mockResolvedValueOnce([{column: 'data1'}]);
      spy.mockResolvedValueOnce([{column: 'data2'}]);

      const {result: result1} = renderHook(
        () =>
          useSelectRowsByUUIDQuery({
            namespace: 'namespace',
            datasetName: 'datasetName',
            uuid: 'id1',
            options: {},
          }),
        {wrapper}
      );

      const {result: result2} = renderHook(
        () =>
          useSelectRowsByUUIDQuery({
            namespace: 'namespace',
            datasetName: 'datasetName',
            uuid: 'id2',
            options: {
              columns: [['column']],
            },
          }),
        {wrapper}
      );

      await waitFor(() => {
        expect(result1.current.currentData).toEqual({column: 'data1'});
      });

      expect(result2.current.currentData).toEqual({column: 'data2'});

      expect(spy).toBeCalledTimes(2);

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

      expect(spy).toBeCalledWith('namespace', 'datasetName', {
        columns: [['column']],
        filters: [
          {
            comparison: 'in',
            path: ['__rowid__'],
            value: ['id2'],
          },
        ],
        limit: 1,
      });
    });

    it('handles failing requests', async () => {
      spy.mockRejectedValue('error_message');

      const {result: result1} = renderHook(
        () =>
          useSelectRowsByUUIDQuery({
            namespace: 'namespace',
            datasetName: 'datasetName',
            uuid: 'id1',
            options: {},
          }),
        {wrapper}
      );

      const {result: result2} = renderHook(
        () =>
          useSelectRowsByUUIDQuery({
            namespace: 'namespace',
            datasetName: 'datasetName',
            uuid: 'id2',
            options: {},
          }),
        {wrapper}
      );

      await waitFor(() => {
        expect(result1.current.error).toEqual('error_message');
      });
      expect(result2.current.error).toEqual('error_message');
    });
  });
});
