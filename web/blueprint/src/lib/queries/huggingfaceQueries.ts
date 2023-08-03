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
export const queryHFSplits = (dataset: string, config?: string) =>
  createQuery({
    queryFn: () =>
      fetch(
        `https://datasets-server.huggingface.co/splits?dataset=${dataset}&config=${config || ''}`
      ).then(res => res.json()),
    queryKey: [TAG, 'getSplits', dataset, config],
    select: res => res.splits as {dataset: string; config: string; split: string}[]
  });
