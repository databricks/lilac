import {
  SlButton,
  SlIcon,
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
import {getDatasetLink, renderError, renderQuery} from './utils';

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
    <div className={styles.row}>
      <JSONSchemaForm
        schema={sourceSchema}
        ignoreProperties={['source_name']}
        onFormData={(formData) => setFormData(formData)}
      ></JSONSchemaForm>
    </div>
  ));
  const loadClicked = () => {
    loadDataset({
      sourceName: sourceName!,
      options: {
        config: formData,
        namespace,
        dataset_name: datasetName,
      },
    });
  };

  if (isLoadDatasetSuccess) {
    location.href = getDatasetLink(namespace, datasetName);
  }

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
          <div className="flex flex-row justify-left items-left flex-grow">
            <div className="flex-grow">
              <SlInput
                value={namespace}
                label="Namespace"
                required={true}
                onSlChange={(e) => setNamespace((e.target as HTMLInputElement).value)}
              />
            </div>
            <div className="mx-2">
              <span className="inline-block align-text-bottom text-xl pt-8">/</span>
            </div>
            <div className="flex-grow">
              <SlInput
                value={datasetName}
                label="Dataset Name"
                required={true}
                onSlChange={(e) => setDatasetName((e.target as HTMLInputElement).value)}
              />
            </div>
          </div>
        </div>
        {sourcesSelect}
        {sourceFieldsForm}
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
          {isLoadDatasetSuccess ? (
            <SlIcon className={styles.load_data_success} name="check-lg"></SlIcon>
          ) : null}
        </div>
      </div>
    </>
  );
};
