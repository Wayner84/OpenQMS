/** Typed client functions for the People module, per docs/API.md#people-module-milestone-1. */

import { apiDelete, apiGet, apiPatch, apiPost } from '../../shared/api/client';
import type {
  Company,
  CompanyListResponse,
  CompanyWriteRequest,
  ListPeopleParams,
  Person,
  PersonListResponse,
  PersonWriteRequest,
} from './types';

/** GET /api/v1/companies (paginated, scoped to the caller's own organisation). */
export function listCompanies(
  params: { limit?: number; offset?: number } = {},
): Promise<CompanyListResponse> {
  const query = new URLSearchParams();
  if (params.limit !== undefined) {
    query.set('limit', String(params.limit));
  }
  if (params.offset !== undefined) {
    query.set('offset', String(params.offset));
  }
  const queryString = query.toString();
  return apiGet<CompanyListResponse>(`/api/v1/companies${queryString ? `?${queryString}` : ''}`);
}

/** POST /api/v1/companies. */
export function createCompany(payload: CompanyWriteRequest): Promise<Company> {
  return apiPost<Company>('/api/v1/companies', payload);
}

/**
 * PATCH /api/v1/companies/{id}. Throws {@link ApiError} with status 404 for a
 * cross-organisation id.
 */
export function updateCompany(id: string, payload: CompanyWriteRequest): Promise<Company> {
  return apiPatch<Company>(`/api/v1/companies/${id}`, payload);
}

/**
 * DELETE /api/v1/companies/{id}. Throws {@link ApiError} with status 409 if any
 * `people` row still references this company — the caller must reassign or delete
 * those contacts first.
 */
export function deleteCompany(id: string): Promise<void> {
  return apiDelete(`/api/v1/companies/${id}`);
}

/** GET /api/v1/companies/{id}/people — paginated list of contacts for one company. */
export function listCompanyPeople(
  companyId: string,
  params: { limit?: number; offset?: number } = {},
): Promise<PersonListResponse> {
  const query = new URLSearchParams();
  if (params.limit !== undefined) {
    query.set('limit', String(params.limit));
  }
  if (params.offset !== undefined) {
    query.set('offset', String(params.offset));
  }
  const queryString = query.toString();
  return apiGet<PersonListResponse>(
    `/api/v1/companies/${companyId}/people${queryString ? `?${queryString}` : ''}`,
  );
}

/**
 * GET /api/v1/people (paginated, scoped to the caller's own organisation).
 * Supports `company_id`/`is_employee`/`department` exact filters and a `search`
 * substring match across name/email/role.
 */
export function listPeople(params: ListPeopleParams = {}): Promise<PersonListResponse> {
  const query = new URLSearchParams();
  if (params.companyId !== undefined) {
    query.set('company_id', params.companyId);
  }
  if (params.isEmployee !== undefined) {
    query.set('is_employee', String(params.isEmployee));
  }
  if (params.department !== undefined) {
    query.set('department', params.department);
  }
  if (params.search !== undefined) {
    query.set('search', params.search);
  }
  if (params.limit !== undefined) {
    query.set('limit', String(params.limit));
  }
  if (params.offset !== undefined) {
    query.set('offset', String(params.offset));
  }
  const queryString = query.toString();
  return apiGet<PersonListResponse>(`/api/v1/people${queryString ? `?${queryString}` : ''}`);
}

/**
 * POST /api/v1/people. Throws {@link ApiError} with status 422 for a contradictory
 * `is_employee`/`company_id` combination, or 404 if `company_id` doesn't exist in
 * this organisation.
 */
export function createPerson(payload: PersonWriteRequest): Promise<Person> {
  return apiPost<Person>('/api/v1/people', payload);
}

/** PATCH /api/v1/people/{id}. See {@link createPerson} for the error contract. */
export function updatePerson(id: string, payload: PersonWriteRequest): Promise<Person> {
  return apiPatch<Person>(`/api/v1/people/${id}`, payload);
}

/** DELETE /api/v1/people/{id}. Throws {@link ApiError} with status 404 for a cross-organisation id. */
export function deletePerson(id: string): Promise<void> {
  return apiDelete(`/api/v1/people/${id}`);
}
