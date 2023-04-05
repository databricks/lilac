import {
  SlButton,
  SlInput,
  SlOption,
  SlSelect,
  SlSpinner,
} from '@shoelace-style/shoelace/dist/react';
import * as React from 'react';
import {PydanticField} from '../fastapi_client';
import styles from './dataset_loader.module.css';
import {
  useGetSourceFieldsQuery,
  useGetSourcesQuery,
  useLoadDatasetMutation,
} from './store/api_data_loader';
import {renderError, renderQuery} from './utils';

export const DatasetLoader = (): JSX.Element => {
  const sources = useGetSourcesQuery();
  const [namespace, setNamespace] = React.useState<string>('local');
  const [datasetName, setDatasetName] = React.useState<string>('');
  const [sourceName, setSourceName] = React.useState<string>();

  const source = useGetSourceFieldsQuery({sourceName: sourceName!}, {skip: sourceName == null});

  const sourcesSelect = renderQuery(sources, (sources) => (
    <div className={styles.row}>
      <SlSelect
        size="medium"
        value={sourceName}
        hoist={true}
        label="Source"
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
    source.currentData == null ||
    datasetName == null ||
    namespace == null;
  const FieldsForm = React.memo(function Form({
    pydanticFields,
  }: {
    pydanticFields: PydanticField[];
  }): JSX.Element {
    const [formData, setFormData] = React.useState<{[key: string]: string}>({});
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
        <div className={styles.row}>
          {pydanticFields.map((field) => (
            <div key={field.name} className="mt-4">
              <SlInput
                value={formData[field.name] || ''}
                label={field.name}
                type={field.type === 'int' ? 'number' : 'text'}
                required={!field.optional}
                onSlChange={(e) =>
                  setFormData({
                    ...formData,
                    [field.name]: (e.target as HTMLInputElement).value,
                  })
                }
              />
            </div>
          ))}
        </div>
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
      </>
    );
  });

  const sourceFieldsForm = renderQuery(source, (pydanticFields) => (
    <FieldsForm pydanticFields={pydanticFields}></FieldsForm>
  ));

  return (
    <>
      <div className={`flex flex-col items-center ${styles.container}`}>
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
            required={true}
            onSlChange={(e) => setDatasetName((e.target as HTMLInputElement).value)}
          />
        </div>
        {sourcesSelect}
        {sourceFieldsForm}
      </div>
    </>
  );
};
