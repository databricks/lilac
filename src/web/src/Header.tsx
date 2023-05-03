import {SlButton, SlIcon, SlProgressRing, SlSpinner} from '@shoelace-style/shoelace/dist/react';
import * as React from 'react';
import {Link} from 'react-router-dom';
import {TaskInfo} from '../fastapi_client';
import {useAppDispatch, useAppSelector} from './hooks';
import {SearchBox} from './searchBox/SearchBox';
import {setTasksPanelOpen, useLazyGetTaskManifestQuery} from './store/store';
import {formatDatetime, renderQuery, useClickOutside} from './utils';

// The poll interval when the tasks tray is open vs closed.
const TASKS_POLL_OPEN_INTERVAL_MS = 1000;
const TASKS_POLL_CLOSED_INTERVAL_MS = 10000;

const spinnerSizePx = 40;
export const Task = React.memo(({task}: {task: TaskInfo}): JSX.Element => {
  const startDateTime = new Date(task.start_timestamp);
  const endDateTime = new Date(task.end_timestamp || '');
  let datetimeInfo: string | JSX.Element = '';
  if (task.status === 'pending') {
    datetimeInfo = formatDatetime(startDateTime);
  } else if (task.status === 'completed') {
    const elapsedTimeSeconds = (endDateTime.getTime() - startDateTime.getTime()) / 1000;
    let ellapsedTimeMessage = '';
    if (elapsedTimeSeconds < 60) {
      ellapsedTimeMessage = `${Math.round(elapsedTimeSeconds)} seconds`;
    } else if (elapsedTimeSeconds < 60 * 60) {
      ellapsedTimeMessage = `${(elapsedTimeSeconds / 60).toFixed(1)} minutes`;
    } else {
      ellapsedTimeMessage = `${(elapsedTimeSeconds / (60 * 60)).toFixed(1)} hours`;
    }

    datetimeInfo = `Finished ${formatDatetime(endDateTime)} (${ellapsedTimeMessage})`;
  } else if (task.status === 'error') {
    datetimeInfo = (
      <p className="text-red-400">
        Failed {formatDatetime(endDateTime)}. <br></br>
        {task.error}
      </p>
    );
  }

  let taskStatusEl: JSX.Element = <></>;
  if (task.status === 'completed') {
    taskStatusEl = <SlIcon className="text-2xl text-green-500" name="check-lg"></SlIcon>;
  } else if (task.status === 'error') {
    taskStatusEl = <SlIcon className="text-2xl text-red-500" name="exclamation-circle"></SlIcon>;
  } else {
    if (task.progress != null) {
      taskStatusEl = (
        <SlProgressRing
          value={task.progress * 100}
          style={
            {
              '--size': `${spinnerSizePx}px`,
              '--track-width': '2px',
              '--indicator-width': '2px',
            } as React.CSSProperties
          }
          className="text-xs"
        >
          {' '}
          {Math.round(task.progress * 100)}%
        </SlProgressRing>
      );
    } else {
      taskStatusEl = <SlSpinner style={{fontSize: `${spinnerSizePx}px`}} />;
    }
  }
  return (
    <div className="border-b last:border-b-0">
      <div className="flex flex-row bg-white p-4 text-sm">
        <div className="flex flex-grow flex-col justify-center">
          <div>{task.name}</div>
          <div className="mt-0.5 text-sm font-light text-slate-400">{datetimeInfo}</div>
        </div>
        <div
          style={{width: `${spinnerSizePx}px`}}
          className="flex items-center justify-center text-sm"
        >
          {taskStatusEl}
        </div>
      </div>
    </div>
  );
});

Task.displayName = 'Task';

export const TaskViewer = (): JSX.Element => {
  const dispatch = useAppDispatch();

  const [loadTaskManifest, taskManifest] = useLazyGetTaskManifestQuery();
  const tasksPanelOpen = useAppSelector((state) => state.app.tasksPanelOpen);

  const tasksDrawerRef = React.useRef<HTMLDivElement>(null);
  const buttonContainerRef = React.useRef<HTMLDivElement>(null);

  useClickOutside(tasksDrawerRef, [buttonContainerRef], () => dispatch(setTasksPanelOpen(false)));

  // Poll for tasks. When the tray is open, we poll faster.
  React.useEffect(() => {
    loadTaskManifest();

    const timer = setInterval(
      () => loadTaskManifest(),
      tasksPanelOpen ? TASKS_POLL_OPEN_INTERVAL_MS : TASKS_POLL_CLOSED_INTERVAL_MS
    );
    return () => clearInterval(timer);
  }, [loadTaskManifest, tasksPanelOpen]);

  const tasksElement = renderQuery(taskManifest, (taskManager) => {
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

    for (const [taskId, task] of tasks) {
      numTasks++;
      if (task.status === 'pending') {
        numPending++;
      }
      taskElements.push(<Task task={task} key={taskId}></Task>);
    }
    let buttonVariant: 'default' | 'primary' | 'success' | 'text' | undefined = 'default';
    let taskMessage = '';
    if (numTasks === 0) {
      buttonVariant = 'text';
      taskMessage = 'No tasks';
    } else if (numPending == 0) {
      buttonVariant = 'success';
      taskMessage = 'Tasks complete';
    } else {
      buttonVariant = 'primary';
      taskMessage = `${numPending} ${numPending === 1 ? 'task' : 'tasks'} pending`;
    }

    return (
      <>
        <div ref={buttonContainerRef}>
          <SlButton
            variant={buttonVariant}
            disabled={numTasks === 0}
            outline
            size="medium"
            onClick={() => (numTasks > 0 ? dispatch(setTasksPanelOpen(!tasksPanelOpen)) : null)}
          >
            <span className="mx-2">{taskMessage}</span>
          </SlButton>
        </div>
        <div
          ref={tasksDrawerRef}
          className={`absolute right-0 top-full
           z-50 -mt-2 w-96 ${tasksPanelOpen ? 'visible' : 'hidden'}`}
        >
          <div
            className={`flex max-h-96 flex-col overflow-y-scroll
            rounded border border-slate-300 shadow-lg`}
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
    <div className="flex h-20 justify-between gap-x-4 border-b px-8">
      <div className="flex items-center text-xl">
        <Link to="/">Lilac</Link>
      </div>
      <div className="z-50 my-4 flex w-full max-w-2xl">
        <SearchBox />
      </div>
      <div className="relative flex items-center">
        <TaskViewer></TaskViewer>
      </div>
    </div>
  );
};
