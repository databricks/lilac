/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { UserAccess } from './UserAccess';
import type { UserInfo } from './UserInfo';

/**
 * Authentication information for the user.
 */
export type AuthenticationInfo = {
    user: (UserInfo | null);
    access: UserAccess;
    auth_enabled: boolean;
    huggingface_space_id: (string | null);
};

