import {SlButton} from '@shoelace-style/shoelace/dist/react';
import * as React from 'react';
import {Link} from 'react-router-dom';
import styles from './header.module.css';
import {SearchBox} from './search_box';

export const Header = React.memo(function Header(): JSX.Element {
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
      <div className="flex items-center">
        <Link to="/dataset_loader">
          <SlButton variant="success" className="mt-1 mr-4">
            Load a dataset
          </SlButton>
        </Link>
      </div>
    </div>
  );
});
