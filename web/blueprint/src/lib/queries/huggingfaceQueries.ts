import {createQuery} from '@tanstack/svelte-query';

const TAG = 'huggingface';
export const queryHFDatasetExists = (dataset: string) =>
  createQuery({
    queryFn: () =>
      fetch(`https://datasets-server.huggingface.co/is-valid?dataset=${dataset}`).then(
        res => res.status === 200
      ),
    queryKey: [TAG, 'isValid', dataset]
  });
export const queryHFSplits = (dataset: string) =>
  createQuery({
    queryFn: () =>
      fetch(`https://datasets-server.huggingface.co/splits?dataset=${dataset}`).then(res =>
        res.json()
      ),
    queryKey: [TAG, 'getSplits', dataset],
    select: res => res.splits as {dataset: string; config: string; split: string}[]
  });
