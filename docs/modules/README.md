# Product Modules

One planning document per product module named in
[docs/ProductSpecification.md](../ProductSpecification.md). Every document below
covers purpose, planned database tables, planned APIs, workflow, relationships to
other modules, future improvements, and known issues/status — all currently
**Status: Planned**, since no module has been implemented yet (see
[docs/CurrentStatus.md](../CurrentStatus.md)). Implementation order and reasoning:
[docs/Roadmap.md](../Roadmap.md).

| Module | Milestone | Summary |
|---|---|---|
| [Document Management](DocumentManagement.md) | M2 | SOPs, work instructions, forms, policies, controlled documents, approval workflow |
| [Calibration and Asset Management](CalibrationAndAssetManagement.md) | M5 | Inspection/measuring equipment and company assets, calibration schedules, certificates |
| [People](People.md) | M1 | Shared employees, customers, suppliers and contacts directory |
| [Products](Products.md) | M3 | Internal/purchased products, assemblies and components |
| [Suppliers](Suppliers.md) | M3 | Approved supplier records, certifications, performance, risk rating |
| [NCR](NCR.md) | M4 | Internal and supplier non-conformance reports, investigation and corrective action |
| [FAIR](FAIR.md) | M7 | AS9102 First Article Inspection Reports |
| [SPC](SPC.md) | M8 | Statistical process control: Cp/Cpk/Pp/Ppk, control charts, trends |
| [Health and Safety: Government Guidance](HealthAndSafetyGuidance.md) | M9 | Browse live HSE guidance |
| [Health and Safety: Audits](HealthAndSafetyAudits.md) | M9 | Configurable audit templates, findings, actions |
| [Health and Safety: Incident Reporting](HealthAndSafetyIncidentReporting.md) | M9 | Near misses, incidents, accidents, investigation |
| [Health and Safety: Risk Assessments](HealthAndSafetyRiskAssessments.md) | M9 | Configurable risk matrices, hazards, control measures |
| [Maintenance](Maintenance.md) | M6 | Maintenance requests, prioritisation, completion history |

## Conventions used in every module document

- All tables are tenant-scoped (`organisation_id` foreign key) unless explicitly
  noted as shared reference data, per
  [Architecture.md](../Architecture.md#multi-tenancy-strategy).
- All APIs are planned under the module's reserved prefix in
  [API.md](../API.md#module-endpoint-prefixes-reserved-not-yet-implemented).
- "Planned" tables/APIs describe the target design for the module's milestone, not
  code that exists — cross-check [docs/CurrentStatus.md](../CurrentStatus.md) before
  assuming anything described here has been built.
- Cross-module references follow [ProductSpecification.md](../ProductSpecification.md#module-relationships):
  prefer references to canonical records over duplicating data.
