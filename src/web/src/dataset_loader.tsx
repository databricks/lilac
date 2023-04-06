import {
  SlButton,
  SlIcon,
  SlInput,
  SlOption,
  SlSelect,
  SlSpinner,
} from '@shoelace-style/shoelace/dist/react';
import {JSONSchema7Type} from 'json-schema';
import * as React from 'react';
import styles from './dataset_loader.module.css';
import {JSONSchemaForm} from './json_schema_form';
import {
  useGetSourceSchemaQuery,
  useGetSourcesQuery,
  useLoadDatasetMutation,
} from './store/api_dataset';
import {getDatasetLink, renderError, renderQuery} from './utils';

export const DatasetLoader = (): JSX.Element => {
  const sources = useGetSourcesQuery();
  const [namespace, setNamespace] = React.useState<string>('local');
  const [datasetName, setDatasetName] = React.useState<string>('');
  const [sourceName, setSourceName] = React.useState<string>('');
  const [formData, setFormData] = React.useState<{[key: string]: JSONSchema7Type}>({});

  const sourceSchema = useGetSourceSchemaQuery({sourceName: sourceName!}, {skip: sourceName == ''});

  const sourcesSelect = renderQuery(sources, (sources) => (
    <div className="w-60">
      <SlSelect
        size="medium"
        value={sourceName}
        label="Data loader"
        hoist={true}
        clearable
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

  const sourceFieldsForm = renderQuery(sourceSchema, (sourceSchema) =>
    sourceSchema != null ? (
      <div className={styles.row}>
        <JSONSchemaForm
          schema={sourceSchema}
          ignoreProperties={['source_name']}
          onFormData={(formData) => setFormData(formData)}
        ></JSONSchemaForm>
      </div>
    ) : (
      <></>
    )
  );
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
          flex flex-col ${styles.container}
          rounded overflow-hidden shadow-lg
          bg-slate-50`}
      >
        <div className={styles.row}>
          <div className="text-3xl">Create a dataset</div>
        </div>
        <div className={styles.row}>
          <div className="flex flex-row justify-left items-left flex-grow">
            <div className="w-44">
              <SlInput
                value={namespace}
                label="namespace"
                required={true}
                onSlChange={(e) => setNamespace((e.target as HTMLInputElement).value)}
              />
            </div>
            <div className="mx-4">
              <span className="inline-block align-text-bottom text-xl pt-8">/</span>
            </div>
            <div className="w-44">
              <SlInput
                value={datasetName}
                label="name"
                required={true}
                onSlChange={(e) => setDatasetName((e.target as HTMLInputElement).value)}
              />
            </div>
          </div>
        </div>

        <div className={styles.row}>{sourcesSelect}</div>
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
