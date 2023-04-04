import {SlSpinner} from '@shoelace-style/shoelace/dist/react';
import * as React from 'react';
import {Link} from 'react-router-dom';
import {useListModelsQuery} from './store/store';
import {getModelLink, renderError} from './utils';

export const Home = React.memo(function Home(): JSX.Element {
  const models = useListModelsQuery();

  return (
    <>
      <div className="flex flex-col">
        <div className="flex flex-col">
          {models.isFetching ? (
            <SlSpinner />
          ) : models.error || models.currentData == null ? (
            renderError(models.error)
          ) : (
            models.currentData.models.map((model, i) => (
              <Link key={`model-link-${i}`} to={getModelLink(model.username, model.name)}>
                {model.username}/{model.name}
              </Link>
            ))
          )}
        </div>
      </div>
    </>
  );
});
