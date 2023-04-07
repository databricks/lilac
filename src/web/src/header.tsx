import {SlButton, SlIcon, SlProgressRing, SlSpinner} from '@shoelace-style/shoelace/dist/react';
import * as React from 'react';
import {Link} from 'react-router-dom';
import {TaskInfo} from '../fastapi_client';
import styles from './header.module.css';
import {SearchBox} from './search_box';
import {useLazyGetTasksQuery} from './store/store';
import {formatDatetime, renderQuery, useClickOutside} from './utils';

const TASKS_POLL_INTERVAL_MS = 2000;

const spinnerSizePx = 40;
export const Task = ({task}: {task: TaskInfo}): JSX.Element => {
  const startDateTime = new Date(task.start_timestamp);
  const endDateTime = new Date(task.end_timestamp || '');
  const datetimeInfo =
    task.status === 'pending' ? (
      <>{formatDatetime(startDateTime)}</>
    ) : (
      <>
        Finished {formatDatetime(endDateTime)} (
        {Math.round(endDateTime.getTime() - startDateTime.getTime()) / (1000 * 60)} mins)
      </>
    );
  return (
    <div className={`${styles.task_container} border-bottom-2 last:border-b-0`}>
      <div className="bg-slate-50 p-2 flex flex-row">
        <div className="flex flex-col flex-grow justify-center">
          <div>{task.name}</div>
          <div className="text-slate-400 text-sm">{datetimeInfo}</div>
        </div>
        <div
          style={{width: `${spinnerSizePx}px`}}
          className="text-sm flex justify-center items-center"
        >
          {task.status === 'completed' ? (
            <SlIcon
              className={styles.completed_task_icon}
              name="check-lg"
              style={{fontSize: '1.5rem'}}
            ></SlIcon>
          ) : task.progress != null ? (
            <SlProgressRing
              value={task.progress * 100}
              style={
                {
                  '--size': `${spinnerSizePx}px`,
                  '--track-width': '2px',
                  '--indicator-width': '2px',
                } as React.CSSProperties
              }
            >
              {Math.round(task.progress * 100)}%
            </SlProgressRing>
          ) : (
            <SlSpinner style={{fontSize: `${spinnerSizePx}px`}} />
          )}
        </div>
      </div>
    </div>
  );
};

export const TaskViewer = (): JSX.Element => {
  const [loadTaskManager, taskManager] = useLazyGetTasksQuery();
  const [tasksPanelOpen, setTasksPanelOpen] = React.useState(true);
  const tasksDrawerRef = React.useRef<HTMLDivElement>(null);
  const buttonContainerRef = React.useRef<HTMLDivElement>(null);

  useClickOutside(tasksDrawerRef, [buttonContainerRef], () => setTasksPanelOpen(false));

  // Poll for tasks.
  React.useEffect(() => {
    loadTaskManager();
    setInterval(() => loadTaskManager(), TASKS_POLL_INTERVAL_MS);

    if (tasksDrawerRef.current != null) {
      tasksDrawerRef.current.focus();
    }
  }, []);

  const tasksElement = renderQuery(taskManager, (taskManager) => {
    let numPending = 0;
    let numTasks = 0;
    const taskElements: JSX.Element[] = [];
    const tasks = Object.entries(taskManager.tasks || {});
    // Sort by start timestamp descending.
    tasks.sort((a, b) => {
      const aStart = new Date(a[1].start_timestamp);
      const bStart = new Date(b[1].start_timestamp);
      if (aStart == null) {
        return 1;
      }
      if (bStart == null) {
        return -1;
      }
      return aStart > bStart ? -1 : 1;
    });

    for (const [taskId, task] of Object.entries(taskManager.tasks || {})) {
      numTasks++;
      if (task.status === 'pending') {
        numPending++;
      }
      taskElements.push(<Task task={task} key={taskId}></Task>);
    }
    let buttonVariant: 'default' | 'primary' | 'success' | undefined = 'default';

    let taskMessage = '';
    if (numTasks === 0) {
      buttonVariant = undefined;
      taskMessage = 'No tasks';
    } else if (numPending == 0) {
      buttonVariant = 'success';
      taskMessage = 'Tasks complete';
    } else {
      buttonVariant = 'primary';
      taskMessage = `${numPending} ${numPending === 1 ? 'task' : 'tasks'} pending`;
    }

    console.log(tasksPanelOpen);
    return (
      <>
        <div className="mr-4" ref={buttonContainerRef}>
          <SlButton
            variant={buttonVariant}
            outline
            size="medium"
            onClick={() => setTasksPanelOpen(!tasksPanelOpen)}
          >
            <span className="mx-2">{taskMessage}</span>
          </SlButton>
        </div>
        <div
          ref={tasksDrawerRef}
          className={
            `absolute  ${styles.tasks_drawer} z-50 ` +
            `right-0 -mt-4 mr-4 top-full bg-white transition-2 `
          }
        >
          <div
            className={`flex flex-col border-slate-300 ${styles.task_element} ${
              tasksPanelOpen ? styles.task_elements_open : styles.task_elements_closed
            }`}
          >
            {taskElements}
          </div>
        </div>
      </>
    );
  });
  return <div>{tasksElement}</div>;
};

export const Header = (): JSX.Element => {
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
      <div className="relative flex items-center">
        <TaskViewer></TaskViewer>
      </div>
    </div>
  );
};
