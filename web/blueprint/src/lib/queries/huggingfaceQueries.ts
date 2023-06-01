import {createQuery} from '@tanstack/svelte-query';

const TAG = 'huggingface';
export const queryHFDatasets = () =>
  createQuery({
    queryFn: () => fetch('https://datasets-server.huggingface.co/valid').then(res => res.json()),
    queryKey: [TAG, 'listDatasets'],
    select: res => res.valid as string[]
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
