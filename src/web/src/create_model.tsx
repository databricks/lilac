import {
  SlButton,
  SlIcon,
  SlInput,
  SlOption,
  SlSelect,
  SlSpinner,
  SlTextarea,
} from '@shoelace-style/shoelace/dist/react';
import * as React from 'react';
import {Link} from 'react-router-dom';
import styles from './create_model.module.css';
import {useCreateModelMutation} from './store/store';
import {getModelLink, renderError} from './utils';

export const CreateModel = React.memo(function CreateModel(): JSX.Element {
  const [username, setUsername] = React.useState('nikhil');
  const [modelName, setModelName] = React.useState<string>('');
  const [description, setDescription] = React.useState('');

  const [
    createModel,
    {
      isLoading: isCreateLoading,
      isError: isCreateError,
      error: createError,
      isSuccess: isCreateSuccess,
    },
  ] = useCreateModelMutation();
  // TODO: Use authentication tokens to populate the user.
  const users = ['nikhil', 'daniel'].map((user) => {
    return (
      <SlOption key={user} value={user}>
        {user}
      </SlOption>
    );
  });

  const createClicked = () => {
    createModel({username: username, name: modelName, description});
  };

  return (
    <>
      <div className={`flex flex-col items-center ${styles.create_container}`}>
        <div className={styles.create_row}>
          <div className="text-2xl font-bold">Create a new model</div>
        </div>
        <div className={styles.create_row}>
          <div className="flex flex-row justify-left items-left">
            <div>
              <SlSelect
                size="medium"
                value={username}
                hoist={true}
                label="Owner"
                onSlChange={(e) => setUsername((e.target as HTMLInputElement).value)}
              >
                {users}
              </SlSelect>
            </div>
            <div className="mx-2">
              <span className="inline-block align-text-bottom text-xl pt-8">/</span>
            </div>
            <div>
              <SlInput
                value={modelName}
                label="Model Name"
                onSlChange={(e) => setModelName((e.target as HTMLInputElement).value)}
              />
            </div>
          </div>
        </div>
        <div className={styles.create_row}>
          <SlTextarea
            value={description}
            placeholder="(Optional) Enter a model description"
            onSlChange={(e) => setDescription((e.target as HTMLInputElement).value)}
          />
        </div>
        <div className={styles.create_row}>
          <SlButton
            disabled={isCreateLoading || isCreateSuccess}
            variant="success"
            className="mt-1 mr-4"
            onClick={() => createClicked()}
          >
            Create model
          </SlButton>

          {isCreateLoading || isCreateSuccess ? (
            <div className="mt-8 flex flex-row flex-nowrap">
              <div className="flex flex-row w-8 h-8">
                {isCreateLoading ? (
                  <SlSpinner className={styles.create_step_loading} />
                ) : (
                  <SlIcon className={styles.create_step_complete} name="check-lg" />
                )}
              </div>
              <div className="my-auto">Creating model...</div>
            </div>
          ) : (
            <></>
          )}
          {isCreateSuccess ? (
            <div className="mt-4">
              <div className="mt-4">
                <Link to={getModelLink(username, modelName)}>
                  <SlButton variant="primary" pill>
                    View model
                  </SlButton>
                </Link>
              </div>
            </div>
          ) : (
            <></>
          )}

          <div className="mt-4">{isCreateError ? <>{renderError(createError)}</> : <></>}</div>
        </div>
      </div>
    </>
  );
});
