import {SlButton, SlIcon, SlInput, SlSpinner} from '@shoelace-style/shoelace/dist/react';
import * as React from 'react';
import {useParams} from 'react-router-dom';
import {LabeledExample} from '../server_api_deprecated';
import {
  useAddExamplesMutation,
  useLazySearchExamplesQuery,
  useLoadModelQuery,
  useModelInfoQuery,
  useSaveModelMutation,
} from '../store/store';
import {renderError} from '../utils';
import {DatasetLoader} from './dataset_loader';
import {Label, Table, TableExample} from './table';

// TODO: Generalize this.
const LABEL_SET = ['out filter', 'in filter'];

export const FilterBuilder = React.memo(function ModelViewer(): JSX.Element {
  const {username, modelName} = useParams<{username: string; modelName: string}>();
  // Search.
  const [searchQuery, setSearchQuery] = React.useState('');

  const [newInputText, setNewInputText] = React.useState('');
  const [newInputLabel, setNewInputLabel] = React.useState<number | null>(null);

  // Labeled data.
  const [labeledData, setLabeledData] = React.useState<LabeledExample[]>([]);

  const {
    currentData: modelInfo,
    error: modelError,
    isError: isModelError,
    isFetching: isModelFetching,
  } = useModelInfoQuery({
    username,
    name: modelName,
  });

  const {
    currentData: modelData,
    error: loadModelError,
    isError: isLoadModelError,
    isFetching: isLoadModelFetching,
  } = useLoadModelQuery({
    username,
    name: modelName,
  });

  React.useEffect(() => {
    if (modelData?.dataset?.labeled_data != null) {
      setLabeledData(modelData?.dataset.labeled_data);
    }
  }, [modelData?.dataset?.labeled_data]);

  const [
    saveModel,
    {
      isLoading: isSaveModelLoading,
      isError: isSaveModelError,
      error: saveModelError,
      isSuccess: isSaveModelSuccess,
    },
  ] = useSaveModelMutation();

  const saveModelClicked = () => {
    saveModel({
      username: username!,
      name: modelName!,
      labeled_data: labeledData,
    });
  };

  const [
    addExamples,
    {
      isLoading: isAddExamplesLoading,
      isError: isAddExamplesError,
      error: addExamplesError,
      isSuccess: isAddExamplesSuccess,
    },
  ] = useAddExamplesMutation();
  [isAddExamplesError, isAddExamplesLoading, isAddExamplesSuccess, addExamplesError];

  const [
    searchExamples,
    {
      currentData: searchExamplesData,
      error: searchExamplesError,
      isError: isSearchExamplesError,
      isFetching: isSearchExamplesLoading,
    },
  ] = useLazySearchExamplesQuery();
  [isSearchExamplesError, isSearchExamplesLoading, searchExamplesError];

  const labelSelected = (rowIdx: number, label: number) => {
    const newLabeledData = [...labeledData];

    let foundExample = false;
    for (const [i, labeledExample] of newLabeledData.entries()) {
      if (labeledExample.row_idx === rowIdx) {
        newLabeledData[i] = {row_idx: rowIdx, label};
        foundExample = true;
      }
    }

    if (!foundExample) {
      newLabeledData.push({row_idx: rowIdx, label});
    }
    //setTrainData(newTrainingData);
    saveModel({
      username: username!,
      name: modelName!,
      labeled_data: newLabeledData,
    });
  };
  const removeExampleLabel = (trainRowIdx: number) => {
    const newTrainData = labeledData.filter((example) => example.row_idx !== trainRowIdx);
    saveModel({
      username: username!,
      name: modelName!,
      labeled_data: newTrainData,
    });
    //setTrainData(trainData.filter((example) => example.row_idx !== trainRowIdx));
  };

  const {negativeTableExamples, positiveTableExamples, labelCountMap} = React.useMemo(() => {
    const negativeTableExamples: TableExample[] = [];
    const positiveTableExamples: TableExample[] = [];
    const labelCountMap: {[label: number]: number} = {};

    const rowIdxSearchSimilarity: {[rowIdx: number]: number} = {};
    for (const rowResult of searchExamplesData?.row_results || []) {
      rowIdxSearchSimilarity[rowResult.row_idx] = rowResult.similarity;
    }

    if (modelData != null && modelData?.has_data) {
      const labelMap: {[rowIdx: number]: number} = {};
      for (const labeledExample of labeledData || []) {
        const dataRow = modelData.dataset!.data[labeledExample.row_idx];

        const labeledTableExample = {
          text: dataRow.text,
          rowIdx: labeledExample.row_idx,
          prediction: dataRow.prediction,
          label: labeledExample.label,
          metadata: dataRow.metadata,
        };
        if (labeledExample.label === 0) {
          negativeTableExamples.push(labeledTableExample);
        } else if (labeledExample.label === 1) {
          positiveTableExamples.push(labeledTableExample);
        }

        labelMap[labeledExample.row_idx] = labeledExample.label;

        // Balance the training data by sorting the tables by prediction.
        if (labelCountMap[labeledExample.label] == null) {
          labelCountMap[labeledExample.label] = 0;
        }
        labelCountMap[labeledExample.label]++;
      }

      for (const [i, dataRow] of modelData.dataset!.data.entries()) {
        // Don't add to the full dataset when it exists in train or test.
        if (labelMap[i] == null) {
          const metadata =
            rowIdxSearchSimilarity[i] != null
              ? {similarity: rowIdxSearchSimilarity[i], ...dataRow.metadata}
              : dataRow.metadata;

          const predictionTableExample = {
            text: dataRow.text,
            rowIdx: i,
            prediction: dataRow.prediction,
            metadata,
          };
          if (dataRow.prediction === 0) {
            negativeTableExamples.push(predictionTableExample);
          } else if (dataRow.prediction === 1) {
            positiveTableExamples.push(predictionTableExample);
          }
        }
      }
    }
    return {
      negativeTableExamples,
      positiveTableExamples,
      labelCountMap,
    };
  }, [modelData, labeledData, searchExamplesData]);

  const isLoading =
    isLoadModelFetching ||
    isModelFetching ||
    isSaveModelLoading ||
    isSearchExamplesLoading ||
    isAddExamplesLoading;
  return (
    <>
      {modelError || isModelError ? renderError(modelError) : <></>}
      {loadModelError || isLoadModelError ? renderError(modelError) : <></>}

      <div className="flex flex-col ml-2 w-full">
        {modelInfo != null || !isModelFetching ? (
          <div className="flex flex-col mb-4">
            <div className="text-2xl">
              {modelInfo?.username} / {modelInfo?.name}
            </div>
            <div className="text-sm">{modelInfo?.description}</div>
          </div>
        ) : (
          <SlSpinner />
        )}

        {modelData != null && !modelData?.has_data && username != null && modelName != null ? (
          <DatasetLoader username={username} modelName={modelName}></DatasetLoader>
        ) : (
          <></>
        )}

        {modelData?.dataset != null ? (
          <>
            <div className="flex flex-row mt-2">
              <div className="mr-2 font-bold">Prefix</div>
              <div className="italic">Movie review: </div> {/** TODO: Move this to server */}
            </div>
            <div className="mt-4">
              <div className="flex flex-row">
                <div>
                  <SlInput
                    placeholder="Manual example text"
                    value={newInputText}
                    onSlChange={(e) => setNewInputText((e.target as HTMLInputElement).value)}
                  />
                </div>
                <div className={`flex items-center justify-items-center mx-2`}>
                  <Label
                    labelId={newInputLabel}
                    labels={LABEL_SET}
                    onLabelChange={(newLabel) => setNewInputLabel(newLabel)}
                  ></Label>
                </div>
                <div>
                  <SlButton
                    disabled={newInputText === '' || newInputLabel == null}
                    variant="primary"
                    className="mt-1 mr-2"
                    size="small"
                    onClick={() =>
                      addExamples({
                        username: username!,
                        name: modelName!,
                        examples: [{text: newInputText, label: newInputLabel!}],
                      })
                    }
                  >
                    Add
                  </SlButton>
                </div>
              </div>
            </div>
            <div className="flex flex-row mt-2 w-64">
              <SlInput
                placeholder="Search"
                value={searchQuery}
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                onInput={(e) => setSearchQuery((e.target as any).value)}
              ></SlInput>
              <SlButton
                variant="primary"
                className="mt-1 mr-2 ml-2"
                size="small"
                onClick={() =>
                  searchExamples({
                    username: username!,
                    modelName: modelName!,
                    query: searchQuery,
                  })
                }
              >
                Search
              </SlButton>
            </div>
            <div className="flex flex-row mt-2 w-64">
              <SlButton
                variant="danger"
                className="mt-1 mr-2 ml-2 opacity-80"
                size="small"
                onClick={() =>
                  saveModel({
                    username: username!,
                    name: modelName!,
                    labeled_data: [],
                  })
                }
              >
                Clear all labels
              </SlButton>
            </div>
            {/* Out of filter table */}
            <div className={`flex flex-row w-full space-x-4 ${isLoading ? 'opacity-25' : ''}`}>
              <div className="w-2/4">
                <Table
                  title="Out of filter"
                  examples={negativeTableExamples}
                  labelSet={LABEL_SET}
                  tableHeightPx={500}
                  exampleRemoved={removeExampleLabel}
                  labelSelected={labelSelected}
                  sortBy={
                    searchExamplesData?.row_results == null
                      ? [
                          {id: 'prediction', desc: labelCountMap[0] >= labelCountMap[1]},
                          {id: 'confidence', desc: false},
                        ]
                      : [{id: 'similarity', desc: true}]
                  }
                  rowIdxFilter={searchExamplesData?.row_results.map(
                    (rowResult) => rowResult.row_idx
                  )}
                ></Table>
              </div>
              {/* In filter table */}

              <div className="w-2/4">
                <Table
                  title="In filter"
                  examples={positiveTableExamples}
                  labelSet={LABEL_SET}
                  tableHeightPx={500}
                  exampleRemoved={removeExampleLabel}
                  labelSelected={labelSelected}
                  sortBy={
                    searchExamplesData?.row_results == null
                      ? [
                          {id: 'prediction', desc: labelCountMap[0] >= labelCountMap[1]},
                          {id: 'confidence', desc: false},
                        ]
                      : [{id: 'similarity', desc: true}]
                  }
                  rowIdxFilter={searchExamplesData?.row_results.map(
                    (rowResult) => rowResult.row_idx
                  )}
                  addExample={(text: string, label: number) =>
                    addExamples({username: username!, name: modelName!, examples: [{text, label}]})
                  }
                ></Table>
              </div>
            </div>
            {/* Save data */}
            <div className="w-full flex flex-row">
              <div>
                <SlButton
                  disabled={isSaveModelLoading}
                  variant="primary"
                  className="mt-1 mr-2"
                  size="small"
                  onClick={() => saveModelClicked()}
                >
                  Save
                </SlButton>
              </div>
              {isSaveModelLoading ? (
                <div className="h-full flex flex-col justify-center justify-items-center text-xl">
                  <SlSpinner></SlSpinner>
                </div>
              ) : (
                <></>
              )}
              <div
                className="h-full flex flex-col justify-center justify-items-center text-xl"
                style={{color: '#f5a623'}}
              >
                {isSaveModelSuccess ? <SlIcon name="check-lg" /> : <></>}
              </div>
              <div
                className="h-full flex flex-col justify-center justify-items-center text-sm"
                style={{color: 'red'}}
              >
                {isSaveModelError ? <>{renderError(saveModelError)}</> : <></>}
              </div>
            </div>
          </>
        ) : (
          <></>
        )}
      </div>
    </>
  );
});
