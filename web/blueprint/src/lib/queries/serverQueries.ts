import {DefaultService} from '$lilac';
import {createApiQuery} from './queryUtils';

export const queryUserAcls = createApiQuery(DefaultService.userAcls, 'server_status');
