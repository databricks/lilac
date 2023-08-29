import {DefaultService} from '$lilac';
import {createApiQuery} from './queryUtils';

export const AUTH_INFO_TAG = 'auth_info';
export const queryAuthInfo = createApiQuery(DefaultService.authInfo, AUTH_INFO_TAG);

export const SERVER_STATUS_TAG = 'status';
export const queryServerStatus = createApiQuery(DefaultService.status, SERVER_STATUS_TAG);
