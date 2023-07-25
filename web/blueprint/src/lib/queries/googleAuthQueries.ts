import {GoogleLoginService} from '$lilac';
import {CONCEPTS_TAG} from './conceptQueries';
import {DATASETS_TAG} from './datasetQueries';
import {queryClient} from './queryClient';
import {createApiMutation} from './queryUtils';
import {AUTH_INFO_TAG} from './serverQueries';

export const googleLogoutMutation = createApiMutation(GoogleLoginService.logout, {
  onSuccess: () => {
    queryClient.invalidateQueries([AUTH_INFO_TAG]);
    queryClient.invalidateQueries([CONCEPTS_TAG]);
    queryClient.invalidateQueries([DATASETS_TAG]);
  }
});
