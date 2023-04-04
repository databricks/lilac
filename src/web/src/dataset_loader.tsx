import {SlInput, SlOption, SlSelect, SlSpinner} from '@shoelace-style/shoelace/dist/react';
import * as React from 'react';
import {useGetSourceFieldsQuery, useGetSourcesQuery} from './store/api_data_loader';
import {queryResult as renderQuery, renderError} from './utils';

export const DatasetLoader = (): JSX.Element => {
  const sources = useGetSourcesQuery();
  const [sourceName, setSourceName] = React.useState<string>();

  const source = useGetSourceFieldsQuery({sourceName: sourceName!}, {skip: sourceName == null});
  console.log(source, source.currentData);

  const sourcesSelect = sources.isFetching ? (
    <SlSpinner />
  ) : sources.error || sources.currentData == null ? (
    renderError(sources.error)
  ) : (
    <>
      <SlSelect
        size="medium"
        value={sourceName}
        hoist={true}
        label="Source"
        onSlChange={(e) => setSourceName((e.target as HTMLInputElement).value)}
      >
        {sources.currentData.sources.map((sourceName) => (
          <SlOption key={sourceName} value={sourceName}>
            {sourceName}
          </SlOption>
        ))}
      </SlSelect>
    </>
  );

  const sourceFieldsForm = renderQuery(source, (pydanticFields) => (
    <div>
      {pydanticFields.map((field) => (
        <div>
          <SlInput
            // value={modelName}
            label={field.name}
            helpText={field.type}
            // onSlChange={(e) => setModelName((e.target as HTMLInputElement).value)}
          />
        </div>
      ))}
    </div>
  ));

  return sources.currentData != null ? (
    <>
      <div className="flex flex-col">
        <div>{sourcesSelect}</div>
        <div>{sourceFieldsForm}</div>
      </div>
    </>
  ) : (
    <>nuthin</>
  );
};
