import {SlButton, SlInput, SlSpinner} from '@shoelace-style/shoelace/dist/react';
import * as React from 'react';
import {useAddModelDataMutation} from '../store/store';
import {renderError} from '../utils';
import styles from './dataset_loader.module.css';

export interface DatasetLoaderProps {
  username: string;
  modelName: string;
}
export const DatasetLoader = React.memo(function DatasetLoader({
  username,
  modelName,
}: DatasetLoaderProps): JSX.Element {
  // For huggingface data loading.
  const [hfDataset, setHfDataset] = React.useState('rotten_tomatoes');
  const [hfSplit, setHfSplit] = React.useState('train');
  const [hfTextField, setHfTextField] = React.useState('text');
  const [
    addModelData,
    {
      isLoading: isAddModelLoading,
      isError: isAddModelDataError,
      error: addModelDataError,
      isSuccess: isAddModelDataSuccess,
    },
  ] = useAddModelDataMutation();

  const addDataClicked = () => {
    addModelData({
      username: username!,
      model_name: modelName!,
      hf_dataset: hfDataset,
      hf_split: hfSplit,
      hf_text_field: hfTextField,
    });
  };
  return (
    <>
      <div className={styles.add_dataset_row}>
        <div className="text-lg">No data found for this model. Please add data.</div>
        <div className="flex flex-col justify-left items-left">
          <div className="mb-6">
            <SlInput
              value={hfDataset}
              helpText="Huggingface Dataset"
              onSlChange={(e) => setHfDataset((e.target as HTMLInputElement).value)}
            />
          </div>
          <div className="mb-6">
            <SlInput
              value={hfSplit}
              helpText="Dataset split"
              onSlChange={(e) => setHfSplit((e.target as HTMLInputElement).value)}
            />
          </div>
          <div className="mb-6">
            <SlInput
              value={hfTextField}
              helpText="Text field"
              onSlChange={(e) => setHfTextField((e.target as HTMLInputElement).value)}
            />
          </div>
        </div>
      </div>
      <div className={styles.add_dataset_row}>
        <SlButton
          disabled={isAddModelLoading || isAddModelDataSuccess}
          variant="success"
          className="mt-1 mr-4"
          onClick={() => addDataClicked()}
        >
          Add data
        </SlButton>
        {isAddModelLoading ? <SlSpinner /> : <></>}
      </div>
      <div className="mt-4">
        {isAddModelDataError ? <>{renderError(addModelDataError)}</> : <></>}
      </div>
    </>
  );
});
