/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { UserAccess } from './UserAccess';
import type { UserInfo } from './UserInfo';

/**
 * Authentication information for the user.
 */
export type AuthenticationInfo = {
    user?: UserInfo;
    access: UserAccess;
    auth_enabled: boolean;
};

