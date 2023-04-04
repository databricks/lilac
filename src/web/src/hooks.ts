import {TypedUseSelectorHook, useDispatch, useSelector} from 'react-redux';
import type {AppDispatch, RootState} from './store/store';

// Use throughout the app instead of plain `useDispatch` and `useSelector`.
// See: https://react-redux.js.org/tutorials/typescript-quick-start
export const useAppDispatch: () => AppDispatch = useDispatch;
export const useAppSelector: TypedUseSelectorHook<RootState> = useSelector;
