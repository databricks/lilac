import {SlButton, SlIcon, SlSpinner} from '@shoelace-style/shoelace/dist/react';
import * as React from 'react';
import {Link} from 'react-router-dom';
import styles from './header.module.css';
import {SearchBox} from './search_box';
import {useGetTasksQuery} from './store/store';
import {renderQuery} from './utils';

export const Header = React.memo(function Header(): JSX.Element {
  const taskManager = useGetTasksQuery();
  const tasksElement = renderQuery(taskManager, (taskManager) => {
    let numPending = 0;
    let numTasks = 0;
    let pendingNoProgress = false;
    for (const [taskId, task] of Object.entries(taskManager.tasks || {})) {
      console.log(task.name, taskId);
      numTasks++;
      if (task.status === 'pending') {
        numPending++;
        if (task.progress == null) {
          pendingNoProgress = true;
        }
      }
    }
    [pendingNoProgress];
    let buttonVariant: 'default' | 'neutral' | 'success' | undefined = 'default';

    let taskMessage = '';
    if (numTasks === 0) {
      buttonVariant = undefined;
      taskMessage = 'No tasks';
    } else if (numPending == 0) {
      buttonVariant = 'neutral';
      taskMessage = 'Tasks complete';
    } else {
      buttonVariant = 'success';
      taskMessage = `${numPending} ${numPending === 1 ? 'task' : 'tasks'} pending`;
    }

    let taskIcon = <></>;
    if (numTasks === 0) {
      taskIcon = <></>;
    } else if (numPending > 0) {
      taskIcon = <SlSpinner></SlSpinner>;
    } else {
      taskIcon = <SlIcon name="check-lg"></SlIcon>;
    }

    return (
      <>
        <SlButton variant={buttonVariant} outline size="medium">
          <span className="mx-2">{taskMessage}</span>
          {taskIcon}
        </SlButton>
      </>
    );
  });

  return (
    <div className={`${styles.app_header} flex justify-between border-b`}>
      <div className="flex items-center">
        <div className={`${styles.app_header_title} text-primary`}>
          <Link to="/">Lilac</Link>
        </div>
      </div>
      <div className="w-96 z-50 flex mt-2">
        <SearchBox />
      </div>
      <div className="flex items-center mr-4">{tasksElement}</div>
    </div>
  );
});
