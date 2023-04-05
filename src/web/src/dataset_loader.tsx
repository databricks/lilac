import {
  SlButton,
  SlInput,
  SlOption,
  SlSelect,
  SlSpinner,
} from '@shoelace-style/shoelace/dist/react';
import * as React from 'react';
import styles from './dataset_loader.module.css';
import {JSONSchemaForm} from './json_schema_form';
import {
  useGetSourceSchemaQuery,
  useGetSourcesQuery,
  useLoadDatasetMutation,
} from './store/api_data_loader';
import {renderError, renderQuery} from './utils';

export const DatasetLoader = (): JSX.Element => {
  const sources = useGetSourcesQuery();
  const [namespace, setNamespace] = React.useState<string>('local');
  const [datasetName, setDatasetName] = React.useState<string>('');
  const [sourceName, setSourceName] = React.useState<string>();
  const [formData, setFormData] = React.useState<{[key: string]: string}>({});

  const sourceSchema = useGetSourceSchemaQuery(
    {sourceName: sourceName!},
    {skip: sourceName == null}
  );

  const sourcesSelect = renderQuery(sources, (sources) => (
    <div className={styles.row}>
      <SlSelect
        size="medium"
        value={sourceName}
        hoist={true}
        label="Choose a data loader"
        onSlChange={(e) => setSourceName((e.target as HTMLInputElement).value)}
      >
        {sources.sources.map((sourceName) => (
          <SlOption key={sourceName} value={sourceName}>
            {sourceName}
          </SlOption>
        ))}
      </SlSelect>
    </div>
  ));

  const [
    loadDataset,
    {
      isLoading: isLoadDatasetLoading,
      isError: isLoadDatasetError,
      error: loadDatasetError,
      isSuccess: isLoadDatasetSuccess,
    },
  ] = useLoadDatasetMutation();

  const loadDatasetButtonDisabled =
    sources.currentData == null ||
    sourceSchema.currentData == null ||
    datasetName == '' ||
    namespace == '';

  const sourceFieldsForm = renderQuery(sourceSchema, (sourceSchema) => (
    <JSONSchemaForm
      schema={sourceSchema}
      ignoreProperties={['source_name']}
      onFormData={(formData) => setFormData(formData)}
    ></JSONSchemaForm>
  ));
  const loadClicked = () => {
    loadDataset({
      source_name: sourceName!,
      config: formData,
      namespace,
      dataset_name: datasetName,
    });
  };

  return (
    <>
      <div
        className={`
          flex flex-col items-center ${styles.container}
          rounded overflow-hidden shadow-lg`}
      >
        <div className={styles.row}>
          <div className="text-2xl font-bold">Load a dataset</div>
        </div>
        <div className={styles.row}>
          <SlInput
            value={namespace}
            label="Namespace"
            required={true}
            onSlChange={(e) => setNamespace((e.target as HTMLInputElement).value)}
          />
        </div>
        <div className={styles.row}>
          <SlInput
            value={datasetName}
            label="Dataset Name"
            help-text="The name of the dataset after it has been loaded."
            required={true}
            onSlChange={(e) => setDatasetName((e.target as HTMLInputElement).value)}
          />
        </div>
        {sourcesSelect}
        <div className={styles.row}>{sourceFieldsForm}</div>
        <div className={styles.row}>
          <SlButton
            disabled={loadDatasetButtonDisabled}
            variant="success"
            className="mt-1 mr-4"
            onClick={() => loadClicked()}
          >
            Load dataset
          </SlButton>
          {isLoadDatasetLoading ? <SlSpinner></SlSpinner> : null}
          {isLoadDatasetError ? renderError(loadDatasetError) : null}
          {isLoadDatasetSuccess ? 'SUCCESS' : null}
        </div>
      </div>
    </>
  );
};
