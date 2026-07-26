/** Types for the auth module, matching docs/API.md#authentication. */

export type UserRole = 'admin' | 'member';

export interface User {
  id: string;
  organisation_id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
}
