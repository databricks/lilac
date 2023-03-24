import {
  SlButton,
  SlIcon,
  SlInput,
  SlRadioButton,
  SlRadioGroup,
  SlSpinner,
} from '@shoelace-style/shoelace/dist/react';
import * as React from 'react';
import {useParams} from 'react-router-dom';
import {
  useLazySearchExamplesQuery,
  useLoadModelQuery,
  useModelInfoQuery,
  useSaveModelMutation,
} from '../store';
import {renderError} from '../utils';
import {DatasetLoader} from './dataset_loader';
import {Example, ExampleViewer, LabeledData} from './example_viewer';

const TOP_K = 100;

type FilterView = 'labeled' | 'semantic' | 'ranked' | 'random';

export const FilterMaker = React.memo(function FilterMaker(): JSX.Element {
  const {username, modelName} = useParams<{username: string; modelName: string}>();
  // Search.
  const [searchQuery, setSearchQuery] = React.useState('Kids go on a treasure hunt');
  const [filterView, setFilterView] = React.useState<FilterView>('random');

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
    const labeledExamples = Object.entries(labeledData).map(([rowIdx, label]) => ({
      row_idx: +rowIdx,
      label,
    }));
    setFilterView('ranked');
    saveModel({
      username: username!,
      name: modelName!,
      labeled_data: labeledExamples,
    });
  };

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

  React.useEffect(() => {
    if (modelData?.dataset?.labeled_data == null) {
      return;
    }
    const newLabeledData: LabeledData = {};
    for (const labeledExample of modelData.dataset.labeled_data) {
      newLabeledData[labeledExample.row_idx.toString()] = labeledExample.label;
    }
    setLabeledData(newLabeledData);
  }, [modelData?.dataset?.labeled_data]);

  const [rankedExamples, randomExamples] = React.useMemo(() => {
    if (modelData?.dataset?.data == null) {
      return [[], []];
    }
    const serverLabeledData: LabeledData = {};
    for (const labeledExample of modelData.dataset.labeled_data) {
      serverLabeledData[labeledExample.row_idx.toString()] = labeledExample.label;
    }
    const modelExamples = modelData.dataset.data
      .map((row, idx) => ({
        text: row.text,
        id: idx.toString(),
        confidence: row.metadata['confidence'] as number,
      }))
      .filter((row) => !(row.id in serverLabeledData));
    const rankedExamples = modelExamples
      .sort((a, b) => b.confidence - a.confidence)
      .slice(0, TOP_K);
    const randomExamples = modelExamples.sort(() => Math.random() - 0.5).slice(0, TOP_K);
    return [rankedExamples, randomExamples];
  }, [modelData?.dataset?.data]);

  const [labeledData, setLabeledData] = React.useState<LabeledData>({});

  let semanticSearchExamples: Example[] = [];
  if (searchExamplesData != null) {
    semanticSearchExamples = searchExamplesData.row_results.slice(0, TOP_K).map((row) => {
      const text = modelData && modelData.dataset ? modelData.dataset.data[row.row_idx].text : '';
      return {text, id: row.row_idx.toString()};
    });
  }
  const isLoading =
    isLoadModelFetching || isModelFetching || isSaveModelLoading || isSearchExamplesLoading;

  const labeledExamples = Object.entries(labeledData).map(([rowIdx]) => ({
    text: modelData?.dataset?.data[+rowIdx].text ?? '',
    id: rowIdx,
  }));
  const labeledTable =
    filterView === 'labeled' ? (
      <>
        <ExampleViewer
          examples={labeledExamples}
          labeledData={labeledData}
          exampleLabeled={(labeledData) => setLabeledData(labeledData)}
        ></ExampleViewer>
      </>
    ) : null;
  const semanticTable =
    filterView === 'semantic' ? (
      <>
        {semanticSearchExamples.length > 0 ? (
          <ExampleViewer
            examples={semanticSearchExamples}
            labeledData={labeledData}
            exampleLabeled={(labeledData) => setLabeledData(labeledData)}
          ></ExampleViewer>
        ) : (
          'Please enter a search query'
        )}
      </>
    ) : null;

  const rankedTable =
    filterView === 'ranked' ? (
      <>
        <ExampleViewer
          examples={rankedExamples}
          labeledData={labeledData}
          exampleLabeled={(labeledData) => setLabeledData(labeledData)}
        ></ExampleViewer>
      </>
    ) : null;

  const randomTable =
    filterView === 'random' ? (
      <ExampleViewer
        examples={randomExamples}
        labeledData={labeledData}
        exampleLabeled={(labeledData) => setLabeledData(labeledData)}
      ></ExampleViewer>
    ) : null;
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
            <div className="flex flex-row mt-2 w-96">
              <SlInput
                placeholder="Search"
                value={searchQuery}
                className="w-full"
                onSlChange={(e) => {
                  setSearchQuery((e.target as HTMLInputElement).value);
                }}
              ></SlInput>
              <SlButton
                variant="primary"
                className="mt-1 mr-2 ml-2"
                size="small"
                onClick={() => {
                  setFilterView('semantic');
                  searchExamples({
                    username: username!,
                    modelName: modelName!,
                    query: searchQuery,
                  });
                }}
              >
                Search
              </SlButton>
            </div>
            <div className="flex flex-row mt-2 w-64">
              <SlButton
                variant="primary"
                className="mt-1 mr-2"
                size="small"
                onClick={() => saveModelClicked()}
              >
                Save
              </SlButton>
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
              {/* Save data */}
              <div className="w-full flex flex-row">
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
            </div>
            <div className="flex flex-col mt-4">
              <SlRadioGroup
                value={filterView}
                onSlChange={(e) =>
                  setFilterView((e.target as HTMLInputElement).value as FilterView)
                }
              >
                <SlRadioButton value="labeled">
                  Labeled ({labeledExamples.length} examples)
                </SlRadioButton>
                <SlRadioButton value="semantic">
                  Semantic ({semanticSearchExamples.length} examples)
                </SlRadioButton>
                <SlRadioButton value="ranked">
                  Ranked ({rankedExamples.length} examples)
                </SlRadioButton>
                <SlRadioButton value="random">
                  Random ({randomExamples.length} examples)
                </SlRadioButton>
              </SlRadioGroup>
              <div className={`${isLoading ? 'opacity-25' : ''}`}>
                {labeledTable}
                {semanticTable}
                {rankedTable}
                {randomTable}
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
