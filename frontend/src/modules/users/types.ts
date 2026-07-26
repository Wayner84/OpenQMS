/** Types for the user management module, matching docs/API.md#user-management-milestone-1. */

import type { User, UserRole } from '../auth/types';

export interface CreateUserRequest {
  email: string;
  full_name: string;
  password: string;
  role: UserRole;
}

export interface UpdateUserRequest {
  full_name?: string;
  role?: UserRole;
  is_active?: boolean;
}

export interface UserListResponse {
  items: User[];
  total: number;
  limit: number;
  offset: number;
}
