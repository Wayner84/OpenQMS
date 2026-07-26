/** Types for the People module, matching docs/API.md#people-module-milestone-1. */

export type CompanyType = 'customer' | 'supplier' | 'other';

export interface Company {
  id: string;
  organisation_id: string;
  name: string;
  type: CompanyType;
  address: string | null;
  phone: string | null;
  general_email: string | null;
  notes: string | null;
  created_by_id: string | null;
  updated_by_id: string | null;
}

export interface CompanyWriteRequest {
  name: string;
  type: CompanyType;
  address?: string | null;
  phone?: string | null;
  general_email?: string | null;
  notes?: string | null;
}

export interface CompanyListResponse {
  items: Company[];
  total: number;
  limit: number;
  offset: number;
}

export interface Person {
  id: string;
  organisation_id: string;
  company_id: string | null;
  first_name: string;
  last_name: string;
  email: string | null;
  phone: string | null;
  role: string | null;
  department: string | null;
  notes: string | null;
  is_employee: boolean;
  created_by_id: string | null;
  updated_by_id: string | null;
}

export interface PersonWriteRequest {
  company_id?: string | null;
  first_name: string;
  last_name: string;
  email?: string | null;
  phone?: string | null;
  role?: string | null;
  department?: string | null;
  notes?: string | null;
  is_employee: boolean;
}

export interface PersonListResponse {
  items: Person[];
  total: number;
  limit: number;
  offset: number;
}

export interface ListPeopleParams {
  companyId?: string;
  isEmployee?: boolean;
  department?: string;
  search?: string;
  limit?: number;
  offset?: number;
}
