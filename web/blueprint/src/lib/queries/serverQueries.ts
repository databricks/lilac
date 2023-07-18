import {DefaultService} from '$lilac';
import {createApiQuery} from './queryUtils';

export const queryServerStatus = createApiQuery(DefaultService.serverStatus, 'server_status');
