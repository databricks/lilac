import '@shoelace-style/shoelace/dist/themes/light.css';
import {setBasePath} from '@shoelace-style/shoelace/dist/utilities/base-path';
import * as React from 'react';
import {createRoot} from 'react-dom/client';
import {Provider} from 'react-redux';
import {
  createBrowserRouter,
  createRoutesFromElements,
  Outlet,
  Route,
  RouterProvider,
} from 'react-router-dom';
import {CreateModel} from './create_model';
import {DatasetLoader} from './dataset_loader';
import {DatasetViewer} from './dataset_viewer/dataset_viewer';
import {Header} from './header';
import {Home} from './home';
import './index.css';
import {FilterMaker} from './model_viewer/filter_maker';
import {store} from './store/store';
setBasePath('/static/shoelace');

export const PageNotFound = React.memo(function PageNotFound(): JSX.Element {
  return <>Error: Page not found!</>;
});

export const AppContainer = function App(): JSX.Element {
  return (
    <>
      <div className="flex flex-col h-full w-full">
        <Header></Header>
        <div className="body flex w-full h-full overflow-hidden pt-4">
          <Outlet />
        </div>
      </div>
    </>
  );
};

const router = createBrowserRouter(
  createRoutesFromElements(
    <Route path="/" element={<AppContainer />}>
      <Route index element={<Home />} />
      <Route path="/datasets/:namespace/:datasetName" element={<DatasetViewer />} />
      <Route path="create" element={<CreateModel />} />
      <Route path="dataset_loader" element={<DatasetLoader />} />
      <Route path="/concepts/:namespace/:conceptName" element={<FilterMaker />} />
      <Route path="*" element={<PageNotFound />} />
    </Route>
  )
);

// Create the react render tree.
const root = createRoot(document.getElementById('root') as HTMLDivElement);
root.render(
  // Make the redux store available to the whole app.
  <React.StrictMode>
    <Provider store={store}>
      <RouterProvider router={router} />
    </Provider>
  </React.StrictMode>
);
