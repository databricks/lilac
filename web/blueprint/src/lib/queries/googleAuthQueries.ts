import {GoogleLoginService} from '$lilac';
import {queryClient} from './queryClient';
import {createApiMutation} from './queryUtils';
import {AUTH_INFO_TAG} from './serverQueries';

export const googleLogoutMutation = createApiMutation(GoogleLoginService.logout, {
  onSuccess: () => queryClient.invalidateQueries([AUTH_INFO_TAG])
});
